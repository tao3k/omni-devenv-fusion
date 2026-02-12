#!/usr/bin/env python3
"""Run LLM-assisted keyword backend evaluation from rust snapshot."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from omni.foundation.services.keyword_eval import (
    evaluate_keyword_backends_multi_model,
    evaluate_keyword_backends_with_llm,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path(
            "packages/rust/crates/omni-vector/tests/snapshots/"
            "test_keyword_backend_quality__keyword_backend_quality_scenarios_v2.snap"
        ),
        help="Path to rust quality snapshot file.",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=None,
        help="Limit number of queries for quick runs.",
    )
    parser.add_argument(
        "--start-query-index",
        type=int,
        default=0,
        help="Start index in snapshot query list for batched evaluation.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Optional model override for LLM provider.",
    )
    parser.add_argument(
        "--fallback-model",
        type=str,
        default=None,
        help="Optional fallback model if primary model is not parseable.",
    )
    parser.add_argument(
        "--model-profile",
        type=str,
        default="balanced",
        help="Judge profile: balanced|strict|fast.",
    )
    parser.add_argument(
        "--multi-model",
        type=str,
        default=None,
        help="Comma-separated model list for multi-model evaluation.",
    )
    parser.add_argument(
        "--skip-unsupported-models",
        action="store_true",
        default=False,
        help="Probe each model once and skip models that fail probe.",
    )
    parser.add_argument(
        "--vote-rounds",
        type=int,
        default=3,
        help="Number of LLM voting rounds per query (odd number recommended).",
    )
    parser.add_argument(
        "--max-api-attempts-per-round",
        type=int,
        default=2,
        help="Bounded LLM API attempts per round (2 recommended for reliability).",
    )
    parser.add_argument(
        "--per-query-timeout-seconds",
        type=int,
        default=90,
        help="Timeout per query-round; timeout falls back to tie and continues.",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=int,
        default=30,
        help="Timeout for each underlying LLM API request.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output JSON path.",
    )
    return parser


async def _run(args: argparse.Namespace) -> dict:
    if args.multi_model:
        models = [m.strip() for m in args.multi_model.split(",") if m.strip()]
        return await evaluate_keyword_backends_multi_model(
            snapshot_path=args.snapshot,
            models=models,
            max_queries=args.max_queries,
            start_query_index=args.start_query_index,
            fallback_model=args.fallback_model,
            model_profile=args.model_profile,
            vote_rounds=args.vote_rounds,
            max_api_attempts_per_round=args.max_api_attempts_per_round,
            per_query_timeout_seconds=args.per_query_timeout_seconds,
            request_timeout_seconds=args.request_timeout_seconds,
            skip_unsupported_models=args.skip_unsupported_models,
        )
    return await evaluate_keyword_backends_with_llm(
        snapshot_path=args.snapshot,
        max_queries=args.max_queries,
        start_query_index=args.start_query_index,
        model=args.model,
        fallback_model=args.fallback_model,
        model_profile=args.model_profile,
        vote_rounds=args.vote_rounds,
        max_api_attempts_per_round=args.max_api_attempts_per_round,
        per_query_timeout_seconds=args.per_query_timeout_seconds,
        request_timeout_seconds=args.request_timeout_seconds,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    report = asyncio.run(_run(args))
    payload = json.dumps(report, ensure_ascii=False, indent=2)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote LLM eval report: {args.output}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
