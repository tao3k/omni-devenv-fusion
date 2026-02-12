"""LLM-assisted evaluation for keyword backend quality snapshots."""

from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Any

from omni.foundation.services.llm.provider import get_llm_provider


@dataclass
class QueryDuelResult:
    """Per-query LLM comparison between two backend hit lists."""

    query: str
    winner: str
    tantivy_score: float
    lance_fts_score: float
    explanation: str
    parse_status: str
    raw_output_excerpt: str
    votes: dict[str, int]
    vote_rounds: int
    confidence: float
    agreement_ratio: float
    reliable: bool
    judge_model: str
    judge_models: list[str]
    fallback_used: bool


@dataclass(frozen=True)
class JudgeProfile:
    name: str
    max_api_attempts_per_round: int
    per_query_timeout_seconds: int
    prefer_tool_call: bool = True


DEFAULT_JUDGE_PROFILES: dict[str, JudgeProfile] = {
    "balanced": JudgeProfile(
        name="balanced",
        max_api_attempts_per_round=2,
        per_query_timeout_seconds=90,
    ),
    "strict": JudgeProfile(
        name="strict",
        max_api_attempts_per_round=3,
        per_query_timeout_seconds=120,
    ),
    "fast": JudgeProfile(
        name="fast",
        max_api_attempts_per_round=1,
        per_query_timeout_seconds=45,
    ),
}


def _resolve_profile(name: str | None) -> JudgeProfile:
    if not name:
        return DEFAULT_JUDGE_PROFILES["balanced"]
    return DEFAULT_JUDGE_PROFILES.get(name, DEFAULT_JUDGE_PROFILES["balanced"])


def _extract_snapshot_json(snapshot_path: Path) -> dict[str, Any]:
    """Parse an insta snapshot file and return the JSON payload."""
    text = snapshot_path.read_text(encoding="utf-8")
    sections = text.split("\n---\n")
    if len(sections) < 2:
        raise ValueError(f"Invalid snapshot format: {snapshot_path}")
    payload = sections[-1].strip()
    return json.loads(payload)


def _extract_json_block(content: str) -> dict[str, Any]:
    """Extract JSON object from plain text or fenced code block."""
    raw = content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output")
    return json.loads(raw[start : end + 1])


def _build_duel_prompt(query_text: str, tantivy_hits: list[str], lance_hits: list[str]) -> str:
    return (
        "Task: judge retrieval quality for a user query.\n"
        "Compare two ranked result lists. Favor semantic relevance and ranking quality.\n"
        "At the end, output EXACTLY one line in this format:\n"
        "VERDICT|winner=<tantivy|lance_fts|tie>|tantivy=<0-100>|lance_fts=<0-100>|confidence=<0-100>|reason=<short>\n"
        "You may think internally, but final answer must include that single VERDICT line.\n"
        "Alternative accepted format:\n"
        "BEGIN_VERDICT\n"
        "winner=tantivy|lance_fts|tie\n"
        "tantivy_score=0-100\n"
        "lance_fts_score=0-100\n"
        "confidence=0-100\n"
        "reason=short\n"
        "END_VERDICT\n\n"
        f"Query: {query_text}\n"
        f"Tantivy Top Hits: {tantivy_hits}\n"
        f"Lance FTS Top Hits: {lance_hits}\n"
    )


def _build_strict_json_retry_prompt(
    query_text: str, tantivy_hits: list[str], lance_hits: list[str]
) -> str:
    return (
        "Return only ONE line:\n"
        "VERDICT|winner=<tantivy|lance_fts|tie>|tantivy=<0-100>|lance_fts=<0-100>|confidence=<0-100>|reason=<short>\n"
        "No markdown, no extra text.\n"
        "Alternative accepted block:\n"
        "BEGIN_VERDICT\n"
        "winner=tantivy|lance_fts|tie\n"
        "tantivy_score=0-100\n"
        "lance_fts_score=0-100\n"
        "confidence=0-100\n"
        "reason=short\n"
        "END_VERDICT\n"
        f'Query: "{query_text}"\n'
        f"Tantivy Top Hits: {tantivy_hits}\n"
        f"Lance FTS Top Hits: {lance_hits}\n"
    )


def _build_reformat_prompt(raw_output: str) -> str:
    return (
        "Convert the following evaluator output into EXACTLY one line:\n"
        "VERDICT|winner=<tantivy|lance_fts|tie>|tantivy=<0-100>|lance_fts=<0-100>|confidence=<0-100>|reason=<short>\n"
        "Rules:\n"
        "- If winner is unclear, use tie.\n"
        "- If scores are missing, use 0.\n"
        "- Output one line only, no markdown.\n\n"
        "Input:\n"
        f"{raw_output}"
    )


def _clamp_score(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _extract_structured_verdict(content: str) -> dict[str, Any]:
    """Extract key=value verdict block from model output."""
    text = content.strip()

    line_match = re.search(
        r"VERDICT\|winner=(tantivy|lance_fts|tie)\|tantivy=([0-9]+(?:\.[0-9]+)?)\|lance_fts=([0-9]+(?:\.[0-9]+)?)\|confidence=([0-9]+(?:\.[0-9]+)?)\|reason=(.+)",
        text,
        flags=re.IGNORECASE,
    )
    if line_match:
        return {
            "winner": line_match.group(1).lower(),
            "tantivy_score": _clamp_score(float(line_match.group(2))),
            "lance_fts_score": _clamp_score(float(line_match.group(3))),
            "confidence": _clamp_score(float(line_match.group(4))),
            "explanation": line_match.group(5).strip() or "verdict_line",
        }

    match = re.search(r"BEGIN_VERDICT(.*?)END_VERDICT", text, flags=re.DOTALL | re.IGNORECASE)
    block = match.group(1) if match else text

    def _extract(pattern: str, default: str = "") -> str:
        m = re.search(pattern, block, flags=re.IGNORECASE)
        return m.group(1).strip() if m else default

    winner = _extract(r"winner\s*=\s*(tantivy|lance_fts|tie)")
    if winner not in {"tantivy", "lance_fts", "tie"}:
        raise ValueError("winner not found in structured verdict")

    tantivy_score = float(_extract(r"tantivy_score\s*=\s*(-?\d+(?:\.\d+)?)", "0"))
    lance_score = float(_extract(r"lance_fts_score\s*=\s*(-?\d+(?:\.\d+)?)", "0"))
    confidence = float(_extract(r"confidence\s*=\s*(-?\d+(?:\.\d+)?)", "0"))
    reason = _extract(r"reason\s*=\s*(.+)", "")

    return {
        "winner": winner,
        "tantivy_score": _clamp_score(tantivy_score),
        "lance_fts_score": _clamp_score(lance_score),
        "confidence": _clamp_score(confidence),
        "explanation": reason or "structured_verdict",
    }


def _coerce_duel_from_text(content: str) -> dict[str, Any] | None:
    """Best-effort extraction when the model doesn't return strict JSON."""
    lowered = content.lower()
    winner = None
    if "winner" in lowered:
        if "tantivy" in lowered and "lance" not in lowered:
            winner = "tantivy"
        elif "lance_fts" in lowered or ("lance" in lowered and "tantivy" not in lowered):
            winner = "lance_fts"
        elif "tie" in lowered:
            winner = "tie"
    if winner is None:
        # Weak fallback based on comparative language.
        if "tantivy" in lowered and any(
            token in lowered for token in ["better", "stronger", "wins", "preferred"]
        ):
            winner = "tantivy"
        elif "lance" in lowered and any(
            token in lowered for token in ["better", "stronger", "wins", "preferred"]
        ):
            winner = "lance_fts"
        else:
            winner = "tie"

    score_pairs = re.findall(r"(tantivy|lance[_ ]?fts)[^0-9]{0,20}(\d{1,3})", lowered)
    tantivy_score = 0.0
    lance_score = 0.0
    for name, score_text in score_pairs:
        score = float(score_text)
        if "tantivy" in name:
            tantivy_score = score
        else:
            lance_score = score

    return {
        "winner": winner,
        "tantivy_score": tantivy_score,
        "lance_fts_score": lance_score,
        "confidence": 20.0,
        "explanation": "coerced_from_non_json",
    }


def _extract_hits_from_row(row: dict[str, Any]) -> list[str]:
    """Support both old (hits) and new (top1/matched_relevant) snapshot schemas."""
    hits = row.get("hits")
    if isinstance(hits, list):
        return [str(x) for x in hits]

    top1 = row.get("top1")
    matched = row.get("matched_relevant", [])
    out: list[str] = []
    if isinstance(top1, str) and top1:
        out.append(top1)
    if isinstance(matched, list):
        for item in matched:
            s = str(item)
            if s and s not in out:
                out.append(s)
    return out


def _judge_tool_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "judge_keyword_duel",
                "description": "Judge retrieval quality between Tantivy and Lance FTS result lists.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "winner": {
                            "type": "string",
                            "enum": ["tantivy", "lance_fts", "tie"],
                        },
                        "tantivy_score": {"type": "number", "minimum": 0, "maximum": 100},
                        "lance_fts_score": {"type": "number", "minimum": 0, "maximum": 100},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                        "explanation": {"type": "string"},
                    },
                    "required": [
                        "winner",
                        "tantivy_score",
                        "lance_fts_score",
                        "confidence",
                        "explanation",
                    ],
                    "additionalProperties": False,
                },
            },
        }
    ]


def _normalize_tool_verdict(payload: dict[str, Any]) -> dict[str, Any]:
    winner = str(payload.get("winner", "tie"))
    if winner not in {"tantivy", "lance_fts", "tie"}:
        winner = "tie"
    return {
        "winner": winner,
        "tantivy_score": _clamp_score(float(payload.get("tantivy_score", 0.0))),
        "lance_fts_score": _clamp_score(float(payload.get("lance_fts_score", 0.0))),
        "confidence": _clamp_score(float(payload.get("confidence", 0.0))),
        "explanation": str(payload.get("explanation", "tool_call_verdict")),
    }


async def _judge_with_tool_call(
    provider: Any,
    *,
    system_prompt: str,
    query_text: str,
    tantivy_hits: list[str],
    lance_hits: list[str],
    model: str | None,
) -> tuple[dict[str, Any], str, str] | None:
    if not hasattr(provider, "complete"):
        return None
    prompt = _build_duel_prompt(query_text, tantivy_hits, lance_hits)
    try:
        response = await provider.complete(
            system_prompt=system_prompt,
            user_query=prompt,
            model=model,
            max_tokens=220,
            tools=_judge_tool_schema(),
            tool_choice={"type": "function", "function": {"name": "judge_keyword_duel"}},
        )
    except Exception:
        return None
    if not getattr(response, "success", False):
        return None

    tool_calls = getattr(response, "tool_calls", None) or []
    for call in tool_calls:
        if str(call.get("name", "")) != "judge_keyword_duel":
            continue
        payload = call.get("input")
        if isinstance(payload, dict):
            try:
                normalized = _normalize_tool_verdict(payload)
                excerpt = json.dumps(normalized, ensure_ascii=False)[:240]
                return normalized, "tool_call_ok", excerpt
            except Exception:
                continue
    return None


async def _judge_with_fallback_models(
    provider: Any,
    *,
    system_prompt: str,
    query_text: str,
    tantivy_hits: list[str],
    lance_hits: list[str],
    primary_model: str | None,
    fallback_model: str | None,
    max_api_attempts: int,
    request_timeout_seconds: int,
) -> tuple[dict[str, Any], str, str, str]:
    candidates = [primary_model]
    if fallback_model and fallback_model != primary_model:
        candidates.append(fallback_model)
    if not candidates:
        candidates = [None]

    last = (
        {
            "winner": "tie",
            "tantivy_score": 0.0,
            "lance_fts_score": 0.0,
            "confidence": 0.0,
            "explanation": "fallback_empty",
        },
        "parse_failed_fallback",
        "",
        "",
    )
    for m in candidates:
        parsed, status, excerpt = await _judge_once(
            provider,
            system_prompt=system_prompt,
            query_text=query_text,
            tantivy_hits=tantivy_hits,
            lance_hits=lance_hits,
            model=m,
            max_api_attempts=max_api_attempts,
            request_timeout_seconds=request_timeout_seconds,
        )
        model_name = m or "default"
        if status not in {"coerced_non_json", "parse_failed_fallback", "timeout_fallback"}:
            return parsed, status, excerpt, model_name
        last = (parsed, status, excerpt, model_name)
    return last


async def _judge_once(
    provider: Any,
    *,
    system_prompt: str,
    query_text: str,
    tantivy_hits: list[str],
    lance_hits: list[str],
    model: str | None,
    max_api_attempts: int = 1,
    request_timeout_seconds: int = 30,
) -> tuple[dict[str, Any], str, str]:
    """Run one LLM judgment round with bounded API attempts."""
    tool_result = await _judge_with_tool_call(
        provider,
        system_prompt=system_prompt,
        query_text=query_text,
        tantivy_hits=tantivy_hits,
        lance_hits=lance_hits,
        model=model,
    )
    if tool_result is not None:
        return tool_result

    attempts = max(1, int(max_api_attempts))
    prompts = [
        _build_duel_prompt(query_text, tantivy_hits, lance_hits),
        _build_strict_json_retry_prompt(query_text, tantivy_hits, lance_hits),
    ]
    max_tokens_for_attempt = [320, 120]
    last_output = ""

    for idx in range(attempts):
        if idx < len(prompts):
            prompt = prompts[idx]
            max_tokens = max_tokens_for_attempt[idx]
        else:
            prompt = _build_reformat_prompt(last_output)
            max_tokens = 120

        content = await provider.complete_async(
            system_prompt=system_prompt,
            user_query=prompt,
            model=model,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            temperature=0,
            top_p=0,
            timeout=max(5, int(request_timeout_seconds)),
        )
        last_output = content
        try:
            status = (
                "structured_ok"
                if idx == 0
                else "structured_retry_ok"
                if idx == 1
                else "structured_reformat_ok"
            )
            return _extract_structured_verdict(content), status, content[:240]
        except Exception:
            try:
                parsed = _extract_json_block(content)
                parsed.setdefault("confidence", 50.0 - (idx * 8.0))
                status = "json_ok" if idx == 0 else "json_retry_ok"
                return parsed, status, content[:240]
            except Exception:
                continue

    coerced = _coerce_duel_from_text(last_output)
    if coerced is not None:
        return coerced, "coerced_non_json", last_output[:240]
    return (
        {
            "winner": "tie",
            "tantivy_score": 0,
            "lance_fts_score": 0,
            "confidence": 0,
            "explanation": "llm_parse_failed",
        },
        "parse_failed_fallback",
        last_output[:240],
    )


async def evaluate_keyword_backends_with_llm(
    snapshot_path: str | Path,
    max_queries: int | None = None,
    start_query_index: int = 0,
    model: str | None = None,
    fallback_model: str | None = None,
    model_profile: str | None = None,
    vote_rounds: int = 3,
    max_api_attempts_per_round: int | None = None,
    per_query_timeout_seconds: int | None = None,
    request_timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Run LLM-based duel evaluation over rust snapshot details."""
    path = Path(snapshot_path)
    data = _extract_snapshot_json(path)

    provider = get_llm_provider()
    if not provider.is_available():
        raise RuntimeError("LLM provider is not available (missing API key/config)")

    tantivy_rows = data.get("tantivy_details", [])
    fts_rows = data.get("lance_fts_details", [])
    fts_by_query = {row["query"]: row for row in fts_rows}

    start = max(0, int(start_query_index))
    if start > 0:
        tantivy_rows = tantivy_rows[start:]
    if max_queries is not None:
        tantivy_rows = tantivy_rows[:max_queries]
    profile = _resolve_profile(model_profile)
    attempts = (
        int(max_api_attempts_per_round)
        if max_api_attempts_per_round is not None
        else profile.max_api_attempts_per_round
    )
    timeout_seconds = (
        int(per_query_timeout_seconds)
        if per_query_timeout_seconds is not None
        else profile.per_query_timeout_seconds
    )

    system_prompt = (
        "You are an impartial IR evaluator. "
        "Evaluate relevance and ranking quality. Follow output contract exactly."
    )
    duel_results: list[QueryDuelResult] = []

    for row in tantivy_rows:
        query_name = row["query"]
        query_text = row["text"]
        tantivy_hits = _extract_hits_from_row(row)
        lance_hits = _extract_hits_from_row(fts_by_query.get(query_name, {}))

        rounds = max(1, int(vote_rounds))
        winners: list[str] = []
        tantivy_scores: list[float] = []
        lance_scores: list[float] = []
        parse_statuses: list[str] = []
        explanations: list[str] = []
        excerpts: list[str] = []
        confidences: list[float] = []
        judge_models_rounds: list[str] = []

        for _ in range(rounds):
            try:
                parsed, parse_status, raw_excerpt, judge_model = await asyncio.wait_for(
                    _judge_with_fallback_models(
                        provider,
                        system_prompt=system_prompt,
                        query_text=query_text,
                        tantivy_hits=tantivy_hits,
                        lance_hits=lance_hits,
                        primary_model=model,
                        fallback_model=fallback_model,
                        max_api_attempts=attempts,
                        request_timeout_seconds=request_timeout_seconds,
                    ),
                    timeout=max(1, timeout_seconds),
                )
            except TimeoutError:
                parsed = {
                    "winner": "tie",
                    "tantivy_score": 0.0,
                    "lance_fts_score": 0.0,
                    "confidence": 0.0,
                    "explanation": "llm_timeout",
                }
                parse_status = "timeout_fallback"
                raw_excerpt = ""
                judge_model = fallback_model or model or "default"
            winners.append(str(parsed.get("winner", "tie")))
            tantivy_scores.append(float(parsed.get("tantivy_score", 0.0)))
            lance_scores.append(float(parsed.get("lance_fts_score", 0.0)))
            parse_statuses.append(parse_status)
            explanations.append(str(parsed.get("explanation", "")))
            excerpts.append(raw_excerpt)
            confidences.append(_clamp_score(float(parsed.get("confidence", 0.0))))
            judge_models_rounds.append(judge_model)

        winner_counter = Counter(winners)
        winner = winner_counter.most_common(1)[0][0] if winner_counter else "tie"
        votes = {k: int(v) for k, v in winner_counter.items()}
        agreement_ratio = winner_counter.get(winner, 0) / rounds if rounds > 0 else 0.0
        parseable_rounds = sum(
            1
            for status in parse_statuses
            if status
            in {
                "tool_call_ok",
                "structured_ok",
                "structured_retry_ok",
                "structured_reformat_ok",
                "json_ok",
                "json_retry_ok",
            }
        )
        primary_status = (
            Counter(parse_statuses).most_common(1)[0][0]
            if parse_statuses
            else "parse_failed_fallback"
        )
        parsed = {
            "winner": winner,
            "tantivy_score": (sum(tantivy_scores) / len(tantivy_scores)) if tantivy_scores else 0.0,
            "lance_fts_score": (sum(lance_scores) / len(lance_scores)) if lance_scores else 0.0,
            "confidence": (sum(confidences) / len(confidences)) if confidences else 0.0,
            "explanation": explanations[0] if explanations else "",
        }
        parse_status = primary_status
        raw_output_excerpt = excerpts[0] if excerpts else ""
        judge_model = judge_models_rounds[0] if judge_models_rounds else (model or "default")
        fallback_used = any(
            jm != (model or provider.get_config().model or "default") for jm in judge_models_rounds
        )
        reliable = (
            parseable_rounds >= ceil(rounds * 0.67)
            and agreement_ratio >= 0.67
            and float(parsed.get("confidence", 0.0)) >= 55.0
        )

        duel_results.append(
            QueryDuelResult(
                query=query_name,
                winner=str(parsed.get("winner", "tie")),
                tantivy_score=float(parsed.get("tantivy_score", 0.0)),
                lance_fts_score=float(parsed.get("lance_fts_score", 0.0)),
                explanation=str(parsed.get("explanation", "")),
                parse_status=parse_status,
                raw_output_excerpt=raw_output_excerpt,
                votes=votes,
                vote_rounds=rounds,
                confidence=float(parsed.get("confidence", 0.0)),
                agreement_ratio=agreement_ratio,
                reliable=reliable,
                judge_model=judge_model,
                judge_models=judge_models_rounds,
                fallback_used=fallback_used,
            )
        )

    total = len(duel_results)
    tantivy_wins = sum(1 for r in duel_results if r.winner == "tantivy")
    fts_wins = sum(1 for r in duel_results if r.winner == "lance_fts")
    ties = sum(1 for r in duel_results if r.winner == "tie")
    reliable_count = sum(1 for r in duel_results if r.reliable)
    high_confidence_count = sum(1 for r in duel_results if r.confidence >= 70.0)
    avg_vote_agreement = (sum(r.agreement_ratio for r in duel_results) / total) if total else 0.0
    fallback_count = sum(1 for r in duel_results if r.fallback_used)

    return {
        "snapshot": str(path),
        "queries_evaluated": total,
        "llm_model": model or provider.get_config().model,
        "offline_summary": data.get("summary", {}),
        "judge_profile": profile.name,
        "primary_model": model or provider.get_config().model,
        "fallback_model": fallback_model,
        "llm_duel_summary": {
            "tantivy_wins": tantivy_wins,
            "lance_fts_wins": fts_wins,
            "ties": ties,
            "tantivy_win_rate": (tantivy_wins / total) if total else 0.0,
            "lance_fts_win_rate": (fts_wins / total) if total else 0.0,
            "reliable_samples": reliable_count,
            "reliable_ratio": (reliable_count / total) if total else 0.0,
            "high_confidence_samples": high_confidence_count,
            "avg_vote_agreement": avg_vote_agreement,
            "fallback_used_samples": fallback_count,
            "fallback_usage_ratio": (fallback_count / total) if total else 0.0,
        },
        "llm_duel_details": [
            {
                "query": r.query,
                "winner": r.winner,
                "tantivy_score": r.tantivy_score,
                "lance_fts_score": r.lance_fts_score,
                "explanation": r.explanation,
                "parse_status": r.parse_status,
                "raw_output_excerpt": r.raw_output_excerpt,
                "votes": r.votes,
                "vote_rounds": r.vote_rounds,
                "confidence": r.confidence,
                "agreement_ratio": r.agreement_ratio,
                "reliable": r.reliable,
                "judge_model": r.judge_model,
                "judge_models": r.judge_models,
                "fallback_used": r.fallback_used,
            }
            for r in duel_results
        ],
    }


async def evaluate_keyword_backends_multi_model(
    snapshot_path: str | Path,
    models: list[str],
    *,
    max_queries: int | None = None,
    start_query_index: int = 0,
    fallback_model: str | None = None,
    model_profile: str | None = None,
    vote_rounds: int = 3,
    max_api_attempts_per_round: int | None = None,
    per_query_timeout_seconds: int | None = None,
    request_timeout_seconds: int = 30,
    skip_unsupported_models: bool = True,
) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    skipped_models: dict[str, str] = {}

    provider = get_llm_provider()

    async def _probe_model_availability(model_name: str) -> bool:
        try:
            text = await asyncio.wait_for(
                provider.complete_async(
                    system_prompt="Return ONLY: OK",
                    user_query="OK",
                    model=model_name,
                    max_tokens=8,
                    temperature=0,
                    top_p=0,
                    timeout=15,
                ),
                timeout=20,
            )
        except Exception:
            return False
        return bool((text or "").strip())

    for model in models:
        if skip_unsupported_models:
            available = await _probe_model_availability(model)
            if not available:
                skipped_models[model] = "probe_failed_or_empty_response"
                continue
        reports[model] = await evaluate_keyword_backends_with_llm(
            snapshot_path=snapshot_path,
            max_queries=max_queries,
            start_query_index=start_query_index,
            model=model,
            fallback_model=fallback_model,
            model_profile=model_profile,
            vote_rounds=vote_rounds,
            max_api_attempts_per_round=max_api_attempts_per_round,
            per_query_timeout_seconds=per_query_timeout_seconds,
            request_timeout_seconds=request_timeout_seconds,
        )

    reliable = {m: reports[m]["llm_duel_summary"].get("reliable_ratio", 0.0) for m in reports}
    best_model = max(reliable, key=reliable.get) if reliable else None
    return {
        "snapshot": str(Path(snapshot_path)),
        "models": models,
        "evaluated_models": list(reports.keys()),
        "skipped_models": skipped_models,
        "best_model_by_reliability": best_model,
        "model_reliability": reliable,
        "reports": reports,
    }


__all__ = [
    "evaluate_keyword_backends_multi_model",
    "evaluate_keyword_backends_with_llm",
]
