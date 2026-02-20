"""Rust scanner backed command index for ToolsLoader."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from omni.foundation.bridge.tool_record_validation import (
    COMMAND_INDEX_SCHEMA_V1,
    validate_scanned_tool_record,
)

_COMMAND_INDEX_CACHE_SCHEMA = "omni.command-index.v1"


def _record_phase(phase: str, duration_ms: float, **extra: Any) -> None:
    """Record monitor phase when skills monitor is active."""
    try:
        from omni.foundation.runtime.skills_monitor import record_phase

        record_phase(phase, duration_ms, **extra)
    except Exception:
        pass


def _iter_script_files(scripts_path: Path) -> list[Path]:
    """Return deterministic list of Python script files for signature building."""
    if not scripts_path.exists():
        return []
    return sorted([p for p in scripts_path.rglob("*.py") if "__pycache__" not in p.parts])


def _scripts_signature(skill_name: str, scripts_path: Path) -> str:
    """Build signature from scripts path + files metadata for cache invalidation."""
    hasher = hashlib.sha256()
    hasher.update(str(skill_name).encode("utf-8"))
    hasher.update(str(scripts_path.resolve()).encode("utf-8"))
    for py_file in _iter_script_files(scripts_path):
        stat = py_file.stat()
        hasher.update(str(py_file.relative_to(scripts_path)).encode("utf-8"))
        hasher.update(str(stat.st_size).encode("utf-8"))
        hasher.update(str(stat.st_mtime_ns).encode("utf-8"))
    return hasher.hexdigest()


def _cache_file_for(skill_name: str, scripts_path: Path) -> Path:
    """Resolve command-index cache file path for this skill/scripts directory."""
    skill_hash = hashlib.sha256(str(scripts_path.resolve()).encode("utf-8")).hexdigest()[:12]
    safe_skill_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in skill_name)
    filename = f"{safe_skill_name}-{skill_hash}.json"
    try:
        from omni.foundation import PRJ_CACHE

        cache_dir = Path(PRJ_CACHE("omni-tools-loader", "command-index"))
    except Exception:
        cache_dir = Path.cwd() / ".cache" / "omni-tools-loader" / "command-index"
    return cache_dir / filename


def _load_cached_index(
    skill_name: str, scripts_path: Path, signature: str
) -> dict[str, list[Path]] | None:
    """Load cached command index if schema/signature match."""
    cache_file = _cache_file_for(skill_name, scripts_path)
    if not cache_file.exists():
        return None
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        if payload.get("schema") != _COMMAND_INDEX_CACHE_SCHEMA:
            return None
        if payload.get("signature") != signature:
            return None
        raw_index = payload.get("index")
        if not isinstance(raw_index, dict):
            return None
        index: dict[str, list[Path]] = {}
        for command, raw_paths in raw_index.items():
            if not isinstance(command, str) or not isinstance(raw_paths, list):
                continue
            resolved_paths = [Path(p) for p in raw_paths if isinstance(p, str) and Path(p).exists()]
            if resolved_paths:
                index[command] = resolved_paths
        return index
    except Exception:
        return None


def _save_cached_index(
    skill_name: str,
    scripts_path: Path,
    signature: str,
    index: dict[str, list[Path]],
) -> None:
    """Persist command index snapshot for next process run."""
    cache_file = _cache_file_for(skill_name, scripts_path)
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": _COMMAND_INDEX_CACHE_SCHEMA,
            "signature": signature,
            "index": {command: [str(path) for path in paths] for command, paths in index.items()},
        }
        cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # Cache persistence is best-effort only.
        return


def build_rust_command_index(skill_name: str, scripts_path: Path) -> dict[str, list[Path]]:
    """Build command->script index from Rust scanner records with strict schema validation."""
    started = time.perf_counter()
    signature = _scripts_signature(skill_name, scripts_path)
    cached_index = _load_cached_index(skill_name, scripts_path, signature)
    if cached_index is not None:
        _record_phase(
            "runner.fast.load.index",
            (time.perf_counter() - started) * 1000,
            source="cache",
            skill=skill_name,
            command_count=len(cached_index),
        )
        return cached_index

    scan_started = time.perf_counter()
    from omni_core_rs import PySkillScanner

    index: dict[str, list[Path]] = {}
    skills_root = scripts_path.parent.parent
    scanner = PySkillScanner(str(skills_root))
    result = scanner.scan_skill_with_tools(skill_name)
    if not result:
        _save_cached_index(skill_name, scripts_path, signature, index)
        _record_phase(
            "runner.fast.load.index",
            (time.perf_counter() - started) * 1000,
            source="rust_scan",
            skill=skill_name,
            command_count=0,
            scan_duration_ms=round((time.perf_counter() - scan_started) * 1000, 2),
        )
        return index

    _meta, tools = result
    skill_prefix = f"{skill_name}."

    for i, tool in enumerate(tools):
        record = {
            "schema": COMMAND_INDEX_SCHEMA_V1,
            "tool_name": str(getattr(tool, "tool_name", "") or ""),
            "description": str(getattr(tool, "description", "") or ""),
            "skill_name": str(getattr(tool, "skill_name", "") or ""),
            "file_path": str(getattr(tool, "file_path", "") or ""),
            "function_name": str(getattr(tool, "function_name", "") or ""),
            "execution_mode": str(getattr(tool, "execution_mode", "") or ""),
            "keywords": list(getattr(tool, "keywords", []) or []),
            "input_schema": str(getattr(tool, "input_schema", "") or ""),
            "docstring": str(getattr(tool, "docstring", "") or ""),
            "file_hash": str(getattr(tool, "file_hash", "") or ""),
            "category": str(getattr(tool, "category", "") or ""),
        }
        validate_scanned_tool_record(record, index=i)

        raw_tool_name = record["tool_name"].strip()
        raw_file_path = record["file_path"].strip()
        if raw_tool_name.startswith(skill_prefix):
            command_name = raw_tool_name[len(skill_prefix) :]
        else:
            command_name = raw_tool_name
        if not command_name:
            continue

        file_path = Path(raw_file_path)
        candidates = [file_path]
        if not file_path.is_absolute():
            candidates.extend(
                [
                    skills_root / file_path,
                    scripts_path.parent / file_path,
                    Path.cwd() / file_path,
                ]
            )
        resolved = next((p for p in candidates if p.exists()), None)
        if resolved is None:
            continue
        index.setdefault(command_name, []).append(resolved)

    _save_cached_index(skill_name, scripts_path, signature, index)
    _record_phase(
        "runner.fast.load.index",
        (time.perf_counter() - started) * 1000,
        source="rust_scan",
        skill=skill_name,
        command_count=len(index),
        scan_duration_ms=round((time.perf_counter() - scan_started) * 1000, 2),
    )
    return index
