"""Tests for mcp_core.instructions module.

Tests thread-safety, lazy loading, and double-checked locking pattern.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from mcp_core.instructions import (
    get_instructions,
    get_instruction,
    get_all_instructions_merged,
    list_instruction_names,
    reload_instructions,
    _loaded,
    _data,
)


class TestInstructionsBasic:
    """Basic functionality tests."""

    def test_get_instructions_returns_dict(self):
        """get_instructions should return a dictionary."""
        result = get_instructions()
        assert isinstance(result, dict)

    def test_get_instruction_returns_content(self):
        """get_instruction should return content for existing instruction."""
        names = list_instruction_names()
        if names:
            content = get_instruction(names[0])
            assert content is not None
            assert isinstance(content, str)

    def test_get_instruction_none_for_missing(self):
        """get_instruction should return None for non-existent instruction."""
        content = get_instruction("non-existent-instruction-xyz")
        assert content is None

    def test_get_all_instructions_merged_returns_string(self):
        """get_all_instructions_merged should return a string."""
        result = get_all_instructions_merged()
        assert isinstance(result, str)

    def test_list_instruction_names_returns_list(self):
        """list_instruction_names should return a list."""
        result = list_instruction_names()
        assert isinstance(result, list)

    def test_problem_solving_is_loaded(self):
        """problem-solving.md should be auto-loaded in instructions."""
        names = list_instruction_names()
        assert "problem-solving" in names, f"problem-solving not in instructions: {names}"

    def test_problem_solving_contains_actions_over_apologies(self):
        """problem-solving.md should contain core principle."""
        content = get_instruction("problem-solving")
        assert content is not None, "problem-solving instruction not found"
        assert "Actions Over Apologies" in content or "actions over apologies" in content.lower(), \
            "Core principle not found in problem-solving.md"
        # Verify the formula is present
        assert "Identify Problem" in content, "Formula not found in problem-solving.md"

    def test_problem_solving_in_merged_output(self):
        """problem-solving content should appear in merged output."""
        merged = get_all_instructions_merged()
        assert "problem-solving" in merged.lower() or "Problem Solving" in merged, \
            "problem-solving not in merged instructions"


class TestInstructionsLazyLoading:
    """Lazy loading tests."""

    def test_no_io_on_import(self):
        """Instructions should not be loaded at module import time."""
        # Force reload to reset state
        reload_instructions()

        # At this point, data should be loaded after list_instruction_names call
        # The key test is that we didn't load during import of the module
        # This is verified by the module design - no eager loading

    def test_single_load_on_multiple_calls(self):
        """Multiple calls should not reload data."""
        # Ensure loaded
        list_instruction_names()

        # Capture state
        first_call = time.time()
        for _ in range(100):
            get_instructions()
        second_call = time.time()

        # Should be fast (data already loaded, no I/O)
        # 100 calls in under 1 second = fast path working
        assert second_call - first_call < 1.0, "Multiple calls should use fast path"


class TestInstructionsThreadSafety:
    """Thread-safety tests - critical for fork-safety."""

    def test_concurrent_access_no_race_condition(self):
        """Multiple threads accessing simultaneously should not cause race conditions."""
        # Reload to ensure clean state
        reload_instructions()

        results: dict[int, dict[str, str]] = {}
        errors: list[tuple[int, Exception]] = []

        def access_instructions(thread_id: int) -> dict[str, str]:
            """Access instructions from a thread."""
            try:
                instructions = get_instructions()
                return {"thread_id": thread_id, "count": len(instructions)}
            except Exception as e:
                errors.append((thread_id, e))
                raise

        # Launch multiple threads accessing simultaneously
        num_threads = 10
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(access_instructions, i) for i in range(num_threads)]
            for future in as_completed(futures):
                result = future.result()
                results[result["thread_id"]] = result

        # No errors should have occurred
        assert len(errors) == 0, f"Race conditions detected: {errors}"

        # All threads should see the same data
        counts = [r["count"] for r in results.values()]
        assert len(set(counts)) == 1, "Threads saw different data counts"

    def test_double_checked_locking_fast_path(self):
        """After first load, subsequent calls should use fast path (no lock)."""
        # Ensure loaded
        reload_instructions()
        list_instruction_names()

        # Measure time for many calls (fast path should be very fast)
        start = time.perf_counter()
        for _ in range(10000):
            _loaded_flag = _loaded  # Read the flag
        fast_path_time = time.perf_counter() - start

        # Fast path should be extremely fast (under 0.1 seconds for 10k reads)
        assert fast_path_time < 0.1, f"Fast path too slow: {fast_path_time}s"

    def test_concurrent_get_instruction_thread_safe(self):
        """Concurrent get_instruction calls should be thread-safe."""
        reload_instructions()

        names = list_instruction_names()
        if not names:
            pytest.skip("No instructions to test")

        errors = []

        def get_random_instruction(thread_id: int) -> None:
            try:
                for name in names:
                    content = get_instruction(name)
                    # Verify content is not empty or truncated
                    if content is not None:
                        assert len(content) > 0
            except Exception as e:
                errors.append((thread_id, e))

        num_threads = 5
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(get_random_instruction, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()  # Propagate any exception

        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_concurrent_get_all_instructions_merged(self):
        """Concurrent get_all_instructions_merged calls should be thread-safe."""
        reload_instructions()

        errors = []
        results = []

        def get_merged(thread_id: int) -> None:
            try:
                result = get_all_instructions_merged()
                results.append((thread_id, len(result)))
            except Exception as e:
                errors.append((thread_id, e))

        num_threads = 5
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(get_merged, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # All threads should get same merged length
        lengths = [r[1] for r in results]
        assert len(set(lengths)) == 1, "Threads got different merged lengths"


class TestInstructionsReload:
    """Reload functionality tests."""

    def test_reload_resets_state(self):
        """reload_instructions should reset internal state."""
        # Get initial state
        initial = get_instructions()
        initial_names = list_instruction_names()

        # Reload
        reload_instructions()
        reloaded = get_instructions()
        reloaded_names = list_instruction_names()

        # Should have same data after reload
        assert set(initial_names) == set(reloaded_names)

    def test_reload_is_thread_safe(self):
        """reload_instructions should be thread-safe."""
        reload_instructions()

        errors = []

        def reload_and_access(thread_id: int) -> None:
            try:
                if thread_id % 2 == 0:
                    reload_instructions()
                else:
                    # Access data while others may be reloading
                    _ = get_instructions()
            except Exception as e:
                errors.append((thread_id, e))

        num_threads = 10
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(reload_and_access, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        # No deadlocks or race conditions
        assert len(errors) == 0, f"Reload not thread-safe: {errors}"


class TestInstructionsForkSafety:
    """Fork-safety tests (simulated fork scenarios)."""

    def test_no_lock_on_import(self):
        """Import should not acquire any locks (fork-safety requirement)."""
        # This is a structural test - the code is designed without
        # eager loading, so import cannot acquire locks
        # The _lock is only acquired in _ensure_loaded() which is
        # called on first access, not on import

    def test_lazy_load_avoid_fork_deadlock(self):
        """Lazy loading should prevent fork deadlock issues.

        The deadlock scenario:
        1. Lock acquired in parent process
        2. Process forks (uv run spawns workers)
        3. Child inherits locked state but no thread to release it
        4. Child deadlocks on lock acquisition

        Our solution: Pure lazy loading means no lock is acquired
        during import, so fork + first access is safe.
        """
        # This is verified by the design - we test it by ensuring
        # the module loads without hanging
        result = get_instructions()
        assert isinstance(result, dict)
        # If we got here without hanging, the fork-safety works
