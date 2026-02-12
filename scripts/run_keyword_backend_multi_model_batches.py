#!/usr/bin/env python3
"""Run batched multi-model keyword eval and produce merged JSON summary."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from omni.foundation.services.keyword_eval import evaluate_keyword_backends_multi_model


def _merge_model_reports(batch_reports: list[dict[str, Any]]) -> dict[str, Any]:
    per_model_details: dict[str, list[dict[str, Any]]] = {}
    skipped: dict[str, str] = {}
    models: list[str] = []
    snapshot = ""
    for report in batch_reports:
        snapshot = report.get("snapshot", snapshot)
        for m in report.get("models", []):
            if m not in models:
                models.append(m)
        skipped.update(report.get("skipped_models", {}))
        for m, model_report in report.get("reports", {}).items():
            per_model_details.setdefault(m, [])
            per_model_details[m].extend(model_report.get("llm_duel_details", []))

    merged_reports: dict[str, Any] = {}
    reliability: dict[str, float] = {}
    for model, details in per_model_details.items():
        total = len(details)
        tantivy_wins = sum(1 for d in details if d.get("winner") == "tantivy")
        fts_wins = sum(1 for d in details if d.get("winner") == "lance_fts")
        ties = sum(1 for d in details if d.get("winner") == "tie")
        reliable = sum(1 for d in details if d.get("reliable"))
        high_conf = sum(1 for d in details if float(d.get("confidence", 0.0)) >= 70.0)
        fallback = sum(1 for d in details if d.get("fallback_used"))
        summary = {
            "tantivy_wins": tantivy_wins,
            "lance_fts_wins": fts_wins,
            "ties": ties,
            "tantivy_win_rate": (tantivy_wins / total) if total else 0.0,
            "lance_fts_win_rate": (fts_wins / total) if total else 0.0,
            "reliable_samples": reliable,
            "reliable_ratio": (reliable / total) if total else 0.0,
            "high_confidence_samples": high_conf,
            "fallback_used_samples": fallback,
            "fallback_usage_ratio": (fallback / total) if total else 0.0,
        }
        reliability[model] = summary["reliable_ratio"]
        merged_reports[model] = {
            "queries_evaluated": total,
            "llm_duel_summary": summary,
            "llm_duel_details": details,
        }

    best = max(reliability, key=reliability.get) if reliability else None
    return {
        "snapshot": snapshot,
        "models": models,
        "evaluated_models": list(merged_reports.keys()),
        "skipped_models": skipped,
        "best_model_by_reliability": best,
        "model_reliability": reliability,
        "reports": merged_reports,
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    batch_reports: list[dict[str, Any]] = []
    for i in range(args.num_batches):
        start = args.start_query_index + i * args.batch_size
        report = await evaluate_keyword_backends_multi_model(
            snapshot_path=args.snapshot,
            models=models,
            max_queries=args.batch_size,
            start_query_index=start,
            fallback_model=args.fallback_model,
            model_profile=args.model_profile,
            vote_rounds=args.vote_rounds,
            max_api_attempts_per_round=args.max_api_attempts_per_round,
            per_query_timeout_seconds=args.per_query_timeout_seconds,
            request_timeout_seconds=args.request_timeout_seconds,
            skip_unsupported_models=args.skip_unsupported_models,
        )
        batch_reports.append(report)
    merged = _merge_model_reports(batch_reports)
    merged["batching"] = {
        "num_batches": args.num_batches,
        "batch_size": args.batch_size,
        "start_query_index": args.start_query_index,
    }
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--models", type=str, required=True)
    parser.add_argument("--fallback-model", type=str, default=None)
    parser.add_argument("--model-profile", type=str, default="balanced")
    parser.add_argument("--vote-rounds", type=int, default=1)
    parser.add_argument("--max-api-attempts-per-round", type=int, default=2)
    parser.add_argument("--per-query-timeout-seconds", type=int, default=30)
    parser.add_argument("--request-timeout-seconds", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--num-batches", type=int, default=4)
    parser.add_argument("--start-query-index", type=int, default=0)
    parser.add_argument("--skip-unsupported-models", action="store_true", default=False)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/keyword-llm-eval-multi-batched.json")
    )
    args = parser.parse_args()

    result = asyncio.run(_run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote batched multi-model report: {args.output}")
    print(f"Best model by reliability: {result.get('best_model_by_reliability')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
