# Cognitive Re-anchoring Mechanism

## Overview

In long interactive sessions, Large Language Models (LLMs) often suffer from "context drift" or "protocol forgetting." Even if a skill's rules were initially loaded via `SKILL.md`, they can be diluted by extensive dialogue history, leading the LLM to revert to default (often unoptimized or unsafe) behaviors.

The **Cognitive Re-anchoring** mechanism in `omni-dev-fusion` solves this by transforming the Security Gatekeeper from a passive "permission checker" into an active "cognitive anchor."

## How It Works

### 1. Protocol Extraction

When a `UniversalScriptSkill` is loaded, it automatically splits the `SKILL.md` file into metadata (YAML) and **Protocol Content** (Markdown instructions).

### 2. Drift Detection

The `SecurityValidator` (Gatekeeper) monitors every tool call. If the LLM attempts to use a tool that is not authorized for the active skill (e.g., trying to use `terminal.run_command` instead of the mandated `git.smart_commit`), the Gatekeeper identifies this as a **Protocol Drift**.

### 3. Active Re-anchoring (Reactive)

Instead of returning a generic error, the Gatekeeper captures the `protocol_content` of the active skill and injects it into a `SecurityError`. This forces the LLM to re-read its instructions at the exact moment of failure.

### 4. Proactive Overload Management (Cognitive Load Control)

To support massive skill libraries (100-1000+ skills), the Gatekeeper tracks the number of **active skills** in the current session.

- **Threshold**: Defaults to 5 active skills.
- **Proactive Warning**: When the threshold is exceeded, even **successful** tool calls will include a `[COGNITIVE LOAD WARNING]`.
- **Injection Mechanism**:
  - For string results: Appended to the end.
  - For dictionary results: Injected into the `message` field or a specialized `_cognition` metadata field.
- **Reset**: Can be cleared via `validator.reset_active_skills()` during session cleanup.

## Advanced Permission Handling

The system supports **Wildcard Permission Projection**:

- `service:*`: Grants access to all methods in a service (e.g., `filesystem:*`).
- `service:method`: Specific method access.
- Correctly resolves both `:` (YAML standard) and `.` (MCP tool standard) delimiters.

## Technical Implementation

- **Security Module**: `packages/python/core/src/omni/core/security/__init__.py`
- **Universal Skills**: `packages/python/core/src/omni/core/skills/universal.py`
- **Kernel Dispatcher**: `packages/python/core/src/omni/core/kernel/engine.py` (Orchestrates the warning injection into tool results).
