#!/usr/bin/env python3
"""
A/B benchmark runner for omni-agent memory behavior in live Telegram webhook runtime.

Goals:
  - compare baseline vs adaptive memory-feedback flows on the same scenarios
  - collect observability-derived memory metrics (plan/decision/latency/context)
  - emit machine-readable JSON and human-readable Markdown report

This script depends on a running local webhook runtime and the black-box probe:
  scripts/channel/agent_channel_blackbox.py
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from test_config_resolver import (
        normalize_telegram_session_partition_mode,
        session_partition_mode_from_runtime_log,
        telegram_session_partition_mode,
    )
except ModuleNotFoundError as import_err:
    _resolver_path = Path(__file__).resolve().with_name("test_config_resolver.py")
    _resolver_spec = importlib.util.spec_from_file_location("test_config_resolver", _resolver_path)
    if _resolver_spec is None or _resolver_spec.loader is None:
        raise RuntimeError(f"failed to load resolver module from {_resolver_path}") from import_err
    _resolver_module = importlib.util.module_from_spec(_resolver_spec)
    sys.modules.setdefault(_resolver_spec.name, _resolver_module)
    _resolver_spec.loader.exec_module(_resolver_module)
    normalize_telegram_session_partition_mode = (
        _resolver_module.normalize_telegram_session_partition_mode
    )
    session_partition_mode_from_runtime_log = (
        _resolver_module.session_partition_mode_from_runtime_log
    )
    telegram_session_partition_mode = _resolver_module.telegram_session_partition_mode

DEFAULT_MAX_WAIT = int(os.environ.get("OMNI_BLACKBOX_MAX_WAIT_SECS", "40"))
DEFAULT_MAX_IDLE_SECS = int(os.environ.get("OMNI_BLACKBOX_MAX_IDLE_SECS", "30"))
DEFAULT_LOG_FILE = os.environ.get("OMNI_CHANNEL_LOG_FILE", ".run/logs/omni-agent-webhook.log")
FORBIDDEN_LOG_PATTERN = "tools/call: Mcp error"

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
EVENT_TOKEN_RE = re.compile(r"\bevent\s*=\s*(?:\"|')?([A-Za-z0-9_.:-]+)")
LOG_TOKEN_RE = re.compile(r"\b([A-Za-z0-9_.:-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s]+))")

RESET_EVENT = "telegram.command.session_reset.replied"
FEEDBACK_EVENT = "telegram.command.session_feedback_json.replied"
CONTROL_ADMIN_REQUIRED_EVENT = "telegram.command.control_admin_required.replied"
RECALL_PLAN_EVENT = "agent.memory.recall.planned"
RECALL_INJECTED_EVENT = "agent.memory.recall.injected"
RECALL_SKIPPED_EVENT = "agent.memory.recall.skipped"
RECALL_FEEDBACK_EVENT = "agent.memory.recall.feedback_updated"
BOT_MARKER = "→ Bot:"


def infer_session_ids_from_runtime_log(log_file: Path) -> tuple[int | None, int | None, int | None]:
    try:
        from test_config_resolver import session_ids_from_runtime_log as resolver
    except ModuleNotFoundError:
        script_dir = Path(__file__).resolve().parent
        if str(script_dir) not in sys.path:
            sys.path.insert(0, str(script_dir))
        from test_config_resolver import session_ids_from_runtime_log as resolver
    return resolver(log_file)


def resolve_runtime_partition_mode(log_file: Path) -> str | None:
    override = os.environ.get("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "").strip()
    normalized_override = normalize_telegram_session_partition_mode(override)
    if normalized_override:
        return normalized_override

    mode_from_log = session_partition_mode_from_runtime_log(log_file)
    if mode_from_log:
        return mode_from_log

    return telegram_session_partition_mode()


@dataclass(frozen=True)
class QuerySpec:
    prompt: str
    expected_keywords: tuple[str, ...]
    required_ratio: float


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    description: str
    setup_prompts: tuple[str, ...]
    queries: tuple[QuerySpec, ...]
    reset_before: bool = True
    reset_after: bool = False


@dataclass
class TurnResult:
    mode: str
    iteration: int
    scenario_id: str
    query_index: int
    prompt: str
    expected_keywords: tuple[str, ...]
    required_ratio: float
    keyword_hit_ratio: float | None
    keyword_success: bool | None
    decision: str | None
    query_tokens: int | None
    recalled_selected: int | None
    recalled_injected: int | None
    context_chars_injected: int | None
    pipeline_duration_ms: int | None
    best_score: float | None
    weakest_score: float | None
    k1: int | None
    k2: int | None
    lambda_value: float | None
    min_score: float | None
    budget_pressure: float | None
    window_pressure: float | None
    recall_feedback_bias: float | None
    feedback_direction: str | None
    feedback_bias_before: float | None
    feedback_bias_after: float | None
    mcp_error_detected: bool
    bot_excerpt: str | None


@dataclass
class ModeSummary:
    mode: str
    iterations: int
    scenarios: int
    query_turns: int
    scored_turns: int
    success_count: int
    success_rate: float
    avg_keyword_hit_ratio: float
    injected_count: int
    skipped_count: int
    injected_rate: float
    avg_pipeline_duration_ms: float
    avg_query_tokens: float
    avg_recalled_selected: float
    avg_recalled_injected: float
    avg_context_chars_injected: float
    avg_best_score: float
    avg_weakest_score: float
    avg_k1: float
    avg_k2: float
    avg_lambda: float
    avg_min_score: float
    avg_budget_pressure: float
    avg_window_pressure: float
    avg_recall_feedback_bias: float
    feedback_updates: int
    feedback_up_count: int
    feedback_down_count: int
    avg_feedback_delta: float
    mcp_error_turns: int


@dataclass
class BenchmarkConfig:
    dataset_path: Path
    log_file: Path
    blackbox_script: Path
    chat_id: int
    user_id: int
    thread_id: int | None
    runtime_partition_mode: str | None
    username: str
    max_wait: int
    max_idle_secs: int
    modes: tuple[str, ...]
    iterations: int
    skip_reset: bool
    output_json: Path
    output_markdown: Path
    fail_on_mcp_error: bool
    feedback_policy: str
    feedback_down_threshold: float


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=(
            "Run live A/B memory benchmark against local omni-agent webhook runtime "
            "(baseline vs adaptive feedback mode)."
        )
    )
    parser.add_argument(
        "--dataset",
        default=str(script_dir / "fixtures" / "memory_benchmark_scenarios.json"),
        help="Scenario dataset JSON path.",
    )
    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG_FILE,
        help=f"Runtime log file path (default: {DEFAULT_LOG_FILE}).",
    )
    parser.add_argument(
        "--blackbox-script",
        default=str(script_dir / "agent_channel_blackbox.py"),
        help="Path to black-box probe script.",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("OMNI_TEST_USERNAME", ""),
        help="Synthetic Telegram username for allowlist checks.",
    )
    parser.add_argument(
        "--chat-id",
        type=int,
        default=None,
        help="Pinned synthetic Telegram chat id. Default: infer once from runtime log.",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="Pinned synthetic Telegram user id. Default: infer once from runtime log.",
    )
    parser.add_argument(
        "--thread-id",
        type=int,
        default=None,
        help="Pinned synthetic Telegram thread id (optional).",
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=DEFAULT_MAX_WAIT,
        help=f"Per probe max wait in seconds (default: {DEFAULT_MAX_WAIT}).",
    )
    parser.add_argument(
        "--max-idle-secs",
        type=int,
        default=DEFAULT_MAX_IDLE_SECS,
        help=f"Per probe max idle seconds (default: {DEFAULT_MAX_IDLE_SECS}).",
    )
    parser.add_argument(
        "--mode",
        action="append",
        choices=("baseline", "adaptive"),
        help="Benchmark mode (repeatable). Default: baseline+adaptive.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Dataset replay count per mode (default: 1).",
    )
    parser.add_argument(
        "--skip-reset",
        action="store_true",
        help="Do not issue /reset between scenarios.",
    )
    parser.add_argument(
        "--output-json",
        default=str(default_report_path("omni-agent-memory-benchmark.json")),
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--output-markdown",
        default=str(default_report_path("omni-agent-memory-benchmark.md")),
        help="Output Markdown report path.",
    )
    parser.add_argument(
        "--fail-on-mcp-error",
        action="store_true",
        help=(
            "Fail immediately when logs include `tools/call: Mcp error`. "
            "Default behavior records this as interference."
        ),
    )
    parser.add_argument(
        "--feedback-policy",
        choices=("strict", "deadband"),
        default="deadband",
        help=(
            "Adaptive feedback policy. "
            "`strict`: success=up, failure=down. "
            "`deadband`: success=up, strong failure only=down, else neutral."
        ),
    )
    parser.add_argument(
        "--feedback-down-threshold",
        type=float,
        default=0.34,
        help=(
            "When feedback-policy=deadband, send `down` only when keyword hit ratio "
            "is less than or equal to this threshold (default: 0.34)."
        ),
    )
    return parser.parse_args()


def default_report_path(filename: str) -> Path:
    runtime_root = Path(os.environ.get("PRJ_RUNTIME_DIR", ".run"))
    if not runtime_root.is_absolute():
        project_root = Path(os.environ.get("PRJ_ROOT", Path.cwd()))
        runtime_root = project_root / runtime_root
    return runtime_root / "reports" / filename


def build_config(args: argparse.Namespace) -> BenchmarkConfig:
    modes = tuple(args.mode) if args.mode else ("baseline", "adaptive")
    if args.max_wait <= 0:
        raise ValueError("--max-wait must be a positive integer.")
    if args.max_idle_secs <= 0:
        raise ValueError("--max-idle-secs must be a positive integer.")
    if args.iterations <= 0:
        raise ValueError("--iterations must be a positive integer.")
    if not (0.0 <= args.feedback_down_threshold <= 1.0):
        raise ValueError("--feedback-down-threshold must be between 0.0 and 1.0.")

    env_chat = os.environ.get("OMNI_TEST_CHAT_ID", "").strip()
    env_user = os.environ.get("OMNI_TEST_USER_ID", "").strip()
    env_thread = os.environ.get("OMNI_TEST_THREAD_ID", "").strip()
    chat_id = args.chat_id if args.chat_id is not None else (int(env_chat) if env_chat else None)
    user_id = args.user_id if args.user_id is not None else (int(env_user) if env_user else None)
    thread_id = (
        args.thread_id if args.thread_id is not None else (int(env_thread) if env_thread else None)
    )

    config = BenchmarkConfig(
        dataset_path=Path(args.dataset).expanduser().resolve(),
        log_file=Path(args.log_file).expanduser().resolve(),
        blackbox_script=Path(args.blackbox_script).expanduser().resolve(),
        chat_id=0,
        user_id=0,
        thread_id=thread_id,
        runtime_partition_mode=None,
        username=args.username.strip(),
        max_wait=args.max_wait,
        max_idle_secs=args.max_idle_secs,
        modes=modes,
        iterations=args.iterations,
        skip_reset=bool(args.skip_reset),
        output_json=Path(args.output_json).expanduser().resolve(),
        output_markdown=Path(args.output_markdown).expanduser().resolve(),
        fail_on_mcp_error=bool(args.fail_on_mcp_error),
        feedback_policy=args.feedback_policy,
        feedback_down_threshold=float(args.feedback_down_threshold),
    )

    if not config.dataset_path.exists():
        raise ValueError(f"dataset not found: {config.dataset_path}")
    if not config.blackbox_script.exists():
        raise ValueError(f"black-box script not found: {config.blackbox_script}")

    if chat_id is None or user_id is None:
        inferred_chat, inferred_user, inferred_thread = infer_session_ids_from_runtime_log(
            config.log_file
        )
        if chat_id is None:
            chat_id = inferred_chat
        if user_id is None:
            user_id = inferred_user
        if config.thread_id is None:
            config.thread_id = inferred_thread
    if chat_id is None or user_id is None:
        raise ValueError(
            "chat/user id are required. Set --chat-id/--user-id (or OMNI_TEST_CHAT_ID/OMNI_TEST_USER_ID), "
            "or ensure runtime log has a recent session marker for inference."
        )
    config.chat_id = int(chat_id)
    config.user_id = int(user_id)
    config.runtime_partition_mode = resolve_runtime_partition_mode(config.log_file)

    config.log_file.parent.mkdir(parents=True, exist_ok=True)
    config.output_json.parent.mkdir(parents=True, exist_ok=True)
    config.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    return config


def load_scenarios(path: Path) -> tuple[ScenarioSpec, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    scenarios_raw = raw.get("scenarios")
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise ValueError("dataset must provide a non-empty 'scenarios' array")

    scenarios: list[ScenarioSpec] = []
    seen_ids: set[str] = set()
    for index, scenario_obj in enumerate(scenarios_raw):
        if not isinstance(scenario_obj, dict):
            raise ValueError(f"scenario at index {index} must be an object")
        scenario_id = str(scenario_obj.get("id", "")).strip()
        if not scenario_id:
            raise ValueError(f"scenario at index {index} has empty id")
        if scenario_id in seen_ids:
            raise ValueError(f"duplicate scenario id: {scenario_id}")
        seen_ids.add(scenario_id)

        description = str(scenario_obj.get("description", "")).strip() or scenario_id

        setup_prompts_raw = scenario_obj.get("setup_prompts", [])
        if not isinstance(setup_prompts_raw, list):
            raise ValueError(f"scenario '{scenario_id}' setup_prompts must be an array")
        setup_prompts = tuple(str(item).strip() for item in setup_prompts_raw if str(item).strip())

        queries_raw = scenario_obj.get("queries", [])
        if not isinstance(queries_raw, list) or not queries_raw:
            raise ValueError(f"scenario '{scenario_id}' must define non-empty queries")
        queries: list[QuerySpec] = []
        for query_index, query_obj in enumerate(queries_raw):
            if not isinstance(query_obj, dict):
                raise ValueError(f"scenario '{scenario_id}' query[{query_index}] must be an object")
            prompt = str(query_obj.get("prompt", "")).strip()
            if not prompt:
                raise ValueError(f"scenario '{scenario_id}' query[{query_index}] has empty prompt")
            keywords_raw = query_obj.get("expected_keywords", [])
            if not isinstance(keywords_raw, list):
                raise ValueError(
                    f"scenario '{scenario_id}' query[{query_index}] expected_keywords must be an array"
                )
            keywords = tuple(str(word).strip() for word in keywords_raw if str(word).strip())
            required_ratio = float(query_obj.get("required_ratio", 1.0))
            if required_ratio <= 0.0 or required_ratio > 1.0:
                raise ValueError(
                    f"scenario '{scenario_id}' query[{query_index}] required_ratio must be in (0, 1]"
                )
            queries.append(
                QuerySpec(
                    prompt=prompt,
                    expected_keywords=keywords,
                    required_ratio=required_ratio,
                )
            )

        scenarios.append(
            ScenarioSpec(
                scenario_id=scenario_id,
                description=description,
                setup_prompts=setup_prompts,
                queries=tuple(queries),
                reset_before=bool(scenario_obj.get("reset_before", True)),
                reset_after=bool(scenario_obj.get("reset_after", False)),
            )
        )

    return tuple(scenarios)


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for _ in handle)


def read_new_lines(path: Path, cursor: int) -> tuple[int, list[str]]:
    if not path.exists():
        return cursor, []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        lines = handle.read().splitlines()
    total = len(lines)
    if total <= cursor:
        return total, []
    return total, lines[cursor:]


def strip_ansi(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value)


def extract_event_token(value: str) -> str | None:
    match = EVENT_TOKEN_RE.search(value)
    return match.group(1) if match else None


def has_event(lines: list[str], event: str) -> bool:
    return any(extract_event_token(line) == event for line in lines)


def parse_log_tokens(value: str) -> dict[str, str]:
    normalized = strip_ansi(value)
    tokens: dict[str, str] = {}
    for match in LOG_TOKEN_RE.finditer(normalized):
        key = match.group(1)
        token = match.group(2) or match.group(3) or match.group(4) or ""
        tokens[key] = token
    return tokens


def token_as_int(tokens: dict[str, str], key: str) -> int | None:
    raw = tokens.get(key)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def token_as_float(tokens: dict[str, str], key: str) -> float | None:
    raw = tokens.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def trim_text(value: str | None, *, max_chars: int = 280) -> str | None:
    if value is None:
        return None
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3] + "..."


def run_probe(
    config: BenchmarkConfig,
    *,
    prompt: str,
    expect_event: str,
    allow_no_bot: bool = False,
) -> list[str]:
    start_line = count_lines(config.log_file)
    cmd = [
        sys.executable,
        str(config.blackbox_script),
        "--prompt",
        prompt,
        "--expect-event",
        expect_event,
        "--chat-id",
        str(config.chat_id),
        "--user-id",
        str(config.user_id),
        "--allow-chat-id",
        str(config.chat_id),
        "--max-wait",
        str(config.max_wait),
        "--max-idle-secs",
        str(config.max_idle_secs),
        "--log-file",
        str(config.log_file),
        "--no-follow",
    ]
    if config.thread_id is not None:
        cmd.extend(["--thread-id", str(config.thread_id)])
    if config.runtime_partition_mode:
        cmd.extend(["--session-partition", config.runtime_partition_mode])
    if config.fail_on_mcp_error:
        cmd.extend(["--forbid-log-regex", FORBIDDEN_LOG_PATTERN])
    else:
        cmd.append("--no-fail-fast-error-log")
    if config.username:
        cmd.extend(["--username", config.username])
    if allow_no_bot:
        cmd.append("--allow-no-bot")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as error:
        _, lines = read_new_lines(config.log_file, start_line)
        normalized_lines = [strip_ansi(line) for line in lines]
        if prompt.startswith("/") and has_event(normalized_lines, CONTROL_ADMIN_REQUIRED_EVENT):
            raise RuntimeError(
                "control command denied (admin_required): "
                "set --user-id to an admin-capable Telegram user for benchmark control flows."
            ) from error
        raise
    _, lines = read_new_lines(config.log_file, start_line)
    return [strip_ansi(line) for line in lines]


def parse_turn_signals(lines: list[str]) -> dict[str, Any]:
    signals: dict[str, Any] = {
        "plan": None,
        "decision": None,
        "feedback": None,
        "bot_line": None,
        "mcp_error": False,
    }

    for line in lines:
        if FORBIDDEN_LOG_PATTERN in line:
            signals["mcp_error"] = True
        if BOT_MARKER in line:
            signals["bot_line"] = line.split(BOT_MARKER, 1)[1].strip()

        event = extract_event_token(line)
        if event is None:
            continue

        tokens = parse_log_tokens(line)
        if event == RECALL_PLAN_EVENT:
            signals["plan"] = tokens
        elif event in (RECALL_INJECTED_EVENT, RECALL_SKIPPED_EVENT):
            tokens = {**tokens, "event": event}
            signals["decision"] = tokens
        elif event == RECALL_FEEDBACK_EVENT:
            signals["feedback"] = tokens

    return signals


def keyword_hit_ratio(bot_line: str | None, expected_keywords: tuple[str, ...]) -> float | None:
    if not expected_keywords:
        return None
    if not bot_line:
        return 0.0
    lowered = bot_line.lower()
    hits = sum(1 for keyword in expected_keywords if keyword.lower() in lowered)
    return hits / len(expected_keywords)


def maybe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.fmean(values))


def maybe_mean_int(values: list[int]) -> float:
    if not values:
        return 0.0
    return float(statistics.fmean(values))


def as_float(value: int | float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def build_turn_result(
    *,
    mode: str,
    iteration: int,
    scenario_id: str,
    query_index: int,
    query: QuerySpec,
    lines: list[str],
    feedback_direction: str | None = None,
    feedback_lines: list[str] | None = None,
) -> TurnResult:
    signals = parse_turn_signals(lines)
    plan = signals.get("plan") or {}
    decision = signals.get("decision") or {}

    bot_line = signals.get("bot_line")
    hit_ratio = keyword_hit_ratio(bot_line, query.expected_keywords)
    success = None
    if hit_ratio is not None:
        success = hit_ratio >= query.required_ratio

    feedback_before: float | None = None
    feedback_after: float | None = None
    if feedback_lines:
        feedback_signals = parse_turn_signals(feedback_lines)
        feedback_tokens = feedback_signals.get("feedback") or {}
        feedback_before = token_as_float(feedback_tokens, "recall_feedback_bias_before")
        feedback_after = token_as_float(feedback_tokens, "recall_feedback_bias_after")

    return TurnResult(
        mode=mode,
        iteration=iteration,
        scenario_id=scenario_id,
        query_index=query_index,
        prompt=query.prompt,
        expected_keywords=query.expected_keywords,
        required_ratio=query.required_ratio,
        keyword_hit_ratio=hit_ratio,
        keyword_success=success,
        decision=(decision.get("event") or "").split(".")[-1] or None,
        query_tokens=token_as_int(decision, "query_tokens"),
        recalled_selected=token_as_int(decision, "recalled_selected"),
        recalled_injected=token_as_int(decision, "recalled_injected"),
        context_chars_injected=token_as_int(decision, "context_chars_injected"),
        pipeline_duration_ms=token_as_int(decision, "pipeline_duration_ms"),
        best_score=token_as_float(decision, "best_score"),
        weakest_score=token_as_float(decision, "weakest_score"),
        k1=token_as_int(plan, "k1"),
        k2=token_as_int(plan, "k2"),
        lambda_value=token_as_float(plan, "lambda"),
        min_score=token_as_float(plan, "min_score"),
        budget_pressure=token_as_float(plan, "budget_pressure"),
        window_pressure=token_as_float(plan, "window_pressure"),
        recall_feedback_bias=token_as_float(plan, "recall_feedback_bias"),
        feedback_direction=feedback_direction,
        feedback_bias_before=feedback_before,
        feedback_bias_after=feedback_after,
        mcp_error_detected=bool(signals.get("mcp_error")),
        bot_excerpt=trim_text(bot_line),
    )


def summarize_mode(
    *,
    mode: str,
    iterations: int,
    scenario_count: int,
    turns: list[TurnResult],
) -> ModeSummary:
    scored_turns = [turn for turn in turns if turn.keyword_hit_ratio is not None]
    successful_turns = [turn for turn in scored_turns if turn.keyword_success]

    query_tokens = [value for value in (turn.query_tokens for turn in turns) if value is not None]
    recalled_selected = [
        value for value in (turn.recalled_selected for turn in turns) if value is not None
    ]
    recalled_injected = [
        value for value in (turn.recalled_injected for turn in turns) if value is not None
    ]
    context_chars = [
        value for value in (turn.context_chars_injected for turn in turns) if value is not None
    ]
    pipeline_duration = [
        value for value in (turn.pipeline_duration_ms for turn in turns) if value is not None
    ]
    best_scores = [value for value in (turn.best_score for turn in turns) if value is not None]
    weakest_scores = [
        value for value in (turn.weakest_score for turn in turns) if value is not None
    ]

    k1_values = [value for value in (turn.k1 for turn in turns) if value is not None]
    k2_values = [value for value in (turn.k2 for turn in turns) if value is not None]
    lambda_values = [value for value in (turn.lambda_value for turn in turns) if value is not None]
    min_score_values = [value for value in (turn.min_score for turn in turns) if value is not None]
    budget_pressure_values = [
        value for value in (turn.budget_pressure for turn in turns) if value is not None
    ]
    window_pressure_values = [
        value for value in (turn.window_pressure for turn in turns) if value is not None
    ]
    recall_bias_values = [
        value for value in (turn.recall_feedback_bias for turn in turns) if value is not None
    ]

    feedback_updates = [
        turn
        for turn in turns
        if turn.feedback_bias_before is not None and turn.feedback_bias_after is not None
    ]
    feedback_deltas = [
        turn.feedback_bias_after - turn.feedback_bias_before for turn in feedback_updates
    ]
    feedback_up_count = sum(1 for turn in turns if turn.feedback_direction == "up")
    feedback_down_count = sum(1 for turn in turns if turn.feedback_direction == "down")
    mcp_error_turns = sum(1 for turn in turns if turn.mcp_error_detected)

    injected_count = sum(1 for turn in turns if turn.decision == "injected")
    skipped_count = sum(1 for turn in turns if turn.decision == "skipped")
    completed_count = injected_count + skipped_count

    return ModeSummary(
        mode=mode,
        iterations=iterations,
        scenarios=scenario_count,
        query_turns=len(turns),
        scored_turns=len(scored_turns),
        success_count=len(successful_turns),
        success_rate=(len(successful_turns) / len(scored_turns)) if scored_turns else 0.0,
        avg_keyword_hit_ratio=maybe_mean(
            [turn.keyword_hit_ratio for turn in scored_turns if turn.keyword_hit_ratio is not None]
        ),
        injected_count=injected_count,
        skipped_count=skipped_count,
        injected_rate=(injected_count / completed_count) if completed_count else 0.0,
        avg_pipeline_duration_ms=maybe_mean_int(pipeline_duration),
        avg_query_tokens=maybe_mean_int(query_tokens),
        avg_recalled_selected=maybe_mean_int(recalled_selected),
        avg_recalled_injected=maybe_mean_int(recalled_injected),
        avg_context_chars_injected=maybe_mean_int(context_chars),
        avg_best_score=maybe_mean(best_scores),
        avg_weakest_score=maybe_mean(weakest_scores),
        avg_k1=maybe_mean_int(k1_values),
        avg_k2=maybe_mean_int(k2_values),
        avg_lambda=maybe_mean(lambda_values),
        avg_min_score=maybe_mean(min_score_values),
        avg_budget_pressure=maybe_mean(budget_pressure_values),
        avg_window_pressure=maybe_mean(window_pressure_values),
        avg_recall_feedback_bias=maybe_mean(recall_bias_values),
        feedback_updates=len(feedback_updates),
        feedback_up_count=feedback_up_count,
        feedback_down_count=feedback_down_count,
        avg_feedback_delta=maybe_mean(feedback_deltas),
        mcp_error_turns=mcp_error_turns,
    )


def compare_mode_summaries(
    baseline: ModeSummary,
    adaptive: ModeSummary,
) -> dict[str, float]:
    return {
        "success_rate_delta": adaptive.success_rate - baseline.success_rate,
        "avg_keyword_hit_ratio_delta": adaptive.avg_keyword_hit_ratio
        - baseline.avg_keyword_hit_ratio,
        "injected_rate_delta": adaptive.injected_rate - baseline.injected_rate,
        "avg_pipeline_duration_ms_delta": adaptive.avg_pipeline_duration_ms
        - baseline.avg_pipeline_duration_ms,
        "avg_recalled_selected_delta": adaptive.avg_recalled_selected
        - baseline.avg_recalled_selected,
        "avg_recalled_injected_delta": adaptive.avg_recalled_injected
        - baseline.avg_recalled_injected,
        "avg_best_score_delta": adaptive.avg_best_score - baseline.avg_best_score,
        "avg_recall_feedback_bias_delta": adaptive.avg_recall_feedback_bias
        - baseline.avg_recall_feedback_bias,
        "mcp_error_turns_delta": float(adaptive.mcp_error_turns - baseline.mcp_error_turns),
    }


def select_feedback_direction(
    *,
    keyword_hit_ratio: float | None,
    keyword_success: bool | None,
    policy: str,
    down_threshold: float,
) -> str | None:
    if keyword_success is None:
        return None
    if policy == "strict":
        return "up" if keyword_success else "down"
    if keyword_success:
        return "up"
    if keyword_hit_ratio is not None and keyword_hit_ratio <= down_threshold:
        return "down"
    return None


def run_reset(config: BenchmarkConfig) -> None:
    run_probe(
        config,
        prompt="/reset",
        expect_event=RESET_EVENT,
        allow_no_bot=True,
    )


def run_feedback(config: BenchmarkConfig, direction: str) -> list[str]:
    prompt = "/session feedback up json" if direction == "up" else "/session feedback down json"
    return run_probe(config, prompt=prompt, expect_event=FEEDBACK_EVENT)


def run_non_command_turn(config: BenchmarkConfig, prompt: str) -> list[str]:
    return run_probe(config, prompt=prompt, expect_event=RECALL_PLAN_EVENT)


def run_mode(
    config: BenchmarkConfig,
    scenarios: tuple[ScenarioSpec, ...],
    mode: str,
) -> list[TurnResult]:
    print(f"\n=== Running mode: {mode} ===", flush=True)
    all_turns: list[TurnResult] = []

    for iteration in range(1, config.iterations + 1):
        print(f"\n[Iteration {iteration}/{config.iterations}]", flush=True)
        for scenario in scenarios:
            print(f"  - Scenario: {scenario.scenario_id}", flush=True)
            if scenario.reset_before and not config.skip_reset:
                run_reset(config)

            for prompt in scenario.setup_prompts:
                run_non_command_turn(config, prompt)

            for index, query in enumerate(scenario.queries, start=1):
                turn_lines = run_non_command_turn(config, query.prompt)
                feedback_direction: str | None = None
                feedback_lines: list[str] | None = None

                provisional = build_turn_result(
                    mode=mode,
                    iteration=iteration,
                    scenario_id=scenario.scenario_id,
                    query_index=index,
                    query=query,
                    lines=turn_lines,
                )

                if mode == "adaptive" and provisional.keyword_success is not None:
                    feedback_direction = select_feedback_direction(
                        keyword_hit_ratio=provisional.keyword_hit_ratio,
                        keyword_success=provisional.keyword_success,
                        policy=config.feedback_policy,
                        down_threshold=config.feedback_down_threshold,
                    )
                    if feedback_direction is not None:
                        feedback_lines = run_feedback(config, feedback_direction)

                turn_result = build_turn_result(
                    mode=mode,
                    iteration=iteration,
                    scenario_id=scenario.scenario_id,
                    query_index=index,
                    query=query,
                    lines=turn_lines,
                    feedback_direction=feedback_direction,
                    feedback_lines=feedback_lines,
                )
                all_turns.append(turn_result)

            if scenario.reset_after and not config.skip_reset:
                run_reset(config)

    return all_turns


def format_float(value: float) -> str:
    return f"{value:.4f}"


def build_markdown_report(
    *,
    config: BenchmarkConfig,
    scenarios: tuple[ScenarioSpec, ...],
    started_at: str,
    finished_at: str,
    mode_summaries: dict[str, ModeSummary],
    comparison: dict[str, float] | None,
) -> str:
    lines: list[str] = []
    lines.append("# Omni-Agent Memory A/B Benchmark")
    lines.append("")
    lines.append("## Run Metadata")
    lines.append("")
    lines.append(f"- started_at_utc: `{started_at}`")
    lines.append(f"- finished_at_utc: `{finished_at}`")
    lines.append(f"- dataset: `{config.dataset_path}`")
    lines.append(f"- log_file: `{config.log_file}`")
    lines.append(
        f"- session_target: `chat={config.chat_id}, user={config.user_id}, "
        f"thread={config.thread_id if config.thread_id is not None else 'none'}`"
    )
    lines.append(f"- runtime_partition_mode: `{config.runtime_partition_mode or 'unknown'}`")
    lines.append(f"- modes: `{', '.join(config.modes)}`")
    lines.append(f"- iterations_per_mode: `{config.iterations}`")
    lines.append(f"- scenario_count: `{len(scenarios)}`")
    lines.append(f"- feedback_policy: `{config.feedback_policy}`")
    lines.append(f"- feedback_down_threshold: `{config.feedback_down_threshold}`")
    lines.append("")

    lines.append("## Scenario Set")
    lines.append("")
    for scenario in scenarios:
        lines.append(
            f"- `{scenario.scenario_id}`: {scenario.description} "
            f"(setup={len(scenario.setup_prompts)}, queries={len(scenario.queries)})"
        )
    lines.append("")

    lines.append("## Mode Summary")
    lines.append("")
    lines.append(
        "| Mode | Query Turns | Scored Turns | Success Rate | Avg Hit Ratio | Injected Rate | Avg Pipeline ms | Avg k1 | Avg k2 | Avg lambda | Avg Feedback Bias | MCP Error Turns |"
    )
    lines.append(
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    for mode in config.modes:
        summary = mode_summaries[mode]
        lines.append(
            "| "
            f"{mode} | "
            f"{summary.query_turns} | "
            f"{summary.scored_turns} | "
            f"{format_float(summary.success_rate)} | "
            f"{format_float(summary.avg_keyword_hit_ratio)} | "
            f"{format_float(summary.injected_rate)} | "
            f"{format_float(summary.avg_pipeline_duration_ms)} | "
            f"{format_float(summary.avg_k1)} | "
            f"{format_float(summary.avg_k2)} | "
            f"{format_float(summary.avg_lambda)} | "
            f"{format_float(summary.avg_recall_feedback_bias)} | "
            f"{summary.mcp_error_turns} |"
        )
    lines.append("")

    if comparison is not None:
        lines.append("## Adaptive Delta vs Baseline")
        lines.append("")
        lines.append("| Metric | Delta |")
        lines.append("| --- | ---: |")
        for key, value in comparison.items():
            lines.append(f"| {key} | {format_float(value)} |")
        lines.append("")

    confidence_note = "moderate"
    baseline = mode_summaries.get("baseline")
    adaptive = mode_summaries.get("adaptive")
    if baseline and adaptive and min(baseline.scored_turns, adaptive.scored_turns) < 5:
        confidence_note = "low"
    total_mcp_error_turns = sum(summary.mcp_error_turns for summary in mode_summaries.values())

    lines.append("## Confidence")
    lines.append("")
    lines.append(
        "- This benchmark is proxy-based (keyword hit + memory observability metrics), "
        "not a human-graded semantic evaluation."
    )
    lines.append(
        f"- Confidence level for this run: `{confidence_note}` "
        f"(scored turns may be small; increase `--iterations` for stronger signal)."
    )
    if total_mcp_error_turns > 0:
        lines.append(
            f"- MCP error interference observed on `{total_mcp_error_turns}` query turn(s)."
        )
    lines.append("")

    return "\n".join(lines)


def serialize_turn(turn: TurnResult) -> dict[str, Any]:
    payload = asdict(turn)
    payload["expected_keywords"] = list(turn.expected_keywords)
    return payload


def to_iso_utc(unix_ts: float) -> str:
    return datetime.fromtimestamp(unix_ts, tz=UTC).isoformat()


def main() -> int:
    args = parse_args()
    try:
        config = build_config(args)
        scenarios = load_scenarios(config.dataset_path)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    started_ts = time.time()
    started_at = to_iso_utc(started_ts)

    print("Running memory benchmark...", flush=True)
    print(f"dataset={config.dataset_path}", flush=True)
    print(f"log_file={config.log_file}", flush=True)
    print(
        f"session_target=chat:{config.chat_id} user:{config.user_id} "
        f"thread:{config.thread_id if config.thread_id is not None else 'none'}",
        flush=True,
    )
    print(
        f"runtime_partition_mode={config.runtime_partition_mode or 'unknown'}",
        flush=True,
    )
    print(f"modes={config.modes}", flush=True)
    print(f"iterations={config.iterations}", flush=True)
    print(f"fail_on_mcp_error={config.fail_on_mcp_error}", flush=True)
    print(
        f"feedback_policy={config.feedback_policy} "
        f"feedback_down_threshold={config.feedback_down_threshold}",
        flush=True,
    )

    mode_turns: dict[str, list[TurnResult]] = {}
    try:
        for mode in config.modes:
            mode_turns[mode] = run_mode(config, scenarios, mode)
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as error:
        print(f"Error: benchmark probe failed with exit code {error.returncode}", file=sys.stderr)
        return error.returncode if error.returncode != 0 else 1

    mode_summaries = {
        mode: summarize_mode(
            mode=mode,
            iterations=config.iterations,
            scenario_count=len(scenarios),
            turns=turns,
        )
        for mode, turns in mode_turns.items()
    }

    comparison: dict[str, float] | None = None
    if "baseline" in mode_summaries and "adaptive" in mode_summaries:
        comparison = compare_mode_summaries(
            mode_summaries["baseline"],
            mode_summaries["adaptive"],
        )

    finished_ts = time.time()
    finished_at = to_iso_utc(finished_ts)

    markdown = build_markdown_report(
        config=config,
        scenarios=scenarios,
        started_at=started_at,
        finished_at=finished_at,
        mode_summaries=mode_summaries,
        comparison=comparison,
    )

    json_payload: dict[str, Any] = {
        "metadata": {
            "started_at_utc": started_at,
            "finished_at_utc": finished_at,
            "duration_secs": round(finished_ts - started_ts, 3),
            "dataset": str(config.dataset_path),
            "log_file": str(config.log_file),
            "chat_id": config.chat_id,
            "user_id": config.user_id,
            "thread_id": config.thread_id,
            "runtime_partition_mode": config.runtime_partition_mode,
            "modes": list(config.modes),
            "iterations_per_mode": config.iterations,
            "scenario_count": len(scenarios),
            "max_wait_secs": config.max_wait,
            "max_idle_secs": config.max_idle_secs,
            "username": config.username,
            "skip_reset": config.skip_reset,
            "fail_on_mcp_error": config.fail_on_mcp_error,
            "feedback_policy": config.feedback_policy,
            "feedback_down_threshold": config.feedback_down_threshold,
        },
        "scenarios": [
            {
                "id": scenario.scenario_id,
                "description": scenario.description,
                "setup_prompts": list(scenario.setup_prompts),
                "queries": [
                    {
                        "prompt": query.prompt,
                        "expected_keywords": list(query.expected_keywords),
                        "required_ratio": query.required_ratio,
                    }
                    for query in scenario.queries
                ],
            }
            for scenario in scenarios
        ],
        "mode_summaries": {mode: asdict(summary) for mode, summary in mode_summaries.items()},
        "comparison": comparison,
        "turns": {
            mode: [serialize_turn(turn) for turn in turns] for mode, turns in mode_turns.items()
        },
    }

    config.output_json.write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    config.output_markdown.write_text(markdown + "\n", encoding="utf-8")

    print("\nBenchmark completed.", flush=True)
    print(f"JSON report: {config.output_json}", flush=True)
    print(f"Markdown report: {config.output_markdown}", flush=True)
    total_mcp_error_turns = sum(summary.mcp_error_turns for summary in mode_summaries.values())
    if total_mcp_error_turns > 0:
        print(
            f"Observed MCP error interference on {total_mcp_error_turns} query turn(s).",
            flush=True,
        )
    if comparison is not None:
        print("Adaptive delta vs baseline:", flush=True)
        for key, value in comparison.items():
            print(f"  {key}={value:.4f}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
