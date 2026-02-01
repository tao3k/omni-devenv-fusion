"""Pytest fixtures for memory module tests."""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from omni.foundation.services.memory.base import (
    STORAGE_MODE_FILE,
    STORAGE_MODE_LANCE,
    ProjectMemory,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for memory storage."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp, ignore_errors=True)


@pytest.fixture
def memory_file_mode(temp_dir):
    """Create a ProjectMemory instance in file mode."""
    memory = ProjectMemory(dir_path=temp_dir, storage_mode=STORAGE_MODE_FILE)
    yield memory


@pytest.fixture
def memory_lance_mode(temp_dir):
    """Create a ProjectMemory instance in LanceDB mode."""
    memory = ProjectMemory(dir_path=temp_dir, storage_mode=STORAGE_MODE_LANCE)
    yield memory


@pytest.fixture
def sample_decision():
    """Sample decision data for testing."""
    return {
        "title": "Use LanceDB for Memory Storage",
        "problem": "File-based storage is slow for large datasets",
        "solution": "Migrate to LanceDB for better performance",
        "rationale": "LanceDB provides efficient structured data storage with ACID guarantees",
        "status": "open",
    }


@pytest.fixture
def sample_task():
    """Sample task data for testing."""
    return {
        "title": "Implement Memory Migration",
        "content": "Create migration script from file to LanceDB",
        "status": "pending",
        "assignee": "Claude",
    }


@pytest.fixture
def sample_context():
    """Sample context data for testing."""
    return {
        "files_tracked": 100,
        "active_skills": ["git", "memory"],
        "current_phase": "implementation",
    }


@pytest.fixture
def populated_memory_file_mode(temp_dir, sample_decision, sample_task, sample_context):
    """Create a populated ProjectMemory instance in file mode."""
    memory = ProjectMemory(dir_path=temp_dir, storage_mode=STORAGE_MODE_FILE)

    # Add decisions
    memory.add_decision(
        title=sample_decision["title"],
        problem=sample_decision["problem"],
        solution=sample_decision["solution"],
        rationale=sample_decision["rationale"],
        status=sample_decision["status"],
    )

    # Add multiple decisions
    memory.add_decision(
        title="Use Async IO",
        problem="Synchronous IO blocks the event loop",
        solution="Use asyncio for all I/O operations",
        rationale="Better performance and responsiveness",
        status="accepted",
    )

    # Add tasks
    memory.add_task(
        title=sample_task["title"],
        content=sample_task["content"],
        status=sample_task["status"],
        assignee=sample_task["assignee"],
    )

    # Add more tasks
    memory.add_task(
        title="Write Unit Tests",
        content="Create comprehensive unit tests",
        status="in_progress",
        assignee="Claude",
    )

    # Save context
    memory.save_context(sample_context)

    # Update status
    memory.update_status(
        phase="implementation",
        focus="writing tests",
        blockers="None",
        sentiment="Neutral",
    )

    return memory


@pytest.fixture
def populated_memory_lance_mode(temp_dir, sample_decision, sample_task, sample_context):
    """Create a populated ProjectMemory instance in LanceDB mode."""
    memory = ProjectMemory(dir_path=temp_dir, storage_mode=STORAGE_MODE_LANCE)

    # Add decisions
    memory.add_decision(
        title=sample_decision["title"],
        problem=sample_decision["problem"],
        solution=sample_decision["solution"],
        rationale=sample_decision["rationale"],
        status=sample_decision["status"],
    )

    # Add multiple decisions
    memory.add_decision(
        title="Use Async IO",
        problem="Synchronous IO blocks the event loop",
        solution="Use asyncio for all I/O operations",
        rationale="Better performance and responsiveness",
        status="accepted",
    )

    # Add tasks
    memory.add_task(
        title=sample_task["title"],
        content=sample_task["content"],
        status=sample_task["status"],
        assignee=sample_task["assignee"],
    )

    # Add more tasks
    memory.add_task(
        title="Write Unit Tests",
        content="Create comprehensive unit tests",
        status="in_progress",
        assignee="Claude",
    )

    # Save context
    memory.save_context(sample_context)

    # Update status
    memory.update_status(
        phase="implementation",
        focus="writing tests",
        blockers="None",
        sentiment="Neutral",
    )

    return memory
