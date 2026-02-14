#!/usr/bin/env python3
"""Generate markdown decision report for Tantivy vs Lance FTS from fixed eval snapshots."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_snapshot_json(snapshot_path: Path) -> dict[str, Any]:
    text = snapshot_path.read_text(encoding="utf-8")
    sections = text.split("\n---\n")
    if len(sections) < 2:
        raise ValueError(f"Invalid insta snapshot format: {snapshot_path}")
    return json.loads(sections[-1].strip())


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _offline_recommendation(summary: dict[str, Any]) -> tuple[str, list[str]]:
    tantivy = summary.get("tantivy", {})
    fts = summary.get("lance_fts", {})

    t_p = _to_float(tantivy.get("mean_p_at_5"))
    t_r = _to_float(tantivy.get("mean_r_at_5"))
    t_ndcg = _to_float(tantivy.get("mean_ndcg_at_5"))

    f_p = _to_float(fts.get("mean_p_at_5"))
    f_r = _to_float(fts.get("mean_r_at_5"))
    f_ndcg = _to_float(fts.get("mean_ndcg_at_5"))

    reasons: list[str] = []
    if t_p > f_p + 0.02:
        reasons.append(f"Tantivy precision lead detected (P@5 {t_p:.4f} vs {f_p:.4f}).")
    if t_r > f_r + 0.02:
        reasons.append(f"Tantivy recall lead detected (R@5 {t_r:.4f} vs {f_r:.4f}).")
    if f_ndcg > t_ndcg + 0.02:
        reasons.append(
            f"Lance FTS ranking quality lead detected (nDCG@5 {f_ndcg:.4f} vs {t_ndcg:.4f})."
        )

    # Decision logic tuned for pragmatic staged rollout.
    if (t_p >= f_p and t_r >= f_r) and not (f_ndcg > t_ndcg + 0.05):
        return "TANTIVY_DEFAULT_WITH_FTS_OPTION", reasons
    if (f_p >= t_p and f_r >= t_r and f_ndcg >= t_ndcg) and (f_ndcg > t_ndcg + 0.03):
        return "LANCE_FTS_DEFAULT", reasons
    return "SCENARIO_SPLIT_OR_HYBRID", reasons


def _per_scene_summary(snapshot_data: dict[str, Any]) -> list[str]:
    """Build per-scene winner summary from lance_fts_details and tantivy_details."""
    t_details = snapshot_data.get("tantivy_details") or []
    f_details = snapshot_data.get("lance_fts_details") or []
    if len(t_details) != len(f_details) or not t_details:
        return []

    by_scene: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for t_row, f_row in zip(t_details, f_details, strict=True):
        scene = (t_row.get("scene") or f_row.get("scene") or "unknown").strip()
        t_ndcg = _to_float(t_row.get("ndcg_at_5"))
        f_ndcg = _to_float(f_row.get("ndcg_at_5"))
        by_scene[scene].append((t_ndcg, f_ndcg))

    lines = []
    wins_t: list[str] = []
    wins_f: list[str] = []
    ties: list[str] = []
    for scene in sorted(by_scene.keys()):
        pairs = by_scene[scene]
        mean_t = sum(p[0] for p in pairs) / len(pairs)
        mean_f = sum(p[1] for p in pairs) / len(pairs)
        diff = mean_t - mean_f
        if diff > 0.02:
            wins_t.append(scene)
        elif diff < -0.02:
            wins_f.append(scene)
        else:
            ties.append(scene)

    if wins_t or wins_f or ties:
        lines.append("| Scene layer | Tantivy better | Lance FTS better | Tie |")
        lines.append("|-------------|----------------|------------------|-----|")
        lines.append(
            f"| v4 scenes | {', '.join(wins_t) or '—'} | "
            f"{', '.join(wins_f) or '—'} | {', '.join(ties) or '—'} |"
        )
    return lines


def _compose_report(
    snapshot_path: Path,
    snapshot_data: dict[str, Any],
    llm_report: dict[str, Any] | None,
    add_per_scene: bool = True,
) -> str:
    summary = snapshot_data.get("summary", {})
    decision, reasons = _offline_recommendation(summary)
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ")
    queries = snapshot_data.get("queries", 0)
    k = snapshot_data.get("k", 0)

    tantivy = summary.get("tantivy", {})
    fts = summary.get("lance_fts", {})

    lines = [
        "# Keyword Backend Decision Report",
        "",
        f"- Generated at: `{ts}`",
        f"- Offline source: `{snapshot_path}`",
        f"- Query count: `{queries}`",
        f"- Top-K: `{k}`",
        "",
        "## Offline Metrics",
        "",
        "| Backend | P@5 | R@5 | MRR | nDCG@5 | Success@1 |",
        "|---|---:|---:|---:|---:|---:|",
        f"| Tantivy | {tantivy.get('mean_p_at_5', 'n/a')} | {tantivy.get('mean_r_at_5', 'n/a')} | "
        f"{tantivy.get('mrr', 'n/a')} | {tantivy.get('mean_ndcg_at_5', 'n/a')} | "
        f"{tantivy.get('success_at_1', 'n/a')} |",
        f"| Lance FTS | {fts.get('mean_p_at_5', 'n/a')} | {fts.get('mean_r_at_5', 'n/a')} | "
        f"{fts.get('mrr', 'n/a')} | {fts.get('mean_ndcg_at_5', 'n/a')} | "
        f"{fts.get('success_at_1', 'n/a')} |",
        "",
        "## Recommendation",
        "",
        f"- Decision: `{decision}`",
    ]

    if reasons:
        lines.append("- Evidence:")
        for reason in reasons:
            lines.append(f"  - {reason}")
    else:
        lines.append("- Evidence: Offline metrics are close; prioritize operational simplicity.")

    if llm_report is not None:
        duel = llm_report.get("llm_duel_summary", {})
        reliable_ratio = duel.get("reliable_ratio", 0.0)
        lines.extend(
            [
                "",
                "## LLM Duel Signals",
                "",
                f"- Tantivy wins: `{duel.get('tantivy_wins', 0)}`",
                f"- Lance FTS wins: `{duel.get('lance_fts_wins', 0)}`",
                f"- Ties: `{duel.get('ties', 0)}`",
                f"- Tantivy win rate: `{duel.get('tantivy_win_rate', 0):.4f}`",
                f"- Lance FTS win rate: `{duel.get('lance_fts_win_rate', 0):.4f}`",
                f"- Reliable samples: `{duel.get('reliable_samples', 0)}`",
                f"- Reliable ratio: `{reliable_ratio:.4f}`",
                f"- High-confidence samples: `{duel.get('high_confidence_samples', 0)}`",
                f"- Avg vote agreement: `{duel.get('avg_vote_agreement', 0):.4f}`",
            ]
        )
        if reliable_ratio < 0.7:
            lines.extend(
                [
                    "",
                    "> Warning: LLM duel reliability is low. "
                    "Use offline IR metrics as primary decision evidence.",
                ]
            )
    else:
        lines.extend(
            [
                "",
                "## LLM Duel Signals",
                "",
                "- Not provided. Run live LLM eval and regenerate this report:",
                "```bash",
                "uv run python scripts/run_keyword_backend_llm_eval.py --output /tmp/keyword-llm-eval.json",
                "uv run python scripts/generate_keyword_backend_decision_report.py "
                "--llm-report /tmp/keyword-llm-eval.json",
                "```",
            ]
        )

    if add_per_scene:
        scene_lines = _per_scene_summary(snapshot_data)
        if scene_lines:
            lines.extend(["", "## Per-scene (v4) summary", ""] + scene_lines + [""])

    lines.extend(
        [
            "",
            "## Rollout Policy",
            "",
            "1. Keep `Tantivy` as default for router/tool discovery latency paths.",
            "2. Enable `Lance FTS` for Lance-native workflows requiring single data plane.",
            "3. Re-run report after any tokenizer/scoring change or dataset refresh.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path(
            "packages/rust/crates/omni-vector/tests/snapshots/"
            "test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap"
        ),
        help="Insta snapshot from test_keyword_backend_quality (v4_large = 120 queries, default)",
    )
    parser.add_argument(
        "--llm-report",
        type=Path,
        default=None,
        help="Optional JSON report produced by run_keyword_backend_llm_eval.py",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/testing/keyword-backend-decision-report.md"),
    )
    parser.add_argument(
        "--no-per-scene",
        action="store_true",
        help="Omit per-scene summary (e.g. for v1/v2 snapshots without scene field)",
    )
    args = parser.parse_args()

    snapshot_data = _load_snapshot_json(args.snapshot)
    llm_report = None
    if args.llm_report is not None:
        llm_report = json.loads(args.llm_report.read_text(encoding="utf-8"))

    report = _compose_report(
        args.snapshot, snapshot_data, llm_report, add_per_scene=not args.no_per_scene
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote decision report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
