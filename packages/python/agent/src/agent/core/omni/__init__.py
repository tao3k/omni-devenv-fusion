"""
agent/core/omni/__init__.py
Omni Loop Module - Modularized CCA Runtime Components.

Components:
- OmniLoop: Main CCA Loop Orchestrator
- ToolLoader: Rust tool loading and schema generation
- SkillInjector: Name Boosting + Hybrid Search skill injection
- LoopState: Session state tracking (visited/modified files)
- ActionGuard: Tool call interceptor for preventing redundant operations

Architecture:
- State Pattern: LoopState for session state management
- Interceptor Pattern: ActionGuard for tool call validation

Usage:
    from agent.core.omni import OmniLoop, run_sync
    from agent.core.omni import ToolLoader, get_tool_loader
    from agent.core.omni import SkillInjector, get_skill_injector
    from agent.core.omni import LoopState, ActionGuard
"""

from agent.core.omni.loop import OmniLoop, interactive_mode, run_sync
from agent.core.omni.tool_loader import ToolLoader, get_tool_loader
from agent.core.omni.skill_injector import SkillInjector, get_skill_injector
from agent.core.omni.state import LoopState
from agent.core.omni.interceptors import ActionGuard, NoOpGuard

__all__ = [
    "OmniLoop",
    "interactive_mode",
    "run_sync",
    "ToolLoader",
    "get_tool_loader",
    "SkillInjector",
    "get_skill_injector",
    "LoopState",
    "ActionGuard",
    "NoOpGuard",
]
