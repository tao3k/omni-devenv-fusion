# Phase 42: State-Aware Routing

**Status**: Implemented
**Date**: 2025-01-13
**Related**: Phase 41 (Wisdom-Aware Routing)

## Overview

State-Aware Routing extends the Semantic Router with real-time environment state detection to prevent hallucinated actions and ground routing decisions in current reality.

## Problem Statement

The Semantic Router sometimes generates Mission Briefs that don't account for the current state of the development environment:

- **Git State**: Router doesn't know if there are uncommitted changes, which branch we're on, or what files are modified
- **Active Context**: Router has no awareness of what the user was recently working on (SCRATCHPAD.md)
- **Hallucination Risk**: Router might suggest actions that conflict with current reality (e.g., "commit your changes" when no changes exist)

## Solution: ContextSniffer

A new `ContextSniffer` class provides real-time environment snapshots:

```
ContextSniffer
├── _get_git_status(): Branch + modified files
├── _get_active_files(): SCRATCHPAD.md content
└── get_snapshot(): Parallel snapshot of all state
```

### Git Status Detection

```python
async def _get_git_status(self) -> str:
    # Returns: "Branch: main | Modified: 5 files (M src/a.py, ...)"
```

Detects:
- Current branch name
- Number of modified files
- Up to 3 modified file names (with +N more indicator)

### Active Context Detection

```python
async def _get_active_files(self) -> str:
    # Returns: "Active Context: 42 lines in SCRATCHPAD.md"
```

Reads `.memory/active_context/SCRATCHPAD.md` for user focus context.

## Integration with Semantic Router

### Three-Way Parallel Context Gathering

```
route(user_query)
    ├── menu_task: Build routing menu (blocking, ~5ms)
    ├── wisdom_task: Query harvested lessons (parallel, ~50ms)
    └── sniffer_task: Get environment snapshot (parallel, ~10ms)
```

### Updated System Prompt

```python
system_prompt = f"""
...

[Phase 42] CURRENT ENVIRONMENT STATE:
{env_snapshot}

ROUTING RULES:
...

[Phase 42] ENVIRONMENT-AWARE RULES:
- If user asks to "commit" and modified files are shown, include modified files in brief
- If workspace has uncommitted changes that might be relevant, acknowledge them in brief
- Use the git branch/status info to contextualize routing decisions
"""
```

## Files Modified

| File | Change |
|------|--------|
| `agent/core/router/sniffer.py` | NEW - ContextSniffer class |
| `agent/core/router/semantic_router.py` | Added sniffer integration, three-way parallel |
| `agent/core/router/models.py` | Added `env_snapshot` field to RoutingResult |
| `agent/cli/commands/route.py` | Display environment snapshot in CLI |

## Usage Example

```bash
$ omni route invoke "commit my changes" --verbose

# Output shows:
# ╭──────────────────────── [Phase 42] Environment State ────────────────────────╮
# │ [ENVIRONMENT STATE]                                                          │
# │ - Branch: main | Modified: 51 files (...)                                    │
# │ - Active Context: Empty                                                      │
# ╰──────────────────────────────────────────────────────────────────────────────╯
```

## Benefits

1. **Prevents Hallucination**: Router knows current state before suggesting actions
2. **Contextual Routing**: Can reference modified files, branch context in Mission Brief
3. **Zero Latency Impact**: Parallel execution adds <10ms to routing
4. **Debuggability**: Users can see what the router "sees" in their environment

## Future Enhancements

- Detect running processes/services
- Read `.env` for configuration context
- Check for uncommitted credentials (security)
- Integration with terminal/IDE for deeper context
