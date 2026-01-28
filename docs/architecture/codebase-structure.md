# Codebase Structure - Omni-Dev-Fusion

> Complete architectural documentation of the Omni-Dev-Fusion project
> Trinity Architecture with Python Trinity (Foundation, Core, MCP-Server) + Rust Crates
> Last Updated: 2026-01-20

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Root Directory Structure](#root-directory-structure)
3. [Python Trinity Architecture](#python-trinity-architecture)
   - [omni-foundation](#omni-foundation)
   - [omni-core](#omni-core)
   - [omni-mcp-server](#omni-mcp-server)
4. [Rust Crates](#rust-crates)
5. [Skills System](#skills-system)
6. [Configuration Files](#configuration-files)
7. [Documentation Structure](#documentation-structure)
8. [Developer Tools](#developer-tools)

---

## Project Overview

### What is Omni-Dev-Fusion?

Omni-Dev-Fusion is an AI-powered development environment that unifies multiple tools into a single interface using the **Trinity Architecture**. It provides:

- **Single Entry Point**: `@omni("skill.command")` - One command to access all tools
- **Zero-Code Skills**: Skills are defined declaratively with YAML frontmatter
- **Hybrid Execution**: Python for orchestration, Rust for performance
- **MCP Protocol**: Model Context Protocol for tool integration

### Trinity Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Clients                          │
│              (Claude Code, GPT-4, etc.)                 │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              omni-mcp-server (L3 - Transport)           │
│         JSON-RPC 2.0 | stdio | SSE | WebSocket          │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                omni-core (L2 - Microkernel)             │
│    Kernel | Router | Skills | Knowledge | Extensions    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│            omni-foundation (L1 - Infrastructure)        │
│    Config | Paths | GitOps | Rust Bridge | Services     │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Rust Crates (Performance Layer)            │
│    omni-vector | omni-tags | omni-edit | omni-security  │
└─────────────────────────────────────────────────────────┘
```

---

## Root Directory Structure

```
omni-dev-fusion/
├── assets/                          # Core assets (skills, configs, templates)
│   ├── skills/                      # 21 Zero-Code skills
│   ├── settings.yaml                # Central configuration
│   ├── skill_index.json             # Master skill registry
│   ├── prompts/                     # LLM prompts
│   ├── templates/                   # File templates
│   ├── knowledge/                   # RAG knowledge base
│   ├── how-to/                      # How-to guides
│   ├── specs/                       # Specifications
│   ├── instructions/                # Instruction files
│   ├── schemas/                     # JSON schemas
│   └── tool-router/                 # Tool routing configuration
│
├── docs/                            # Complete documentation
│   ├── index.md                     # Documentation index
│   ├── backlog.md                   # Development backlog
│   ├── reference/                   # Protocol documentation
│   ├── explanation/                 # Architecture explanations
│   ├── developer/                   # Developer guides
│   ├── human/                       # Human-readable docs
│   ├── llm/                         # LLM-specific documentation
│   └── tutorials/                   # Tutorials
│
├── .claude/                         # Claude Code configuration
│   ├── commands/                    # Slash command templates
│   │   ├── smart-commit.md          # Git commit workflow
│   │   ├── hotfix.md                # Hotfix workflow
│   │   ├── load-skills.md           # Load skills into memory
│   │   ├── omni.md                  # Execute skill command
│   │   └── ...
│   ├── plans/                       # Planning documents
│   ├── project_instructions.md      # Project instructions
│   ├── settings.json                # Claude settings (symlink)
│   └── settings.local.json          # Local overrides
│
├── packages/
│   ├── python/                      # Python packages (Trinity)
│   │   ├── foundation/              # L1 - Infrastructure
│   │   ├── core/                    # L2 - Microkernel Core
│   │   ├── mcp-server/              # L3 - Transport
│   │   └── agent/                   # Agent implementation
│   │
│   └── rust/                        # Rust crates
│       ├── crates/                  # 11 Rust crates
│       │   ├── omni-ast/            # AST utilities
│       │   ├── omni-edit/           # Structural refactoring
│       │   ├── omni-io/             # File I/O
│       │   ├── omni-lance/          # LanceDB utilities
│       │   ├── omni-security/       # Secret scanning
│       │   ├── omni-sniffer/        # Environment sniffer
│       │   ├── omni-tags/           # Symbol extraction
│       │   ├── omni-tokenizer/      # Token counting
│       │   ├── omni-types/          # Common types
│       │   ├── omni-vector/         # Vector database
│       │   └── skills-scanner/      # Skill scanning
│       │
│       └── bindings/
│           └── python/              # PyO3 Python bindings
│
├── scripts/                         # Build and utility scripts
│   ├── benchmark_rust_core.py       # Rust benchmark runner
│   ├── test_meta_agent.py           # Meta-agent tests
│   ├── sync-for-gpt.sh              # GPT sync script
│   └── ...
│
├── .cache/                          # Repomix skill contexts (auto-generated)
├── .data/                           # Project data
├── target/                          # Rust build output
├── dist/                            # Distribution artifacts
│
├── pyproject.toml                   # Python project configuration
├── Cargo.toml                       # Rust workspace configuration
├── Cargo.lock                       # Rust dependency lock
├── justfile                         # Task automation
├── README.md                        # Project overview
├── CLAUDE.md                        # LLM instructions
├── .mcp.json                        # MCP server config
└── lefthook.yml                     # Git hooks (symlink)
```

---

## Python Trinity Architecture

### 1. omni-foundation (L1 - Infrastructure)

**Location**: `packages/python/foundation/src/omni/foundation/`

**Purpose**: Provides foundational services - configuration, paths, Git operations, Rust bridge isolation, and external services.

```
omni/foundation/
├── __init__.py                     # Lazy-loading facade, version management
│
├── api/
│   ├── __init__.py
│   └── decorators.py               # Foundation decorators and utilities
│
├── bridge/                         # Rust bindings isolation layer
│   ├── __init__.py                 # Bridge exports
│   ├── interfaces.py               # Protocol definitions (VectorStoreProvider, etc.)
│   ├── types.py                    # Bridge type definitions
│   ├── rust_impl.py                # Rust implementation wrapper
│   ├── rust_analyzer.py            # Rust code analyzer bindings
│   ├── rust_scanner.py             # Rust file scanner bindings
│   ├── rust_vector.py              # Rust vector store bindings
│   └── scanner.py                  # Scanner interface
│
├── config/                         # Configuration management
│   ├── __init__.py
│   ├── settings.py                 # get_setting() - Settings retrieval, Settings singleton
│   ├── paths.py                    # get_api_key(), get_mcp_config_path()
│   ├── directory.py                # get_conf_dir(), set_conf_dir()
│   ├── dirs.py                     # PRJ_DIRS, PRJ_DATA, PRJ_CACHE
│   ├── logging.py                  # configure_logging()
│   ├── skills.py                   # Skills-related config
│   └── config_paths.py             # Config path utilities
│
├── runtime/                        # Runtime operations
│   ├── __init__.py
│   ├── gitops.py                   # get_project_root(), is_git_repo(), PROJECT singleton
│   ├── isolation.py                # run_skill_command() - Command isolation
│   ├── lib.py                      # Library utilities
│   └── context/                    # Context management
│       ├── __init__.py
│       ├── base.py                 # Context base class
│       └── registry.py             # Context registry
│
├── services/                       # External services
│   ├── __init__.py
│   ├── llm/                        # LLM service
│   │   ├── __init__.py
│   │   ├── api_key.py              # API key management
│   │   ├── client.py               # LLM client
│   │   ├── personas.py             # Persona definitions
│   │   └── inference.py            # Inference utilities
│   │
│   ├── embedding.py                # Embedding service
│   ├── vector_store.py             # Vector store service
│   │
│   └── memory/                     # Memory service
│       ├── __init__.py
│       ├── base.py                 # Memory base class
│       └── vector.py               # Vector memory implementation
│
├── mcp_core/                       # MCP core functionality
│   ├── __init__.py
│   ├── api/                        # API utilities
│   ├── context/                    # Context management
│   ├── inference/                  # Inference services
│   ├── instructions/               # Instruction loading
│   ├── lazy_cache/                 # Caching system
│   ├── memory/                     # Memory management
│   ├── protocol.py                 # Protocol definitions
│   ├── reference_library.py        # Reference library
│   ├── rich_utils.py               # Rich terminal utilities
│   └── utils/                      # Utility functions
│
└── utils/                          # Utility modules
    ├── __init__.py
    ├── cache/                      # Caching system
    │   ├── __init__.py
    │   ├── config.py               # Config cache
    │   ├── file.py                 # File cache
    │   ├── markdown.py             # Markdown cache
    │   └── repomix.py              # Repomix cache
    │
    ├── instructions/               # Instruction loading
    │   ├── __init__.py
    │   └── loader.py               # Instruction loader
    │
    ├── env.py                      # Environment utilities
    ├── file_ops.py                 # File operations
    ├── path_safety.py              # Path safety utilities
    └── skill_utils.py              # Skill utilities
```

#### Key Modules

| Module                  | Purpose                 | Key Exports                     |
| ----------------------- | ----------------------- | ------------------------------- |
| `config/settings.py`    | Configuration singleton | `Settings`, `get_setting()`     |
| `runtime/gitops.py`     | Project root detection  | `get_project_root()`, `PROJECT` |
| `bridge/rust_vector.py` | Vector store bridge     | `RustVectorStore`               |
| `services/embedding.py` | Embedding service       | `get_embedding_service()`       |

---

### 2. omni-core (L2 - Microkernel Core)

**Location**: `packages/python/core/src/omni/core/`

**Purpose**: Provides the microkernel engine - single entry point, lifecycle management, semantic routing, and the skills system.

```
omni/core/
├── __init__.py                     # Kernel, LifecycleManager exports
│
├── kernel/                         # Microkernel Core
│   ├── __init__.py
│   ├── engine.py                   # Kernel class - single entry point, lifecycle mgmt
│   ├── lifecycle.py                # LifecycleManager, LifecycleState
│   ├── watcher.py                  # KernelWatcher - file system watcher for hot reload
│   └── components/                 # Kernel components
│       ├── __init__.py
│       ├── registry.py             # Component registry
│       ├── skill_loader.py         # Skill loading component
│       ├── skill_plugin.py         # Skill plugin interface
│       └── mcp_tool.py             # MCP tool component
│
├── router/                         # Semantic Routing (The Cortex)
│   ├── __init__.py                 # OmniRouter, HiveRouter, IntentSniffer exports
│   ├── main.py                     # OmniRouter - unified router facade
│   ├── router.py                   # SemanticRouter, FallbackRouter, UnifiedRouter
│   ├── hive.py                     # HiveRouter - multi-hive routing strategy
│   ├── cache.py                    # Router caching
│   ├── indexer.py                  # SkillIndexer - builds semantic index
│   ├── sniffer.py                  # IntentSniffer - context detection
│   ├── models.py                   # Router models
│   └── semantic/                   # Semantic routing
│       ├── __init__.py
│       ├── cortex.py               # Semantic cortex
│       ├── fallback.py             # Fallback router
│       └── router.py               # Semantic router implementation
│
├── skills/                         # Skills System
│   ├── __init__.py                 # All skill exports
│   ├── discovery.py                # SkillDiscoveryService, DiscoveredSkill
│   ├── registry.py                 # SkillRegistry - skill metadata management
│   ├── runtime.py                  # SkillContext, SkillManager - execution context
│   ├── memory.py                   # SkillMemory - skill memory management
│   ├── script_loader.py            # ScriptLoader, skill_command decorator
│   ├── universal.py                # UniversalScriptSkill - Zero-Code skill container
│   ├── structure.py                # Skill structure definitions
│   ├── state.py                    # Skill state management
│   │
│   ├── extensions/                 # Extension loading system
│   │   ├── __init__.py
│   │   ├── loader.py               # SkillExtensionLoader
│   │   ├── wrapper.py              # ExtensionWrapper
│   │   ├── fixtures.py
│   │   ├── directory_loader.py     # Directory-based extension loading
│   │   ├── rust_bridge/            # Rust bridge extensions
│   │   │   ├── __init__.py
│   │   │   ├── bindings.py
│   │   │   └── accelerator.py
│   │   │
│   │   └── sniffer/                # Sniffer extensions
│   │       ├── __init__.py
│   │       ├── loader.py
│   │       └── decorators.py
│   │
│   └── registry/                   # Skill registry (per-skill storage)
│       └── __init__.py
│
└── knowledge/                      # Knowledge management
    ├── __init__.py
    └── librarian.py                # Knowledge librarian
```

#### Key Modules

| Module                    | Purpose            | Key Exports                     |
| ------------------------- | ------------------ | ------------------------------- |
| `kernel/engine.py`        | Microkernel engine | `Kernel`                        |
| `router/main.py`          | Unified router     | `OmniRouter`                    |
| `skills/discovery.py`     | Skill discovery    | `SkillDiscoveryService`         |
| `skills/script_loader.py` | Script loading     | `ScriptLoader`, `skill_command` |

---

### 3. omni-mcp-server (L3 - Transport)

**Location**: `packages/python/mcp-server/src/omni/mcp/`

**Purpose**: Provides MCP protocol implementation - JSON-RPC 2.0 types, protocol interfaces, server orchestration, and transport implementations.

```
omni/mcp/
├── __init__.py                     # MCPServer, types, interfaces exports
│
├── types.py                        # JSON-RPC 2.0 types
│                                    # JSONRPCRequest, JSONRPCResponse, JSONRPCError
│                                    # MCPErrorCode, error response helpers
│
├── interfaces.py                   # Protocol definitions
│                                    # MCPRequestHandler, MCPTransport
│                                    # RequestId, ServerNotification
│
├── server.py                       # MCPServer - pure orchestration
│                                    # Server lifecycle, request routing
│
├── interfaces.py                   # Protocol interfaces
│
├── types.py                        # Type definitions
│
└── transport/                      # Transport implementations
    ├── __init__.py
    ├── stdio.py                    # StdioTransport - stdio-based transport
    ├── sse.py                      # SSEServer - Server-Sent Events transport
    └── transport.py                # Base transport interface
```

#### Key Modules

| Module               | Purpose            | Key Exports                                 |
| -------------------- | ------------------ | ------------------------------------------- |
| `types.py`           | JSON-RPC 2.0 types | `JSONRPCRequest`, `make_success_response()` |
| `server.py`          | MCP server         | `MCPServer`                                 |
| `transport/stdio.py` | stdio transport    | `StdioTransport`                            |
| `transport/sse.py`   | SSE transport      | `SSEServer`                                 |

---

## Rust Crates

**Location**: `packages/rust/crates/`

For detailed Rust crate documentation, see [Rust Crates](rust-crates.md).

### Overview

```
packages/rust/crates/
├── omni-ast/              # Unified AST utilities using ast-grep
├── omni-edit/             # Structural refactoring (The Surgeon)
├── omni-io/               # File I/O utilities with encoding detection
├── omni-lance/            # LanceDB RecordBatch utilities
├── omni-security/         # High-performance secret scanning
├── omni-sniffer/          # Environment sniffer (Git + scratchpad)
├── omni-tags/             # Code symbol extraction (The Cartographer)
├── omni-tokenizer/        # Token counting (tiktoken)
├── omni-types/            # Common type definitions
├── omni-vector/           # High-Performance Vector Database (LanceDB)
└── skills-scanner/        # Modular skill directory scanning
```

---

## Skills System

**Location**: `assets/skills/`

For detailed skills documentation, see [Skills System](skills.md).

### Overview

```
assets/skills/
├── _template/                     # Skill template for creating new skills
│   ├── SKILL.md                   # Skill documentation template
│   ├── README.md
│   ├── pyproject.toml
│   ├── scripts/                   # Command implementations
│   │   ├── __init__.py
│   │   └── commands.py
│   └── references/
│
├── advanced_tools/                # Advanced tool operations
│   ├── SKILL.md
│   ├── scripts/
│   └── extensions/
│
├── code_tools/                    # Code analysis and navigation
│   ├── SKILL.md
│   ├── scripts/
│   │   ├── analyze.py
│   │   ├── navigation.py
│   │   └── refactor.py
│   └── extensions/
│
├── crawl4ai/                      # Web crawling
│   ├── SKILL.md
│   └── scripts/
│
├── documentation/                 # Documentation generation
│   ├── SKILL.md
│   └── scripts/
│
├── filesystem/                    # File operations
│   ├── SKILL.md
│   └── scripts/
│       ├── __init__.py
│       └── io.py
│
├── git/                           # Git operations (smart-commit, status, etc.)
│   ├── SKILL.md
│   ├── scripts/
│   │   ├── __init__.py
│   │   ├── commit.py
│   │   ├── status.py
│   │   ├── workflow.py
│   │   └── ...
│   ├── extensions/                # Rust bridge extensions
│   │   └── rust_bridge/
│   │       ├── __init__.py
│   │       ├── accelerator.py
│   │       └── bindings.py
│   ├── templates/
│   └── tests/
│
├── knowledge/                     # Knowledge base management
│   ├── SKILL.md
│   └── scripts/
│
├── memory/                        # Memory/session management
│   ├── SKILL.md
│   └── scripts/
│
├── meta/                          # Meta-operations (refine, etc.)
│   ├── SKILL.md
│   └── scripts/
│
├── note_taker/                    # Note taking & session summarization
│   ├── SKILL.md
│   └── scripts/
│
├── python_engineering/            # Python-specific tools
│   ├── SKILL.md
│   └── scripts/
│
├── rust_engineering/              # Rust-specific tools
│   ├── SKILL.md
│   └── scripts/
│
├── skill/                         # Skill management (discovery, load, reload)
│   ├── SKILL.md
│   └── scripts/
│
├── software_engineering/          # General software engineering
│   ├── SKILL.md
│   └── scripts/
│
├── terminal/                      # Terminal commands
│   ├── SKILL.md
│   └── scripts/
│
├── testing/                       # Testing tools (pytest)
│   ├── SKILL.md
│   └── scripts/
│
├── testing_protocol/              # Testing protocol management
│   ├── SKILL.md
│   └── scripts/
│
└── writer/                        # Writing/text tools
    ├── SKILL.md
    └── scripts/
```

---

## Configuration Files

### Core Configuration

| File                      | Purpose                                                                  |
| ------------------------- | ------------------------------------------------------------------------ |
| `assets/settings.yaml`    | Central configuration: skills dir, knowledge dir, API keys, LLM settings |
| `assets/skill_index.json` | Master registry of all skills with metadata                              |
| `pyproject.toml`          | Python project configuration (uv workspace, ruff, mypy)                  |
| `Cargo.toml`              | Rust workspace configuration (11 crates)                                 |
| `justfile`                | Task automation (build, test, lint commands)                             |
| `.mcp.json`               | MCP server configuration                                                 |

### Git Configuration

| File               | Purpose                  |
| ------------------ | ------------------------ |
| `.github/actions/` | GitHub Actions workflows |
| `lefthook.yml`     | Git hooks configuration  |

---

## Documentation Structure

**Location**: `docs/`

```
docs/
├── index.md                       # Documentation index
├── backlog.md                     # Development backlog
│
├── reference/                     # Protocol documentation (19 files)
│   ├── odf-ep-protocol.md        # Engineering Protocol (CRITICAL)
│   ├── project-execution-standard.md  # Project execution (CRITICAL)
│   ├── odf-rep-protocol.md       # RAG/Representation Protocol
│   ├── extension-system.md       # Extension system architecture
│   ├── extension-system-llm.md   # Extension system for LLMs
│   ├── sniffer.md                # Code sniffer documentation
│   ├── mcp-orchestrator.md       # MCP orchestrator
│   ├── mcp-transport.md          # MCP transport layer
│   ├── mcp-best-practices.md     # MCP best practices
│   ├── cognitive-architecture.md
│   ├── documentation-standards.md
│   ├── cli.md                    # CLI reference
│   └── ...
│
├── explanation/                   # Architecture explanations
│   ├── trinity-architecture.md   # Trinity Architecture overview
│   ├── zero-code-skill-architecture.md
│   └── ...
│
├── developer/                     # Developer guides
│   ├── testing.md                # Testing guide
│   └── ...
│
├── human/                         # Human-readable docs
│   └── architecture/
│
├── llm/                           # LLM-specific documentation
│
└── tutorials/                     # Tutorials
```

---

## Developer Tools

### Claude Code Configuration

**Location**: `.claude/`

```
.claude/
├── commands/                      # Slash command templates
│   ├── smart-commit.md            # Git commit workflow
│   ├── hotfix.md                  # Hotfix workflow
│   ├── load-skills.md             # Load skills into memory
│   ├── load-skill.md              # Load single skill
│   ├── skills.md                  # List skills
│   ├── omni.md                    # Execute skill command
│   └── backlog.md                 # View backlog
│
├── plans/                         # Planning documents
│   └── odf-ep-v6-planning-prompt.md
│
├── project_instructions.md        # Project instructions
└── settings.json                  # Claude settings (symlink)
```

### Build and Test

**Location**: `justfile`

```bash
# Key just commands
just test              # Run all tests
just build-rust-dev    # Build Rust debug bindings
just lint              # Run linters
just format            # Format code
just validate          # Full validation
```

### Build Scripts

**Location**: `scripts/`

```
scripts/
├── benchmark_rust_core.py       # Rust benchmark runner
├── sync-for-gpt.sh              # GPT sync script
├── test_meta_agent.py           # Meta-agent tests
├── test_cartographer.py         # Cartographer tests
└── test_ouroboros.py            # Ouroboros tests
```

---

## Dependency Flow

### Layer Dependencies

```
omni-foundation (L1)
    │
    ├── config/settings.py ──────► Settings singleton
    ├── runtime/gitops.py ───────► get_project_root()
    ├── bridge/rust_*.py ────────► Rust crate bindings
    └── services/embedding.py ───► Vector store + embeddings
            │
            ▼
    omni-core (L2)
            │
            ├── kernel/engine.py ◄── Kernel, lifecycle
            ├── router/main.py ◄───► OmniRouter, IntentSniffer
            └── skills/discovery.py ◄─► Skills, ScriptLoader
                    │
                    ▼
        omni-mcp-server (L3)
                    │
                    ├── server.py ◄────── MCPServer
                    ├── types.py ◄──────► JSON-RPC 2.0 types
                    └── transport/*.py ◄─ Transport impl
```

### Rust-Python Bridge

```
Python                    Rust
   │                        │
   ├─► omni-vector ───────► omni-vector (LanceDB)
   │                        │
   ├─► omni-tags ─────────► omni-tags (Symbol extraction)
   │                        │
   ├─► omni-edit ─────────► omni-edit (Structural refactoring)
   │                        │
   └─► omni-security ─────► omni-security (Secret scanning)
```

---

## Key Concepts

### Zero-Code Skill Architecture

Skills are defined declaratively using YAML frontmatter in `SKILL.md`:

```yaml
---
name: git
description: Git operations skill
commands:
  - name: status
    description: Show working tree status
  - name: commit
    description: Commit changes
---
```

### Trinity Package Design

1. **Foundation (L1)**: Pure infrastructure - no business logic
2. **Core (L2)**: Business logic - orchestration, skills, routing
3. **MCP-Server (L3)**: Protocol - JSON-RPC 2.0, transport

### Rust for Performance

- **omni-vector**: Vector search with LanceDB
- **omni-tags**: Fast symbol extraction with tree-sitter
- **omni-edit**: Batch refactoring with rayon parallelism
- **omni-security**: Secret scanning with DFA regex

---

## Related Documentation

- [Trinity Architecture](explanation/trills.md)
- [Rust Crates](rust-crates.md)
- [Skills System](skills.md)
- [Engineering Protocol](../reference/odf-ep-protocol.md)
- [Project Execution Standard](../reference/project-execution-standard.md)
