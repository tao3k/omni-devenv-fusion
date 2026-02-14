"""Shared fixtures for router integration tests (route_hybrid with real skills index)."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def router_lance_path():
    """Isolated vector store path; routing uses the skills table in this store."""
    temp_dir = tempfile.mkdtemp(prefix="skills-integration-")
    try:
        yield str(Path(temp_dir))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def sync_router_from_skills_async(storage_path: str) -> dict[str, int | str]:
    """Populate the skills table in the given store from assets/skills (routing reads from skills)."""
    from omni.foundation.bridge import RustVectorStore
    from omni.foundation.config.skills import SKILLS_DIR

    skills_path = SKILLS_DIR()
    if not skills_path.exists():
        return {"status": "error", "error": "skills path not found", "tools_indexed": 0}

    store = RustVectorStore(storage_path, enable_keyword_index=True)
    skills_count, _ = await store.index_skill_tools_dual(str(skills_path), "skills", "skills")
    return {"status": "success", "skills_indexed": skills_count, "tools_indexed": skills_count}


@pytest.fixture(scope="module")
def router_for_integration(router_lance_path):
    """Create a router for integration tests."""
    from omni.core.router.main import OmniRouter, RouterRegistry

    RouterRegistry.reset_all()
    router = OmniRouter(storage_path=router_lance_path)
    yield router
    RouterRegistry.reset_all()
