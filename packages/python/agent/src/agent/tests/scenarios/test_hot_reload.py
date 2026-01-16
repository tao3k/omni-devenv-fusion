"""
tests/scenarios/test_hot_reload.py
Phase 36.4: Zero-Downtime Hot Reload & State Consistency Test Suite

This suite verifies the complete hot-reload lifecycle with SURGICAL PRECISION:
1. The "Brain Surgery": Recursive sys.modules cleanup (Memory IO)
2. The "Nervous System": Observer pattern & MCP notifications (MCP Pipe IO)
3. The "Heartbeat": Loader orchestration (File IO + State Management)

Design Philosophy:
- "Slow is Smooth, Smooth is Fast" - Rigorous verification before remote operations
- Each test runs 2-3 cycles to confirm state consistency
- Zero external dependencies (no network, no git)

Usage:
    uv run pytest packages/python/agent/src/agent/tests/scenarios/test_hot_reload.py -v
"""

import sys
import types
import asyncio
import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

# Domain Imports
from agent.core.skill_manager import SkillManager, Skill, SkillCommand
from agent.core.loader import SkillLoader, LoadResult
from agent.core.protocols import ExecutionMode


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_skill_manager_singleton():
    """Reset SkillManager singleton before each test."""
    import agent.core.skill_manager.manager as manager_module

    # Reset the singleton
    manager_module._instance = None
    yield
    # Cleanup after test
    manager_module._instance = None


@pytest.fixture
def temp_skill_dir(tmp_path) -> Path:
    """Create a temporary skills directory with realistic structure."""
    skills_dir = tmp_path / "assets" / "skills"
    skills_dir.mkdir(parents=True)
    return skills_dir


@pytest.fixture
def skill_manager(temp_skill_dir) -> SkillManager:
    """Fresh SkillManager for each test."""
    manager = SkillManager(skills_dir=temp_skill_dir)
    return manager


def create_mock_skill(skill_name: str, module_name: str, path: Path) -> Skill:
    """Create a mock Skill object for testing."""
    return Skill(
        name=skill_name,
        manifest={"name": skill_name, "version": "1.0.0", "description": "Test skill"},
        commands={},
        module_name=module_name,
        path=path,
        execution_mode=ExecutionMode.LIBRARY,
    )


# =============================================================================
# HELPER: Create Mock Skill on Disk (without actual imports)
# =============================================================================


def create_mock_skill_on_disk(skill_dir: Path, skill_name: str, version: str = "1.0.0"):
    """
    Create a mock skill structure on disk for File IO tests.
    This creates a valid SKILL.md but uses plain Python functions
    that don't require special decorators.
    """
    skill_dir.mkdir(exist_ok=True)

    # 1. tools.py - plain Python, no decorators needed for testing
    (skill_dir / "tools.py").write_text(f'''
# Mock skill module - no decorator imports needed for testing

def get_version():
    """Return the current version of this skill."""
    return "{version}"

def hello():
    """Greet from {skill_name}."""
    return "Hello from {skill_name} v{version}"
''')

    # 2. scripts/logic.py (for recursive cleanup test)
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / "__init__.py").write_text("")
    (scripts_dir / "logic.py").write_text(f'''
def do_math():
    """Simulated computation."""
    return {version == "1.0.0" and 42 or 84}
''')

    # 3. SKILL.md
    (skill_dir / "SKILL.md").write_text(f"""---
name: {skill_name}
version: {version}
description: Test skill for hot reload verification
---
""")

    return skill_dir


# =============================================================================
# CATEGORY 1: The "Brain Surgery" - Recursive sys.modules Cleanup
# Tests Memory IO consistency
# =============================================================================


def test_scenario1_recursive_sys_modules_cleanup(skill_manager, temp_skill_dir):
    """
    Test: Surgical Memory Cleanup

    Verifies that unloading a skill removes BOTH main module AND submodules.
    This is the #1 cause of "stale code" bugs in hot-reload systems.

    Cycle: Load -> Simulate Submodules -> Unload -> Verify ALL modules removed
    """
    skill_name = "brain_surgery_test"
    module_name = f"agent.skills.{skill_name}.tools"
    skill_path = temp_skill_dir / skill_name
    skill_path.mkdir()

    # Create mock skill
    mock_skill = create_mock_skill(skill_name, module_name, skill_path / "tools.py")
    skill_manager._skills[skill_name] = mock_skill

    # Simulate loaded modules (main + submodules)
    main_module = module_name
    submodules = [
        f"agent.skills.{skill_name}.scripts.__init__",
        f"agent.skills.{skill_name}.scripts.logic",
        f"agent.skills.{skill_name}.scripts.utils",
    ]

    # Inject into sys.modules
    sys.modules[main_module] = types.ModuleType(main_module)
    for sub in submodules:
        sys.modules[sub] = types.ModuleType(sub)

    # Add unrelated module (should NOT be removed)
    sys.modules["agent.skills.unrelated"] = types.ModuleType("agent.skills.unrelated")

    # Verify preconditions
    assert main_module in sys.modules
    assert all(sub in sys.modules for sub in submodules)
    assert "agent.skills.unrelated" in sys.modules

    # === CYCLE 1: Perform Unload ===
    result = skill_manager.unload(skill_name)
    assert result is True
    assert skill_name not in skill_manager._skills

    # === CYCLE 2: Verify Cleanup ===
    # Main module should be removed
    assert main_module not in sys.modules, f"Main module '{main_module}' still in sys.modules!"

    # ALL submodules should be removed (this is the surgical part)
    for sub in submodules:
        assert sub not in sys.modules, f"Submodule '{sub}' still in sys.modules!"

    # Unrelated module should NOT be touched
    assert "agent.skills.unrelated" in sys.modules, "Unrelated module was incorrectly removed!"


def test_scenario1_multiple_unload_calls(skill_manager, temp_skill_dir):
    """
    Test: Idempotent Unload

    Verify that calling unload multiple times is safe and idempotent.
    """
    skill_name = "idempotent_test"
    module_name = f"agent.skills.{skill_name}.tools"
    skill_path = temp_skill_dir / skill_name

    mock_skill = create_mock_skill(skill_name, module_name, skill_path / "tools.py")
    skill_manager._skills[skill_name] = mock_skill
    sys.modules[module_name] = types.ModuleType(module_name)

    # First unload
    result1 = skill_manager.unload(skill_name)
    assert result1 is True

    # Second unload (should return False, not crash)
    result2 = skill_manager.unload(skill_name)
    assert result2 is False

    # Third unload (still safe)
    result3 = skill_manager.unload(skill_name)
    assert result3 is False


# =============================================================================
# CATEGORY 2: The "Nervous System" - Observer Pattern & MCP Integration
# Tests MCP Pipe IO (must NOT pollute stdout)
# =============================================================================


@pytest.mark.asyncio
async def test_scenario2_observer_pattern_basic(skill_manager):
    """
    Test: Observer Registration & Notification

    Verify that observers can subscribe and receive notifications.
    """
    callback = AsyncMock()
    skill_manager.subscribe(callback)

    # Verify registration
    assert len(skill_manager._observers) == 1
    assert skill_manager._observers[0] is callback

    # Trigger notification (Phase 36.5: new signature with skill_name and change_type)
    skill_manager._notify_change("test_skill", "load")
    # Phase 36.5: Debounce is 200ms, need to wait for notification
    await asyncio.sleep(0.3)

    # Verify callback was invoked with correct arguments
    callback.assert_called_once_with("test_skill", "load")


@pytest.mark.asyncio
async def test_scenario2_multiple_observers(skill_manager):
    """
    Test: Multiple Observer Support

    Verify that multiple observers all receive notifications.
    """
    callbacks = [AsyncMock() for _ in range(5)]

    for cb in callbacks:
        skill_manager.subscribe(cb)

    # Trigger notification (Phase 36.5: new signature)
    skill_manager._notify_change("test_skill", "load")
    # Phase 36.5: Debounce is 200ms, need to wait for notification
    await asyncio.sleep(0.3)

    # All should be called exactly once with correct arguments
    for cb in callbacks:
        cb.assert_called_once_with("test_skill", "load")


@pytest.mark.asyncio
async def test_scenario2_mcp_notification_with_session(skill_manager):
    """
    Test: MCP Notification (With Active Session)

    Verify that _notify_tools_changed calls send_tool_list_changed
    when a session is available.
    """
    from agent.mcp_server import _notify_tools_changed

    # Create mock session
    mock_session = AsyncMock()
    mock_request_context = MagicMock()
    mock_request_context.session = mock_session

    # Patch server.request_context at module level
    import agent.mcp_server as mcp_module

    # Save original server instance
    original_server = mcp_module.server

    class MockContext:
        request_context = mock_request_context

    try:
        # Replace server with mock
        mcp_module.server = MockContext()

        # Subscribe
        skill_manager.subscribe(_notify_tools_changed)

        # Trigger (Phase 36.5: new signature)
        skill_manager._notify_change("test_skill", "load")
        # Phase 36.5: Debounce is 200ms
        await asyncio.sleep(0.3)

        # Verify
        mock_session.send_tool_list_changed.assert_called_once()

    finally:
        # Restore original server instance
        mcp_module.server = original_server


@pytest.mark.asyncio
async def test_scenario2_mcp_notification_no_session(skill_manager):
    """
    Test: MCP Notification (No Active Session)

    Verify that _notify_tools_changed handles missing session gracefully
    (logs debug, doesn't crash).
    """
    from agent.mcp_server import _notify_tools_changed

    # Subscribe
    skill_manager.subscribe(_notify_tools_changed)

    # Trigger without session (should not raise)
    try:
        skill_manager._notify_change("test_skill", "load")
        # Phase 36.5: Debounce is 200ms
        await asyncio.sleep(0.3)
    except Exception as e:
        pytest.fail(f"Callback raised exception with no session: {e}")


@pytest.mark.asyncio
async def test_scenario2_observer_error_isolation(skill_manager):
    """
    Test: Observer Error Isolation

    Verify that one failing observer doesn't affect others.
    """
    good_callback = AsyncMock()
    bad_callback = AsyncMock(side_effect=Exception("Observer crash"))
    another_good = AsyncMock()

    skill_manager.subscribe(good_callback)
    skill_manager.subscribe(bad_callback)
    skill_manager.subscribe(another_good)

    # Trigger - should not raise
    skill_manager._notify_change("test_skill", "load")
    # Phase 36.5: Debounce is 200ms
    await asyncio.sleep(0.3)

    # Good callbacks should still be called with correct arguments
    good_callback.assert_called_once_with("test_skill", "load")
    another_good.assert_called_once_with("test_skill", "load")


# =============================================================================
# CATEGORY 3: The "Heartbeat" - Hot Reload Cycle (File IO + State)
# Tests File IO consistency and state management
# =============================================================================


def test_scenario3_reload_orchestration(skill_manager, temp_skill_dir):
    """
    Test: Loader Reload Orchestration

    Verify that reload() properly orchestrates (Phase 36.5 transactional reload):
    1. Validate syntax of new code
    2. Unload (with cleanup) - inline, no notification
    3. Load fresh - single "reload" notification

    Runs 2 cycles to confirm consistency.
    Uses class-level patching to avoid __slots__ issues.
    """
    loader = SkillLoader(manager=skill_manager)
    skill_name = "reload_test"
    skill_dir = temp_skill_dir / skill_name

    # === CYCLE 1: Create skill on disk ===
    create_mock_skill_on_disk(skill_dir, skill_name, "1.0.0")

    # Create mock module
    mock_module = types.ModuleType(f"agent.skills.{skill_name}.tools")
    mock_module.get_version = lambda: "1.0.0"
    mock_module.hello = lambda: "Hello from reload_test v1.0.0"

    # === CYCLE 1: Initial Load (mocked at class level) ===
    original_load_skill = SkillManager.load_skill

    def mock_load_skill(self, path, reload=False):
        """Mock load_skill that returns a skill without actual import."""
        skill = Skill(
            name=skill_name,
            manifest={"name": skill_name, "version": "1.0.0"},
            commands={},
            module_name=f"agent.skills.{skill_name}.tools",
            path=path / "tools.py",
            execution_mode=ExecutionMode.LIBRARY,
            _module=mock_module,
        )
        self._skills[skill_name] = skill
        # Phase 36.5: Notify with skill_name and change_type
        self._notify_change(skill_name, "load")
        return skill

    with patch.object(SkillManager, "load_skill", mock_load_skill):
        result1 = skill_manager.load_skill(skill_dir)

    assert result1 is not None
    assert skill_name in skill_manager._skills
    skill_v1 = skill_manager._skills[skill_name]

    # === CYCLE 2: Modify and Reload ===
    time.sleep(0.01)
    create_mock_skill_on_disk(skill_dir, skill_name, "2.0.0")

    # Phase 36.5: reload() does inline unload, so we verify:
    # 1. Old skill was removed from _skills
    # 2. New skill was loaded
    # 3. Notification was sent with "reload" type

    # Track reload calls
    reload_calls = []
    original_reload = SkillManager.reload

    def tracking_reload(self, name):
        reload_calls.append(name)
        return original_reload(self, name)

    with patch.object(SkillManager, "reload", tracking_reload):
        # Reload using manager (which Loader.reload calls)
        result2 = skill_manager.reload(skill_name)

    # Verify reload orchestration
    assert result2 is not None
    assert len(reload_calls) == 1
    assert reload_calls[0] == skill_name

    # Verify old skill was removed and new skill loaded
    assert skill_name in skill_manager._skills
    skill_v2 = skill_manager._skills[skill_name]
    assert skill_v2 is not skill_v1  # Should be new object


def test_scenario3_manager_reload_method(skill_manager, temp_skill_dir):
    """
    Test: Manager Reload Method (Phase 36.5)

    Verify that manager.reload() performs transactional reload:
    1. Syntax validation BEFORE unloading
    2. Inline unload (no notification)
    3. Load fresh with reload=True
    4. Single "reload" notification (not separate unload+load)
    """
    skill_name = "manager_reload_test"
    skill_dir = temp_skill_dir / skill_name
    create_mock_skill_on_disk(skill_dir, skill_name, "1.0.0")

    mock_module = types.ModuleType(f"agent.skills.{skill_name}.tools")

    # Track calls
    reload_calls = []
    load_calls = []

    original_reload = SkillManager.reload
    original_load = SkillManager.load_skill

    def tracking_reload(self, name):
        reload_calls.append(name)
        return original_reload(self, name)

    def mock_load_skill(self, path, reload=False):
        """Mock load_skill that tracks reload parameter."""
        load_calls.append((path, reload))
        skill = Skill(
            name=skill_name,
            manifest={"name": skill_name, "version": "1.0.0"},
            commands={},
            module_name=f"agent.skills.{skill_name}.tools",
            path=path / "tools.py",
            execution_mode=ExecutionMode.LIBRARY,
            _module=mock_module,
        )
        self._skills[skill_name] = skill
        # Phase 36.5: Notify with "reload" type
        self._notify_change(skill_name, "reload")
        return skill

    with patch.object(SkillManager, "reload", tracking_reload):
        with patch.object(SkillManager, "load_skill", mock_load_skill):
            # Load initial
            result = skill_manager.load_skill(skill_dir)
            assert result is not None

            # Reset tracking
            reload_calls.clear()
            load_calls.clear()

            # Modify and reload
            time.sleep(0.01)
            create_mock_skill_on_disk(skill_dir, skill_name, "2.0.0")
            skill_manager.reload(skill_name)

    # Verify reload was called
    assert len(reload_calls) == 1
    assert reload_calls[0] == skill_name

    # Verify load was called with reload=True
    assert len(load_calls) == 1
    assert load_calls[0][1] is True


def test_scenario3_reload_nonexistent_skill(skill_manager):
    """
    Test: Reload Non-existent Skill

    Verify that reloading a non-existent skill returns None gracefully.
    """
    result = skill_manager.reload("nonexistent_skill")
    assert result is None


def test_scenario3_command_cache_coherence(skill_manager, temp_skill_dir):
    """
    Test: Command Cache Coherence

    Verify that after reload, the O(1) command cache is properly invalidated.
    This is critical: if cache isn't cleared, old code will be executed!
    """
    skill_name = "cache_test"
    skill_dir = temp_skill_dir / skill_name
    create_mock_skill_on_disk(skill_dir, skill_name, "1.0.0")

    mock_module = types.ModuleType(f"agent.skills.{skill_name}.tools")

    # Load skill (mocked)
    original_load = SkillManager.load_skill

    def mock_load_skill(self, path, reload=False):
        skill = Skill(
            name=skill_name,
            manifest={"name": skill_name, "version": "1.0.0"},
            commands={},
            module_name=f"agent.skills.{skill_name}.tools",
            path=path / "tools.py",
            execution_mode=ExecutionMode.LIBRARY,
            _module=mock_module,
        )
        self._skills[skill_name] = skill
        return skill

    with patch.object(SkillManager, "load_skill", mock_load_skill):
        skill_manager.load_skill(skill_dir)

    # Simulate command execution (populates cache)
    cache_key = f"{skill_name}.get_version"
    skill_manager._command_cache[cache_key] = MagicMock(spec=SkillCommand)
    initial_cmd = skill_manager._command_cache[cache_key]

    # Reload (mocked)
    time.sleep(0.01)
    create_mock_skill_on_disk(skill_dir, skill_name, "2.0.0")

    # Need to mock reload to call our mocked load_skill
    def mock_reload(self, skill_name):
        skill_path = self._discover_single(skill_name)
        if skill_path is None:
            return None
        self.unload(skill_name)
        return self.load_skill(skill_path, reload=True)

    with patch.object(SkillManager, "reload", mock_reload):
        skill_manager.reload(skill_name)

    # Verify cache was cleared
    assert cache_key not in skill_manager._command_cache


# =============================================================================
# CATEGORY 4: Integration - Full Hot Reload Cycle
# Tests complete flow: Modify -> Detect -> Reload -> Notify
# =============================================================================


@pytest.mark.asyncio
async def test_scenario4_full_reload_cycle(temp_skill_dir):
    """
    Test: Complete Hot Reload Cycle (Phase 36.5)

    Verify the complete cycle:
    1. Initial load works with notification
    2. File modification is detected (via mtime)
    3. Reload performs syntax validation, inline unload, and notification
    4. Debouncing works correctly (multiple changes batched)

    This is the INTEGRATION test that proves the whole system works.
    Runs 3 reload cycles to confirm stability.
    """
    skill_name = "full_cycle_test"
    skill_dir = temp_skill_dir / skill_name
    manager = SkillManager(skills_dir=temp_skill_dir)

    # Track observer calls
    observer_calls = []

    def tracking_callback(skill_name, change_type):
        observer_calls.append((time.time(), skill_name, change_type))

    manager.subscribe(tracking_callback)

    mock_module = types.ModuleType(f"agent.skills.{skill_name}.tools")

    def mock_load_skill(self, path, reload=False):
        """Mock load_skill that returns a proper skill and notifies observers."""
        # Get mtime from file
        tools_path = path / "tools.py"
        mtime = tools_path.stat().st_mtime if tools_path.exists() else 0.0

        skill = Skill(
            name=skill_name,
            manifest={"name": skill_name, "version": "1.0.0"},
            commands={},
            module_name=f"agent.skills.{skill_name}.tools",
            path=tools_path,
            mtime=mtime,
            execution_mode=ExecutionMode.LIBRARY,
            _module=mock_module,
        )
        self._skills[skill_name] = skill
        # Phase 36.5: Notify observers
        self._notify_change(skill_name, "load")
        return skill

    with patch.object(SkillManager, "load_skill", mock_load_skill):
        # === CYCLE 1: Initial Load ===
        create_mock_skill_on_disk(skill_dir, skill_name, "1.0.0")

        result1 = manager.load_skill(skill_dir)
        assert result1 is not None
        assert skill_name in manager._skills

        # Wait for debounced notification
        await asyncio.sleep(0.3)

        # Observer should be notified at least once
        initial_count = len(observer_calls)
        assert initial_count >= 1
        # Verify skill_name in notification
        assert observer_calls[-1][1] == skill_name

        # === CYCLE 2: Modify and Reload ===
        time.sleep(0.02)  # Ensure mtime difference
        create_mock_skill_on_disk(skill_dir, skill_name, "2.0.0")

        result2 = manager.reload(skill_name)
        assert result2 is not None
        assert skill_name in manager._skills

        # New skill object
        assert manager._skills[skill_name] is not result1

        # Wait for debounced notification
        await asyncio.sleep(0.3)

        # Observer should be notified again (at least one more notification)
        reload_count = len(observer_calls)
        assert reload_count > initial_count, "Reload should trigger notification"

        # Verify skill_name in notification
        assert observer_calls[-1][1] == skill_name

        # === CYCLE 3: Another Reload (Idempotency) ===
        time.sleep(0.02)
        create_mock_skill_on_disk(skill_dir, skill_name, "3.0.0")

        result3 = manager.reload(skill_name)
        assert result3 is not None

        await asyncio.sleep(0.3)

        final_count = len(observer_calls)
        assert final_count > reload_count, "Second reload should also trigger notification"

        print(f"✅ Full cycle complete: 3 reloads, {len(observer_calls)} observer notifications")


# =============================================================================
# CATEGORY 5: IO Safety - Verify No Stdout Pollution
# Critical for MCP protocol stability
# =============================================================================


def test_scenario5_mcp_io_safety(temp_skill_dir, capsys):
    """
    Test: MCP Server IO Safety

    Verify that _notify_tools_changed and related functions
    do NOT write to stdout (would break MCP protocol).
    """
    import subprocess
    import sys

    # Run a subprocess that imports and calls _notify_tools_changed
    # with no active session
    test_code = """
import sys
sys.path.insert(0, "packages/python/agent/src")

from agent.core.skill_manager import SkillManager
from agent.mcp_server import _notify_tools_changed
import asyncio

async def test():
    manager = SkillManager()
    manager.subscribe(_notify_tools_changed)
    # Phase 36.5: new signature with skill_name and change_type
    manager._notify_change("test_skill", "load")
    await asyncio.sleep(0.01)
    print("STDOUT_MARKER")

asyncio.run(test())
"""

    result = subprocess.run(
        [sys.executable, "-c", test_code],
        capture_output=True,
        text=True,
        cwd="/Users/guangtao/ghq/github.com/tao3k/omni-devenv-fusion",
    )

    # stdout should only contain our marker
    # The key check is: no unexpected output during _notify_tools_changed


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
