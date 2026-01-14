#!/usr/bin/env python3
"""
scripts/test_omni_loop.py
Phase 56: The Omni Loop Integration Test.

Tests the complete CCA Runtime Integration with ContextOrchestrator and NoteTaker.
"""

from __future__ import annotations


def test_omni_agent_initialization():
    """Test that OmniAgent initializes correctly with all components."""
    from agent.core.omni_agent import OmniAgent

    agent = OmniAgent()
    assert agent.orchestrator is not None, "ContextOrchestrator should be initialized"
    assert agent.note_taker is not None, "NoteTaker should be initialized"
    assert agent.session_id is not None, "Session ID should be set"
    assert len(agent.orchestrator.layers) == 5, "Should have 5 context layers"


def test_cca_context_building():
    """Test that CCA context building works."""
    from agent.core.omni_agent import OmniAgent

    agent = OmniAgent()
    context = agent._build_cca_context("Fix the login bug in auth.py")

    assert len(context) > 0, "Context should not be empty"
    stats = agent.orchestrator.get_context_stats(context)
    assert stats["total_tokens"] > 0, "Should have token count"


def test_tool_loading():
    """Test that tools are loaded from skill registry."""
    from agent.core.omni_agent import OmniAgent

    agent = OmniAgent()
    agent._load_tools()

    # Just verify the method runs without error
    # Tool count depends on loaded skills
    assert isinstance(agent._tools, dict), "Tools should be a dict"


def test_completion_detection():
    """Test task completion detection."""
    from agent.core.omni_agent import OmniAgent

    agent = OmniAgent()

    assert agent._is_complete("TASK_COMPLETE") == True
    assert agent._is_complete("Done with the task") == True
    assert agent._is_complete("All done!") == True
    assert agent._is_complete("I'm still working on it") == False


def test_cli_entry_point():
    """Test CLI entry point module."""
    from agent.cli.omni_loop import main

    # Check main is callable
    assert callable(main), "main should be callable"


def test_run_sync_function():
    """Test the sync wrapper function."""
    from agent.core.omni_agent import run_sync

    assert callable(run_sync), "run_sync should be callable"
