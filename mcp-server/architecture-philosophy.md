# Architecture Philosophy: Dual-MCP & Knowledge Organization

> Date: 2024-12-31
> Author: Claude (Human: tao3k)
> Status: Implemented

## Core Philosophy

**Separation of Concerns**: Strategy vs. Tactics

```
┌─────────────────────────────────────────────────────────┐
│                    Orchestrator (Strategy)               │
│  • SDLC Coordination                                    │
│  • Architecture Decisions                               │
│  • SRE/Platform Expertise                               │
│  • Delegates to specialists                             │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Delegates
                          ▼
┌─────────────────────────────────────────────────────────┐
│                      Coder (Tactics)                    │
│  • Surgical Coding                                      │
│  • AST Refactoring                                      │
│  • File Operations                                      │
│  • Executes delegated tasks                             │
└─────────────────────────────────────────────────────────┘
```

## Dual-MCP Pattern

See `mcp-server/dual-mode-context.md` for detailed implementation.

## Router-Augmented Coding (RAC)

**Three-Tier Knowledge System**:

```
┌─────────────────────────────────────────────────────────┐
│  L1: Standards (agent/standards/lang-*.md)             │
│  - Language-specific conventions                        │
│  - Best practices                                       │
│  - Anti-patterns to avoid                               │
└─────────────────────────────────────────────────────────┘
                          │
                          │ consult_language_expert
                          ▼
┌─────────────────────────────────────────────────────────┐
│  L2: Case Law (tool-router/data/examples/*.jsonl)      │
│  - Real-world examples                                  │
│  - Context-specific patterns                            │
│  - Few-shot learning                                    │
└─────────────────────────────────────────────────────────┘
                          │
                          │ LLM reasoning
                          ▼
┌─────────────────────────────────────────────────────────┐
│  L3: Execution (Coder MCP tools)                        │
│  - Read/Write/Refactor operations                       │
│  - AST-based structural changes                         │
│  - Safe sandbox execution                               │
└─────────────────────────────────────────────────────────┘
```

## Documentation Organization Principle

### The 5-Bucket Model

| Directory | Content Type | Queryable By |
|-----------|--------------|--------------|
| `agent/standards/` | **公共标准** - 语言/框架无关的规范 | `consult_*` loads all |
| `agent/knowledge/` | **问题解决方案** - 症状→原因→修复 | `consult_*` searches |
| `agent/specs/` | **功能规格** - What to build | `draft_feature_spec` |
| `agent/how-to/` | **操作指南** - How to do X | `execute_doc_action` |
| `design/` | **设计决策** - Why we chose X | Human reference |

## problem-solving.md Philosophy

**定位**: 思维方式 (Thinking Method)，不是具体问题的解决方案

| ✅ Should Contain | ❌ Should NOT Contain |
|------------------|----------------------|
| 调试协议 (Rule of Three) | Python 特定 threading 问题 |
| 问题诊断流程 | UV workspace 配置细节 |
| 纠错能力培养 | 特定语言的 import 冲突 |
| 工具使用心智模型 | 具体错误消息的解决方案 |

## knowledge/ Philosophy

**定位**: 可搜索的问题-解决方案知识库，MCP 工具可以查询

```markdown
# Title of the Problem

> Keywords: tag1, tag2, tag3  ← MCP search target

## Symptom
## Root Cause
## Solution
## Wrong Solutions  ← Critical: anti-patterns to avoid
## Related
```

### Why Keywords?

- `consult_language_expert` can search by language tag
- `consult_specialist` can search by domain tag
- Enables **Router-Augmented Coding**
