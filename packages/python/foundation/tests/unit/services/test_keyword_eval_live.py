from __future__ import annotations

import os
from pathlib import Path

import pytest

from omni.foundation.services.keyword_eval import evaluate_keyword_backends_with_llm
from omni.foundation.services.llm.provider import get_llm_provider


@pytest.mark.slow
@pytest.mark.asyncio
async def test_keyword_backend_llm_live_duel() -> None:
    if os.getenv("OMNI_RUN_REAL_LLM_EVAL") != "1":
        pytest.skip("Set OMNI_RUN_REAL_LLM_EVAL=1 to run live LLM evaluation")

    provider = get_llm_provider()
    if not provider.is_available():
        pytest.skip("LLM provider is not available in current environment")

    snapshot = Path(
        "packages/rust/crates/omni-vector/tests/snapshots/"
        "test_keyword_backend_quality__keyword_backend_quality_scenarios_v2.snap"
    )
    report = await evaluate_keyword_backends_with_llm(
        snapshot_path=snapshot,
        max_queries=2,
    )
    assert report["queries_evaluated"] == 2
    assert len(report["llm_duel_details"]) == 2
