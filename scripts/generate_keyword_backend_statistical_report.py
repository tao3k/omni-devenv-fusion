#!/usr/bin/env python3
"""Generate statistical evidence report for keyword backend replacement decision."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from math import comb
from pathlib import Path
from typing import Any


def _load_snapshot(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("\n---\n")
    if len(parts) < 2:
        raise ValueError(f"Invalid snapshot format: {path}")
    return json.loads(parts[-1].strip())


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


@dataclass
class MetricStats:
    wins: int
    losses: int
    ties: int
    mean_delta: float
    ci_low: float
    ci_high: float
    sign_p: float


def _sign_test_p_value(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    tail = sum(comb(n, i) * (0.5**n) for i in range(k + 1))
    return min(1.0, 2.0 * tail)


def _bootstrap_ci(
    values: list[float], reps: int = 4000, alpha: float = 0.05
) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    n = len(values)
    means: list[float] = []
    for _ in range(reps):
        sample = [values[random.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = int((alpha / 2.0) * reps)
    hi_idx = int((1.0 - alpha / 2.0) * reps) - 1
    return (sum(values) / n, means[lo_idx], means[hi_idx])


def _collect_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    t_rows = {row["query"]: row for row in snapshot.get("tantivy_details", [])}
    f_rows = {row["query"]: row for row in snapshot.get("lance_fts_details", [])}
    merged: list[dict[str, Any]] = []
    for query, t in t_rows.items():
        f = f_rows.get(query, {})
        merged.append(
            {
                "query": query,
                "scene": t.get("scene", "unknown"),
                "text": t.get("text", ""),
                "tantivy": t,
                "lance_fts": f,
            }
        )
    return merged


def _metric_stats(rows: list[dict[str, Any]], metric: str) -> MetricStats:
    deltas: list[float] = []
    wins = losses = ties = 0
    for row in rows:
        t = _to_float(row["tantivy"].get(metric))
        f = _to_float(row["lance_fts"].get(metric))
        d = t - f
        deltas.append(d)
        if d > 1e-9:
            wins += 1
        elif d < -1e-9:
            losses += 1
        else:
            ties += 1
    mean_delta, ci_low, ci_high = _bootstrap_ci(deltas)
    return MetricStats(
        wins=wins,
        losses=losses,
        ties=ties,
        mean_delta=mean_delta,
        ci_low=ci_low,
        ci_high=ci_high,
        sign_p=_sign_test_p_value(wins, losses),
    )


def _scene_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_scene: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_scene.setdefault(row["scene"], []).append(row)

    result: list[dict[str, Any]] = []
    for scene in sorted(by_scene):
        items = by_scene[scene]
        p = _metric_stats(items, "p_at_5")
        r = _metric_stats(items, "r_at_5")
        n = _metric_stats(items, "ndcg_at_5")
        result.append(
            {
                "scene": scene,
                "queries": len(items),
                "delta_p_at_5": p.mean_delta,
                "delta_r_at_5": r.mean_delta,
                "delta_ndcg_at_5": n.mean_delta,
                "winner": (
                    "tantivy"
                    if (p.mean_delta >= 0 and r.mean_delta >= 0 and n.mean_delta >= -0.01)
                    else "lance_fts"
                    if (p.mean_delta <= 0 and r.mean_delta <= 0 and n.mean_delta > 0.01)
                    else "split"
                ),
            }
        )
    return result


def _build_report(snapshot_path: Path, data: dict[str, Any]) -> str:
    rows = _collect_rows(data)
    p = _metric_stats(rows, "p_at_5")
    r = _metric_stats(rows, "r_at_5")
    n = _metric_stats(rows, "ndcg_at_5")
    scenes = _scene_summary(rows)
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ")

    lines = [
        "# Keyword Backend Statistical Report",
        "",
        f"- Generated at: `{now}`",
        f"- Snapshot: `{snapshot_path}`",
        f"- Query count: `{len(rows)}`",
        "",
        "## Global Statistics (Tantivy - Lance FTS)",
        "",
        "| Metric | Win/Loss/Tie | Mean Delta | 95% CI | Sign-Test p |",
        "|---|---:|---:|---:|---:|",
        f"| P@5 | {p.wins}/{p.losses}/{p.ties} | {p.mean_delta:+.4f} | [{p.ci_low:+.4f}, {p.ci_high:+.4f}] | {p.sign_p:.4f} |",
        f"| R@5 | {r.wins}/{r.losses}/{r.ties} | {r.mean_delta:+.4f} | [{r.ci_low:+.4f}, {r.ci_high:+.4f}] | {r.sign_p:.4f} |",
        f"| nDCG@5 | {n.wins}/{n.losses}/{n.ties} | {n.mean_delta:+.4f} | [{n.ci_low:+.4f}, {n.ci_high:+.4f}] | {n.sign_p:.4f} |",
        "",
        "## Scene Boundaries",
        "",
        "| Scene | Queries | ΔP@5 | ΔR@5 | ΔnDCG@5 | Policy Winner |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for s in scenes:
        lines.append(
            f"| {s['scene']} | {s['queries']} | {s['delta_p_at_5']:+.4f} | {s['delta_r_at_5']:+.4f} | {s['delta_ndcg_at_5']:+.4f} | {s['winner']} |"
        )

    default_policy = "Tantivy"
    if p.mean_delta < -0.01 and r.mean_delta < -0.01 and n.mean_delta < -0.01:
        default_policy = "Lance FTS"
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Default backend: `{default_policy}`",
            "- Use scene winner for overrides where `Policy Winner` is not the default.",
            "- Do not perform global replacement unless all global metrics are consistently superior with non-overlapping practical CI margin.",
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
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/testing/keyword-backend-statistical-report.md"),
    )
    args = parser.parse_args()

    data = _load_snapshot(args.snapshot)
    report = _build_report(args.snapshot, data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote statistical report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
