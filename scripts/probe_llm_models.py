#!/usr/bin/env python3
"""Probe model availability for current configured LLM provider."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from omni.foundation.services.llm.provider import get_llm_provider


async def _probe_one(model: str, timeout_seconds: int) -> dict:
    provider = get_llm_provider()
    if not provider.is_available():
        return {"model": model, "supported": False, "reason": "provider_unavailable"}
    try:
        resp = await provider.complete(
            system_prompt="Return ONLY: OK",
            user_query="OK",
            model=model,
            max_tokens=8,
            temperature=0,
            top_p=0,
            timeout=timeout_seconds,
        )
    except Exception as e:  # pragma: no cover - defensive
        return {"model": model, "supported": False, "reason": f"exception:{e}"}

    if resp.success and (resp.content or "").strip():
        return {"model": model, "supported": True, "reason": "ok"}
    reason = (resp.error or "empty_response").strip()
    return {"model": model, "supported": False, "reason": reason}


async def _run(models: list[str], timeout_seconds: int) -> dict:
    results = []
    for m in models:
        results.append(await _probe_one(m, timeout_seconds))
    supported = [r["model"] for r in results if r["supported"]]
    unsupported = [r for r in results if not r["supported"]]
    return {
        "models": models,
        "supported_models": supported,
        "unsupported_models": unsupported,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        type=str,
        required=True,
        help="Comma-separated model names to probe.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=15)
    parser.add_argument("--output", type=Path, default=Path("/tmp/llm-model-probe.json"))
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    payload = asyncio.run(_run(models, args.timeout_seconds))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote model probe report: {args.output}")
    print(f"Supported: {payload['supported_models']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
