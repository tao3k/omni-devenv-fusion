from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from omni.foundation.services import keyword_eval


class _FakeProvider:
    def is_available(self) -> bool:
        return True

    async def complete_async(
        self,
        system_prompt: str,
        user_query: str = "",
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        if "commit_flow" in user_query or "commit changes" in user_query:
            return (
                '{"winner":"tantivy","tantivy_score":88,'
                '"lance_fts_score":81,"explanation":"better top-2"}'
            )
        return '{"winner":"tie","tantivy_score":80,"lance_fts_score":80,"explanation":"comparable"}'

    def get_config(self):  # pragma: no cover - tiny shim
        class _Cfg:
            model = "fake-model"

        return _Cfg()


class _ToolCallProvider:
    def is_available(self) -> bool:
        return True

    async def complete(
        self,
        system_prompt: str,
        user_query: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ):
        return SimpleNamespace(
            success=True,
            tool_calls=[
                {
                    "name": "judge_keyword_duel",
                    "input": {
                        "winner": "tantivy",
                        "tantivy_score": 90,
                        "lance_fts_score": 60,
                        "confidence": 88,
                        "explanation": "tool-call verdict",
                    },
                }
            ],
            content="",
        )

    async def complete_async(self, *args, **kwargs) -> str:  # pragma: no cover - should not be used
        raise AssertionError(
            "complete_async should not be used when tool call verdict is available"
        )

    def get_config(self):  # pragma: no cover - tiny shim
        class _Cfg:
            model = "fake-model"

        return _Cfg()


class _ReformatProvider:
    def is_available(self) -> bool:
        return True

    async def complete(self, *args, **kwargs):  # pragma: no cover - force async fallback path
        raise RuntimeError("no tool call")

    async def complete_async(
        self,
        system_prompt: str,
        user_query: str = "",
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        if "Convert the following evaluator output" in user_query:
            return "VERDICT|winner=tantivy|tantivy=80|lance_fts=60|confidence=70|reason=reformatted"
        return "I think Tantivy is better overall but here is my analysis in paragraphs."

    def get_config(self):  # pragma: no cover
        class _Cfg:
            model = "fake-model"

        return _Cfg()


class _FallbackModelProvider:
    def is_available(self) -> bool:
        return True

    async def complete(self, *args, **kwargs):  # pragma: no cover
        raise RuntimeError("no tool call")

    async def complete_async(
        self,
        system_prompt: str,
        user_query: str = "",
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        if model == "backup-model":
            return (
                "VERDICT|winner=tantivy|tantivy=85|lance_fts=65|confidence=75|reason=fallback_model"
            )
        return "free text analysis without strict format"

    def get_config(self):  # pragma: no cover
        class _Cfg:
            model = "primary-model"

        return _Cfg()


class _ProbeProvider:
    def is_available(self) -> bool:
        return True

    async def complete(self, *args, **kwargs):  # pragma: no cover
        raise RuntimeError("no tool call")

    async def complete_async(self, *args, **kwargs) -> str:
        model = kwargs.get("model")
        user_query = kwargs.get("user_query", "")
        if user_query == "OK":
            return "" if model == "bad-model" else "OK"
        return "VERDICT|winner=tie|tantivy=0|lance_fts=0|confidence=80|reason=test"

    def get_config(self):  # pragma: no cover
        class _Cfg:
            model = "primary-model"

        return _Cfg()


@pytest.mark.asyncio
async def test_evaluate_keyword_backends_with_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = Path(
        "packages/rust/crates/omni-vector/tests/snapshots/"
        "test_keyword_backend_quality__keyword_backend_quality_scenarios_v2.snap"
    )
    monkeypatch.setattr(keyword_eval, "get_llm_provider", lambda: _FakeProvider())

    report = await keyword_eval.evaluate_keyword_backends_with_llm(
        snapshot_path=snapshot,
        max_queries=3,
    )

    assert report["queries_evaluated"] == 3
    summary = report["llm_duel_summary"]
    assert summary["tantivy_wins"] + summary["lance_fts_wins"] + summary["ties"] == 3
    assert "reliable_samples" in summary
    assert "reliable_ratio" in summary
    assert "high_confidence_samples" in summary
    assert "avg_vote_agreement" in summary
    assert "fallback_used_samples" in summary
    assert "fallback_usage_ratio" in summary
    assert len(report["llm_duel_details"]) == 3
    for item in report["llm_duel_details"]:
        assert "parse_status" in item
        assert "raw_output_excerpt" in item
        assert "votes" in item
        assert "vote_rounds" in item
        assert "confidence" in item
        assert "agreement_ratio" in item
        assert "reliable" in item
        assert "judge_model" in item
        assert "judge_models" in item
        assert "fallback_used" in item


@pytest.mark.asyncio
async def test_evaluate_keyword_backends_with_llm_tool_call_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = Path(
        "packages/rust/crates/omni-vector/tests/snapshots/"
        "test_keyword_backend_quality__keyword_backend_quality_scenarios_v2.snap"
    )
    monkeypatch.setattr(keyword_eval, "get_llm_provider", lambda: _ToolCallProvider())

    report = await keyword_eval.evaluate_keyword_backends_with_llm(
        snapshot_path=snapshot,
        max_queries=1,
        vote_rounds=3,
        max_api_attempts_per_round=1,
    )

    assert report["queries_evaluated"] == 1
    summary = report["llm_duel_summary"]
    assert summary["tantivy_wins"] == 1
    assert summary["lance_fts_wins"] == 0
    assert summary["reliable_samples"] == 1
    assert summary["reliable_ratio"] == 1.0

    detail = report["llm_duel_details"][0]
    assert detail["parse_status"] == "tool_call_ok"
    assert detail["winner"] == "tantivy"
    assert detail["reliable"] is True
    assert detail["confidence"] >= 80.0


def test_extract_structured_verdict_line_format() -> None:
    verdict = (
        "analysis...\n"
        "VERDICT|winner=tantivy|tantivy=91|lance_fts=66|confidence=82|reason=better intent coverage\n"
    )
    parsed = keyword_eval._extract_structured_verdict(verdict)
    assert parsed["winner"] == "tantivy"
    assert parsed["tantivy_score"] == 91.0
    assert parsed["lance_fts_score"] == 66.0
    assert parsed["confidence"] == 82.0


@pytest.mark.asyncio
async def test_evaluate_keyword_backends_with_llm_reformat_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = Path(
        "packages/rust/crates/omni-vector/tests/snapshots/"
        "test_keyword_backend_quality__keyword_backend_quality_scenarios_v2.snap"
    )
    monkeypatch.setattr(keyword_eval, "get_llm_provider", lambda: _ReformatProvider())
    report = await keyword_eval.evaluate_keyword_backends_with_llm(
        snapshot_path=snapshot,
        max_queries=1,
        vote_rounds=1,
        max_api_attempts_per_round=3,
    )
    detail = report["llm_duel_details"][0]
    assert detail["parse_status"] == "structured_reformat_ok"
    assert detail["winner"] == "tantivy"
    assert detail["reliable"] is True


@pytest.mark.asyncio
async def test_evaluate_keyword_backends_with_llm_fallback_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = Path(
        "packages/rust/crates/omni-vector/tests/snapshots/"
        "test_keyword_backend_quality__keyword_backend_quality_scenarios_v2.snap"
    )
    monkeypatch.setattr(keyword_eval, "get_llm_provider", lambda: _FallbackModelProvider())
    report = await keyword_eval.evaluate_keyword_backends_with_llm(
        snapshot_path=snapshot,
        max_queries=1,
        vote_rounds=1,
        model="primary-model",
        fallback_model="backup-model",
        max_api_attempts_per_round=1,
    )
    detail = report["llm_duel_details"][0]
    assert detail["winner"] == "tantivy"
    assert detail["judge_model"] == "backup-model"
    assert detail["reliable"] is True
    assert detail["fallback_used"] is True


@pytest.mark.asyncio
async def test_evaluate_keyword_backends_multi_model(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = Path(
        "packages/rust/crates/omni-vector/tests/snapshots/"
        "test_keyword_backend_quality__keyword_backend_quality_scenarios_v2.snap"
    )
    monkeypatch.setattr(keyword_eval, "get_llm_provider", lambda: _FallbackModelProvider())
    report = await keyword_eval.evaluate_keyword_backends_multi_model(
        snapshot_path=snapshot,
        models=["primary-model", "backup-model"],
        max_queries=1,
        vote_rounds=1,
        max_api_attempts_per_round=1,
    )
    assert report["best_model_by_reliability"] in {"primary-model", "backup-model"}
    assert set(report["reports"]) == {"primary-model", "backup-model"}


@pytest.mark.asyncio
async def test_evaluate_keyword_backends_multi_model_skip_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = Path(
        "packages/rust/crates/omni-vector/tests/snapshots/"
        "test_keyword_backend_quality__keyword_backend_quality_scenarios_v2.snap"
    )
    monkeypatch.setattr(keyword_eval, "get_llm_provider", lambda: _ProbeProvider())
    report = await keyword_eval.evaluate_keyword_backends_multi_model(
        snapshot_path=snapshot,
        models=["good-model", "bad-model"],
        max_queries=1,
        vote_rounds=1,
        max_api_attempts_per_round=1,
        skip_unsupported_models=True,
    )
    assert report["evaluated_models"] == ["good-model"]
    assert "bad-model" in report["skipped_models"]
