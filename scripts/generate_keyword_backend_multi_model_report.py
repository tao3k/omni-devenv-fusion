#!/usr/bin/env python3
"""Generate markdown report from multi-model keyword backend eval JSON."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _build_markdown(data: dict[str, Any], source: Path) -> str:
    models: list[str] = data.get("models", [])
    evaluated_models: list[str] = data.get("evaluated_models", models)
    skipped_models: dict[str, str] = data.get("skipped_models", {})
    reports: dict[str, Any] = data.get("reports", {})
    best = data.get("best_model_by_reliability", "n/a")
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ")

    lines = [
        "# Keyword Backend Multi-Model Report",
        "",
        f"- Generated at: `{now}`",
        f"- Source JSON: `{source}`",
        f"- Snapshot: `{data.get('snapshot', '')}`",
        f"- Models: `{', '.join(models)}`",
        f"- Evaluated models: `{', '.join(evaluated_models)}`",
        f"- Best model by reliability: `{best}`",
        "",
        "## Per-Model Summary",
        "",
        "| Model | Queries | Tantivy Win Rate | Lance FTS Win Rate | Reliable Ratio | High-Conf | Fallback Usage |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model in models:
        if model not in reports:
            continue
        report = reports.get(model, {})
        summary = report.get("llm_duel_summary", {})
        queries = report.get("queries_evaluated", 0)
        lines.append(
            f"| {model} | {queries} | "
            f"{_to_float(summary.get('tantivy_win_rate')):.4f} | "
            f"{_to_float(summary.get('lance_fts_win_rate')):.4f} | "
            f"{_to_float(summary.get('reliable_ratio')):.4f} | "
            f"{int(_to_float(summary.get('high_confidence_samples')))} | "
            f"{_to_float(summary.get('fallback_usage_ratio')):.4f} |"
        )

    lines.extend(["", "## Recommendation", ""])
    if best == "n/a" or not models:
        lines.append("- No valid model result found.")
    else:
        lines.append(f"- Keep `{best}` as primary judge model for now.")
        lines.append(
            "- Keep offline IR metrics as primary replacement evidence when reliable ratio is low."
        )
        lines.append(
            "- Use fallback model only for parse-recovery, not for changing business verdict policy."
        )

    if skipped_models:
        lines.extend(
            [
                "",
                "## Skipped Models",
                "",
            ]
        )
        for m, reason in skipped_models.items():
            lines.append(f"- `{m}`: `{reason}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Path to multi-model eval JSON.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/testing/keyword-backend-multi-model-report.md"),
    )
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    md = _build_markdown(data, args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")
    print(f"Wrote multi-model report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
