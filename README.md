# Omni-Dev-Fusion

> From Copilot to Autopilot: Building the Agentic OS for the post-IDE era.

## The Problem

AI coding assistants are great at writing code, but **terrible at the rest of software development**:

- **Context loss** - Forgets project conventions, architectural patterns, and team standards
- **Fragmented tools** - Git, testing, deployment all require different tools and workflows
- **No memory** - Every session starts from scratch
- **Discovery gap** - Can't find existing solutions in your codebase

## The Solution

Omni-Dev-Fusion is an **Agentic OS kernel** that gives your AI assistant:

1. **Persistent memory** - Knowledge base that remembers your patterns, errors, and solutions
2. **Unified interface** - One tool (`@omni(...)`) for every development task
3. **Smart discovery** - Hybrid search finds the right skill or solution instantly
4. **Quality gates** - Spec-first workflow prevents cowboy coding

## What It Solves

| Pain Point                              | Omni-Dev-Fusion Solution                       |
| --------------------------------------- | ---------------------------------------------- |
| "AI keeps making the same mistakes"     | Knowledge base stores error patterns and fixes |
| "I have to repeat myself every session" | Persistent context across sessions             |
| "Which tool do I use for this?"         | `@omni` dispatches to the right skill          |
| "AI doesn't know our codebase patterns" | Vector search indexes your conventions         |
| "Commits are a mess"                    | Smart commit with scope validation             |

## Key Features

### 🧠 Intelligent Context

- Knowledge base with semantic search
- Skill discovery with hybrid ranking (vector + keyword)
- Incremental sync using xxhash (only reindexes changed files)

### 🔧 Unified Interface

```
@omni("git.commit", {"scope": "feat", "message": "..."})  # Smart commit
@omni("db.search", {"query": "user auth", "limit": 5})    # Find solutions
@omni("skill.discover", {"query": "docker deployment"})  # Find skills
```

### ⚡ High Performance

- **Rust foundation** - Tree-sitter parsing, xxhash sync, LanceDB storage
- **Python flexibility** - MCP server, skill commands, agent logic
- **Hybrid search** - RRF fusion for accurate results

### 🛡️ Quality Enforcement

- Specification-first workflow
- Conventional commit validation
- Review gates before commit

## Quick Start

```bash
git clone https://github.com/tao3k/omni-dev-fusion.git
cd omni-dev-fusion
just setup && omni sync
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               Trinity Architecture v4.0                        │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Foundation  │ Rust Core (omni-*)                │
│  Layer 2: Core         │ Python Agent + MCP Server          │
│  Layer 3: Skills       │ Skill Commands (assets/skills/*)   │
│  Layer 4: Knowledge     │ Vector Search + Symbol Index      │
└─────────────────────────────────────────────────────────────┘
```

### Rust Crates

| Crate            | Purpose                           |
| ---------------- | --------------------------------- |
| `omni-ast`       | Tree-sitter code parsing          |
| `omni-vector`    | Hybrid search (LanceDB + Tantivy) |
| `omni-knowledge` | Knowledge ingestion & sync        |
| `omni-scanner`   | Skill metadata extraction         |
| `omni-tags`      | AST symbol extraction             |

## Why It Works

1. **Memory, not just tools** - Your patterns persist across sessions
2. **Discovery, not guessing** - Vector search finds existing solutions
3. **Quality, not chaos** - Spec-first prevents rework
4. **Speed, not bloat** - Rust core, Python flexibility

## For Claude Code

Built as an MCP server - works with Claude Code out of the box:

```bash
# Enable in Claude Code
/mcp enable orchestrator
```

---

Built with Rust, Python, Nix, and Claude Code
