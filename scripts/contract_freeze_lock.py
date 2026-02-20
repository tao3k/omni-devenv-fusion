#!/usr/bin/env python3
"""Verify or update the A0 contract freeze lock file.

This lock file pins sha256 digests for contract-critical files:
- Omega and memory gate Rust contracts
- Xiuxian-Qianhuan injection contracts
- Canonical shared JSON schemas used by runtime traces
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Final

LOCK_VERSION: Final[int] = 1
HASH_ALGORITHM: Final[str] = "sha256"

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
LOCK_PATH: Final[Path] = PROJECT_ROOT / "packages/shared/schemas/contract-freeze.lock.json"

FROZEN_FILES: Final[tuple[str, ...]] = (
    "packages/rust/crates/omni-agent/src/contracts/omega.rs",
    "packages/rust/crates/omni-agent/src/contracts/memory_gate.rs",
    "packages/rust/crates/xiuxian-qianhuan/src/contracts/block.rs",
    "packages/rust/crates/xiuxian-qianhuan/src/contracts/policy.rs",
    "packages/rust/crates/xiuxian-qianhuan/src/contracts/snapshot.rs",
    "packages/shared/schemas/omni.discover.match.v1.schema.json",
    "packages/shared/schemas/omni.memory.gate_event.v1.schema.json",
    "packages/shared/schemas/omni.agent.route_trace.v1.schema.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_entries() -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for rel_path in sorted(FROZEN_FILES):
        abs_path = PROJECT_ROOT / rel_path
        if not abs_path.exists():
            raise FileNotFoundError(f"Frozen contract file missing: {rel_path}")
        entries.append({"path": rel_path, HASH_ALGORITHM: _sha256(abs_path)})
    return entries


def _read_lock() -> dict:
    if not LOCK_PATH.exists():
        raise FileNotFoundError(f"Lock file missing: {LOCK_PATH}")
    try:
        payload = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse lock file JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Lock file root must be an object")
    return payload


def _write_lock(entries: list[dict[str, str]]) -> None:
    payload = {
        "version": LOCK_VERSION,
        "algorithm": HASH_ALGORITHM,
        "entries": entries,
    }
    LOCK_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _verify_lock() -> int:
    expected = _read_lock()
    if int(expected.get("version", 0)) != LOCK_VERSION:
        print(
            f"[contract-freeze] lock version mismatch: {expected.get('version')} != {LOCK_VERSION}",
            file=sys.stderr,
        )
        return 1
    if str(expected.get("algorithm", "")) != HASH_ALGORITHM:
        print(
            f"[contract-freeze] lock algorithm mismatch: "
            f"{expected.get('algorithm')} != {HASH_ALGORITHM}",
            file=sys.stderr,
        )
        return 1

    expected_entries_raw = expected.get("entries")
    if not isinstance(expected_entries_raw, list):
        print("[contract-freeze] lock entries must be a list", file=sys.stderr)
        return 1

    expected_entries: dict[str, str] = {}
    for item in expected_entries_raw:
        if not isinstance(item, dict):
            print("[contract-freeze] invalid lock entry type", file=sys.stderr)
            return 1
        rel_path = item.get("path")
        digest = item.get(HASH_ALGORITHM)
        if not isinstance(rel_path, str) or not isinstance(digest, str):
            print("[contract-freeze] invalid lock entry shape", file=sys.stderr)
            return 1
        expected_entries[rel_path] = digest

    current_entries = _collect_entries()
    current_by_path = {entry["path"]: entry[HASH_ALGORITHM] for entry in current_entries}

    expected_paths = set(expected_entries)
    current_paths = set(current_by_path)
    missing = sorted(expected_paths - current_paths)
    extra = sorted(current_paths - expected_paths)
    mismatched = sorted(
        rel_path
        for rel_path in expected_paths & current_paths
        if expected_entries[rel_path] != current_by_path[rel_path]
    )

    if missing or extra or mismatched:
        print("[contract-freeze] lock verification failed", file=sys.stderr)
        if missing:
            print(f"  missing paths in current tree: {missing}", file=sys.stderr)
        if extra:
            print(f"  unexpected new paths: {extra}", file=sys.stderr)
        if mismatched:
            for rel_path in mismatched:
                print(
                    "  digest mismatch "
                    f"{rel_path}: expected={expected_entries[rel_path]} "
                    f"current={current_by_path[rel_path]}",
                    file=sys.stderr,
                )
        print(
            "Run `python3 scripts/contract_freeze_lock.py --update` "
            "only when contract changes are intentional.",
            file=sys.stderr,
        )
        return 1

    print(f"[contract-freeze] verified {len(current_entries)} locked files")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify/update A0 contract freeze lock")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Regenerate the lock file from current file digests",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify the lock file (default behavior)",
    )
    args = parser.parse_args()

    if args.update:
        entries = _collect_entries()
        _write_lock(entries)
        print(f"[contract-freeze] wrote lock with {len(entries)} entries -> {LOCK_PATH}")
        return 0

    return _verify_lock()


if __name__ == "__main__":
    raise SystemExit(main())
