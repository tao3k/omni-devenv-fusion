"""Pytest fixtures for memory module tests (Lance-only backend)."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from omni.foundation.services.memory.base import ProjectMemory


@pytest.fixture
def temp_dir():
    """Create a temporary directory for isolated memory storage."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp, ignore_errors=True)


@pytest.fixture
def memory_store(temp_dir):
    """Create a ProjectMemory instance (LanceDB backend)."""
    return ProjectMemory(dir_path=temp_dir)


@pytest.fixture
def populated_memory_store(memory_store):
    """Populate memory store with representative data."""
    memory_store.add_decision(
        title="Use LanceDB for Memory Storage",
        problem="Need structured persistence",
        solution="Use LanceDB tables",
        rationale="Efficient local querying",
        status="open",
    )
    memory_store.add_decision(
        title="Use Async IO",
        problem="Blocking path in handlers",
        solution="Adopt async where applicable",
        rationale="Reduce latency spikes",
        status="accepted",
    )
    memory_store.add_task(
        title="Implement Memory Migration",
        content="Migrate old markdown records",
        status="pending",
        assignee="Claude",
    )
    memory_store.add_task(
        title="Write Unit Tests",
        content="Add coverage for memory module",
        status="in_progress",
        assignee="Claude",
    )
    memory_store.save_context(
        {
            "files_tracked": 100,
            "active_skills": ["git", "memory"],
            "current_phase": "implementation",
        }
    )
    memory_store.update_status(
        phase="implementation",
        focus="writing tests",
        blockers="None",
        sentiment="Neutral",
    )
    return memory_store
