# Cognitive Re-anchoring via Gatekeeper V2

> **Category**: ARCHITECTURE | **Date**: 2026-01-28

# Skill Protocol Re-anchoring & Gatekeeper V2

## Concept

Transforming the Security Gatekeeper into a cognitive steering mechanism to prevent LLM protocol forgetting in long sessions.

## Key Features

- **Protocol Injection**: Automatically extract instructions from `SKILL.md` and inject them into security error messages when drift is detected.
- **Cognitive Drift Detection**: Identify when an LLM attempts to bypass skill-specific tools (e.g., using raw shell instead of MCP tools).
- **Active Overload Management**: Monitor active skill count and provide warnings when context clutter exceeds the cognitive threshold (default: 5 skills).

## Implementation Details

- `SecurityValidator` tracks `active_skills` and `failure_counts`.
- `UniversalScriptSkill.protocol_content` provides the raw Markdown guidance.
- `Kernel.execute_tool` orchestrates the extraction and injection of guidance.

## Why it matters

This allows the project to scale to 1000+ skills by ensuring that even if the LLM "forgets" specific rules in a long session, the system "reminds" it exactly at the point of failure, maintaining zero-trust execution and high accuracy.
