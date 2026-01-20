# Omni-Dev-Fusion Fusion

> From Copilot to Autopilot: Building the Agentic OS for the post-IDE era.

Omni-Dev-Fusion Fusion is an Agentic OS kernel that bridges the gap between human intent and machine execution. By integrating the innovative **Tri-MCP Tri-Core Architecture**, Fusion strictly separates cognitive planning (Brain/Orchestrator), atomic execution (Hands/Executor), and precision coding (Pen/Coder) at the physical layer.

With **Nix** for absolute environment reproducibility and a rigorous "Legislation-Execution" policy engine, Fusion empowers AI to autonomously handle the complete SDLC—from architectural design to AST-level refactoring.Phase 63

## One Tool Architecture

Fusion uses a single MCP tool entry point with infinite skill commands:

```python
@omni("git.status")           # Get git status
@omni("git.commit", {...})    # Commit with cog validation
@omni("file.read", {...})     # Read file
@omni("help")                 # Show all skills
```

| Pattern         | Example      | Dispatches To      |
| --------------- | ------------ | ------------------ |
| `skill.command` | `git.status` | `git.git_status()` |
| `skill`         | `git`        | Shows skill help   |

## Skill Network (Git Installer)

Omni can now **download and install skills from Git repositories** at runtime, enabling true capability expansion:

```bash
# Install a skill from GitHub
omni skill install https://github.com/omni-dev/skill-pandas

# Install specific version
omni skill install https://github.com/omni-dev/skill-docker --version v2.1.0

# Update an installed skill
omni skill update pandas-expert

# List all installed skills
omni skill list

# Show skill details
omni skill info pandas-expert
```

### Skill Management Commands

| Command                                                        | Description                        |
| -------------------------------------------------------------- | ---------------------------------- |
| `omni skill install <url>`                                     | Install skill from Git URL         |
| `omni skill install <url> --name <name>`                       | Install with custom name           |
| `omni skill install <url> --version <ref>`                     | Install specific branch/tag/commit |
| `omni skill update <skill>`                                    | Update skill to latest             |
| `omni skill update <skill> --strategy stash\|abort\|overwrite` | Update with conflict handling      |
| `omni skill list`                                              | List all installed skills          |
| `omni skill info <skill>`                                      | Show skill manifest and lockfile   |

### How It Works

1. **Clone/Update**: Uses GitPython + subprocess for reliable Git operations
2. **Sparse Checkout**: Supports monorepo subdirectory installation
3. **Dependency Detection**: Prevents circular dependencies during install
4. **Lockfile**: Generates `.omni-lock.json` for reproducible installs
5. **Dirty Handling**: Stashes local changes, pulls, then pops (stash strategy)

## Cascading Templates & Skill Structure Validation

Omni supports **cascading templates** with "User Overrides > Skill Defaults" pattern:

```bash
# Check skill structure
omni skill check                 # Check all skills
omni skill check git             # Check specific skill
omni skill check git --examples  # With structure examples

# Manage templates (cascading pattern)
omni skill templates list git              # List templates with source
omni skill templates eject git commit_message.j2  # Copy default to user dir
omni skill templates info git commit_message.j2   # Show template content

# Create new skill from template
omni skill create my-skill --description "My new skill"
```

### Cascading Template Pattern

```
# Priority 1: User Overrides (assets/templates/{skill}/)
assets/templates/git/
├── commit_message.j2     # Custom template (highest priority)

# Priority 2: Skill Defaults (assets/skills/{skill}/templates/)
assets/skills/git/templates/
├── commit_message.j2     # Skill default (fallback)
├── workflow_result.j2
└── error_message.j2
```

### Skill Structure Validation

```
🔍 git

✅ Valid: True
📊 Score: 100.0%
📁 Location: assets/skills/git

## 📁 Structure
├── SKILL.md              # Required
├── tools.py              # Required
├── templates/            # Optional (cascading)
├── scripts/              # Optional (isolated)
└── tests/                # Optional (zero-config)
```

## JIT Skill Acquisition

Omni can **dynamically discover and install skills** when you need capabilities not currently loaded:

```python
# Discover skills matching a query
@omni("skill.discover", {"query": "data analysis", "limit": 5})

# Get task-based suggestions
@omni("skill.suggest", {"task": "analyze pcap file"})

# Install and load a skill
@omni("skill.jit_install", {"skill_id": "network-analysis"})

# List all known skills
@omni("skill.list_index")
```

### Workflow: Acquiring a New Capability

```
User: "Analyze this pcap file"

You: @omni("skill.suggest", {"task": "analyze pcap file"})
     → Found: network-analysis (keywords: pcap, network, wireshark)

     @omni("skill.jit_install", {"skill_id": "network-analysis"})
     → ✅ Installed and loaded!

     Ready to analyze your pcap file.
```

### Available Skills in Index (20 skills)

| Skill ID           | Description                               | Keywords                           |
| ------------------ | ----------------------------------------- | ---------------------------------- |
| `pandas-expert`    | Advanced pandas data manipulation         | pandas, dataframe, data-analysis   |
| `docker-ops`       | Docker container management               | docker, containers, kubernetes     |
| `network-analysis` | PCAP analysis and network troubleshooting | pcap, network, wireshark           |
| `ml-pytorch`       | Machine learning with PyTorch             | pytorch, ml, deep-learning         |
| `aws-cloud`        | AWS cloud services management             | aws, ec2, s3, lambda               |
| `database-sql`     | SQL database operations                   | sql, postgres, mysql, query        |
| `video-processing` | FFmpeg video transcoding                  | video, ffmpeg, transcoding         |
| `rust-systems`     | Rust systems programming                  | rust, wasm, systems                |
| `graphql-api`      | GraphQL schema design                     | graphql, api, schema               |
| `terraform-infra`  | Infrastructure as Code                    | terraform, infrastructure, iac     |
| `security-audit`   | Security vulnerability scanning           | security, vulnerability, audit     |
| `regex-master`     | Regular expression parsing                | regex, pattern, text               |
| `http-client`      | HTTP requests and API testing             | http, api, rest, curl              |
| `git-advanced`     | Advanced git operations                   | git, rebase, bisect, workflow      |
| `shell-scripting`  | Bash/shell scripting                      | bash, shell, scripting, automation |
| `cryptography`     | Encryption and cryptographic ops          | crypto, encryption, hash           |
| `testing-pytest`   | Python testing with pytest                | pytest, testing, coverage          |
| `async-python`     | Python async/await programming            | async, asyncio, concurrency        |
| `fastapi-web`      | FastAPI web framework                     | fastapi, web, api, openapi         |
| `image-processing` | PIL/Pillow image manipulation             | image, pillow, png, jpeg           |

### Key Features

1. **Weighted Scoring**: Keywords (+10), ID (+8), Name (+5), Description (+2)
2. **Auto-Load**: Skills are automatically loaded after installation
3. **Index-Based**: Uses `known_skills.json` for reliable discovery

## Vector-Enhanced Discovery (Virtual Loading)

Omni now uses **LanceDB-based vector search** for intelligent skill discovery with semantic matching:

```bash
# Reindex all skills into vector store
omni skill reindex
omni skill reindex --clear    # Full rebuild

# Show index statistics
omni skill index-stats

# Search local skills only
@omni("skill.discover", {"query": "docker containers", "local_only": true})

# Get task-based suggestions
@omni("skill.suggest", {"task": "analyze nginx logs"})
```

### Routing Flow

```
User Request
    ↓
1. Semantic Cortex (fuzzy cache)
2. Exact Match Cache
3. LLM Routing (Hot Path)
4. Vector Fallback (Cold Path) ← NEW
    - Only searches LOCAL skills (installed_only=True)
    - Returns suggested_skills in RoutingResult
```

### How It Works

- **Index Source**: SKILL.md files are parsed and embedded
- **Storage**: LanceDB table `skills` (via omni-vector)
- **Query**: Semantic similarity search with metadata filtering
- **Fallback**: Triggered when LLM confidence < 0.5 or uses generic skills

### Vector Fallback Example

```python
# User: "write documentation about this project"
# LLM returns: confidence=0.7, selects generic "writer" skill

# Vector Fallback triggers
# Searches for "write documentation" in local skills
# Finds: documentation (score=0.92)

# Result:
# {
#     "selected_skills": ["writer"],
#     "suggested_skills": ["documentation"],  # NEW!
#     "confidence": 0.85,  # Boosted
#     "reasoning": "... [Vector Fallback] Found local skill: documentation"
# }
```

### Available Commands

| Command                  | Description                |
| ------------------------ | -------------------------- |
| `omni skill reindex`     | Rebuild vector index       |
| `omni skill index-stats` | Show index statistics      |
| `skill.discover`         | Semantic skill search      |
| `skill.suggest`          | Task-based recommendations |
| `skill.reindex`          | Rebuild index (tool)       |

See [Developer Guide](../docs/developer/discover.md) for detailed architecture documentation.

## Hot Reload & Index Sync

Omni now supports **zero-downtime skill reloading** with automatic index synchronization:

```bash
# Reload a skill at runtime
omni skill reload git

# Force reload (skip syntax validation)
omni skill reload git --force

# Watch mode (auto-reload on file changes)
omni skill watch git
```

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SkillManager (Runtime)                       │
├─────────────────────────────────────────────────────────────────┤
│  _observers: [MCP Observer, Index Sync Observer]               │
│  _debounced_notify(): 200ms batch window                       │
└─────────────────────────────────────────────────────────────────┘
           ↓                              ↓
┌────────────────────────┐    ┌──────────────────────────────┐
│  MCP Observer          │    │  Index Sync Observer         │
│  send_tool_list_       │    │  Vector Store Upsert         │
│  changed()             │    │  (Vector Discovery Sync)     │
└────────────────────────┘    └──────────────────────────────┘
```

### Key Features

- **Observer Pattern**: Skills emit events on load/unload/reload
- **Debounced Notifications**: 200ms batching prevents notification storms
- **Index Sync**: LanceDB index stays in sync with runtime changes
- **Transactional Safety**: Syntax validation prevents "bricked" skills

### Flow

```
File Modified → Syntax Check → Unload → Load → Debounced Notification
                                              ↓
                          ┌──────────────────┴──────────────────┐
                          ↓                                       ↓
                   MCP Observer                          Index Sync
                   Tool List Update                      Vector Store Upsert
```

## Production Stability

Optimizations for 100+ skill scale and Swarm mode:

### 1. Async Task GC Protection

Background tasks are tracked to prevent premature garbage collection.

### 2. Atomic Upsert

LanceDB uses atomic `upsert` instead of delete+add (no race conditions).

### 3. Startup Reconciliation

Automatic cleanup of "phantom skills" after crash or unclean shutdown.

### Performance at Scale

| Metric                        | Value                          |
| ----------------------------- | ------------------------------ |
| Concurrent reload (10 skills) | 1 notification (90% reduction) |
| Reload time (with sync)       | ~80ms                          |
| Phantom skill detection       | Automatic at startup           |

See [Developer Guide](../docs/developer/discover.md) for details.

## The Vision

**Copilot** (today): AI helps you write code, you drive.

**Autopilot** (tomorrow): AI drives, you architect.

The gap is State, Memory, Policy, Orchestration. **Fusion fills this gap.**

## Smart Commit Workflow

Fusion includes an intelligent commit workflow powered by cog for scope validation:

```bash
/commit
```

**Workflow:**

1. **Preparation** - Stage files, run lefthook pre-commit, check sensitive files
2. **Analysis** - Generate commit message with type/scope/files
3. **Validation** - cog validates scope against `cog.toml`
4. **Execute** - User confirms, commit is executed

**Features:**

- Automatic lefthook integration
- Sensitive file detection (.env, .pem, .key, etc.)
- cog scope validation (type + scope checking)
- Conventional commit format enforcement

## Tri-MCP Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   Claude Desktop                                               │
│        │                                                       │
│        ├── 🧠 orchestrator (The Brain)                         │
│        │      └── Planning, Routing, Reviewing, Policy         │
│        │                                                         │
│        ├── 🛠️ executor (The Hands)                             │
│        │      └── Git, Testing, Shell, Documentation           │
│        │                                                         │
│        └── 📝 coder (The Pen)                                   │
│               └── File I/O, AST Search/Rewrite                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

| Component        | Role      | Responsibilities                                    |
| ---------------- | --------- | --------------------------------------------------- |
| **Orchestrator** | The Brain | Planning, Routing, Spec enforcement, Code Review    |
| **Executor**     | The Hands | Git operations, Testing, Shell execution, Docs      |
| **Coder**        | The Pen   | File I/O, AST-based search/rewrite, Code generation |

## Core Philosophy: Legislation Before Execution

Fusion enforces a strict **"Spec-First" SDLC**. The core concept is: **Legislation First, Then Execution, Then Review**. The system prevents Cowboy Coding through Orchestrator enforcement.

### The SDLC Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. LEGISLATION    →   2. PLANNING   →   3. CODING             │
│  (The Brain)             (The Brain)        (The Pen)           │
│                                                                 │
│  4. TESTING        →   5. REVIEW     →   6. COMMIT             │
│  (The Hands)            (The Immune)      (Protocol)            │
└─────────────────────────────────────────────────────────────────┘
```

### 1. Legislation Phase - "The Brain"

Any new feature or major change must start here.

- **Trigger**: User requests a new feature or refactor.
- **Gatekeeper**: Orchestrator calls `start_spec(name="...")`.
- **Actions**:
  1. If spec doesn't exist, the system **blocks** direct coding, returns "blocked".
  2. Call `draft_feature_spec` to write requirements (usually in `assets/specs/`).
  3. Call `verify_spec_completeness` to verify the spec includes goals, architecture, test plan.

- **Output**: An approved `.md` specification document.

### 2. Planning & Routing Phase - "The Brain"

- **Actions**:
  - Use `manage_context` to update current status (Phase: Planning).
  - Use `consult_router` to decide which tools to use.
  - Consult expert personas (`consult_specialist`) when needed, e.g., ask "Architect" for design patterns, "SRE" for reliability.

### 3. Coding Phase - "The Pen"

- **Status**: `manage_context(phase="Coding")`
- **Executor**: **Coder MCP** (`src/mcp_server/coder/main.py`)
- **Actions**:
  - `read_file` / `search_files`: Understand existing code (micro view).
  - `save_file`: Atomic file writes (.bak backup + syntax validation).
  - `ast_search` / `ast_rewrite`: AST-based precise refactoring (not simple text replacement).

### 4. Testing Phase - "The Hands"

- **Status**: `manage_context(phase="Testing")`
- **Executor**: **Executor MCP** (`src/mcp_server/executor/main.py`)
- **Actions**:
  - `run_task("just test-basic")`: Run basic tests.
  - `run_task("just test-mcp")`: Integration tests for MCP servers.
  - `safe_sandbox`: Execute validation commands in restricted environment.

### 5. Review & Commit Phase - "The Immune System"

- **Actions**:
  1. **Review**: Call `review_staged_changes`. Orchestrator checks code against Spec and `agent/writing-style/*.md` standards.
  2. **Authorized Commit**:
     - Call `smart_commit`. **Note**: Agent cannot run `git commit` directly.
     - System generates an Auth Token and pauses.
     - **User Intervention**: User confirms changes and runs authorization command.
     - Call `execute_authorized_commit` to complete the final commit.

### Tri-MCP Division in SDLC

| SDLC Stage                | Responsible Entity  | Key Actions                             |
| ------------------------- | ------------------- | --------------------------------------- |
| **Requirements & Design** | 🧠 **Orchestrator** | `start_spec`, `draft_feature_spec`      |
| **Implementation**        | 📝 **Coder**        | `save_file`, `ast_rewrite`              |
| **Build & Test**          | 🛠️ **Executor**     | `run_task`, `just test`                 |
| **Code Review**           | 🧠 **Orchestrator** | `review_staged_changes`                 |
| **Publish/Commit**        | 🧠 + 🛠️ **Joint**   | `smart_commit` (protocol) -> `git push` |

## SDLC Capabilities

### Planning & Routing (The Brain)

| Tool                       | Description                                                         |
| -------------------------- | ------------------------------------------------------------------- |
| `start_spec`               | Gatekeeper—blocks new work without a spec                           |
| `draft_feature_spec`       | AI-assisted spec generation                                         |
| `verify_spec_completeness` | Validates spec completeness                                         |
| `manage_context`           | Updates workflow state                                              |
| `consult_router`           | Intent → Right Tool, every time                                     |
| `consult_specialist`       | Expert consultation (architect, sre, devops_mlops, platform_expert) |

### Implementation (The Pen)

| Tool           | Description                                        |
| -------------- | -------------------------------------------------- |
| `read_file`    | Single file reading (micro-level)                  |
| `search_files` | Pattern search (grep-like)                         |
| `save_file`    | Atomic writes with .bak backup & syntax validation |
| `ast_search`   | Query code structure using ast-grep patterns       |
| `ast_rewrite`  | Apply structural patches based on AST patterns     |

### Verification (The Hands)

| Tool                | Description                                       |
| ------------------- | ------------------------------------------------- |
| `run_task`          | Execute `just` commands safely                    |
| `smart_test_runner` | Modified-Code Protocol for minimal test execution |
| `safe_sandbox`      | Restricted command execution                      |
| `smart_commit`      | Protocol-driven commit with authorization         |

### Review & Quality (The Immune System)

| Tool                      | Description                                    |
| ------------------------- | ---------------------------------------------- |
| `review_staged_changes`   | Code review against project standards          |
| `check_doc_sync`          | Verify documentation updated with code changes |
| `verify_design_alignment` | Check spec compliance                          |

## Key Differentiators

| Differentiator             | Why It Matters                                       |
| -------------------------- | ---------------------------------------------------- |
| **Physical Tri-MCP**       | Brain/Hands/Pen never mix—guaranteed context hygiene |
| **Policy Engine**          | Spec-first prevents Cowboy Coding                    |
| **AST Precision**          | Refactor with trees, not regex                       |
| **Nix Reproducibility**    | Same environment, everywhere                         |
| **Actions Over Apologies** | LLM demonstrates fixes, not apologies                |

## Quick Start

```bash
# Clone and enter
git clone https://github.com/tao3k/omni-dev-fusion.git
cd omni-dev-fusion

# Setup development environment
just setup

# Validate everything
just validate
```

## Documentation Structure

| Topic          | Location                                        |
| -------------- | ----------------------------------------------- |
| Architecture   | `docs/reference/mcp-orchestrator.md`            |
| Tri-MCP Design | `docs/explanation/dual-mcp-architecture.md`     |
| MCP Tools      | `packages/python/agent/src/agent/mcp_server.py` |
| Workflows      | `agent/skills/*/prompts.md`                     |
| Slash Commands | `.claude/commands/*.md`                         |
| Skill Docs     | `agent/skills/{skill}/commit-workflow.md`       |
| Specs          | `assets/specs/*.md`                             |

## Skill Architecture

Each skill is a self-contained module:

```
agent/skills/{skill}/
├── prompts.md       # Rules & routing (LLM reads when active)
├── tools.py         # Atomic execution (blind, stateless)
└── commit-workflow.md  # Workflow documentation (if applicable)
```

**To load a skill:** `/load-skill <skill_name>`

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).

## Acknowledgments

Built with modern tools that empower AI-assisted software development:

- **Anthropic Claude Code** - AI-powered coding assistant with MCP support
- **devenv** - Reproducible development environments
- **Nix ecosystem** - Declarative package management
- **omnibus framework** - Advanced configuration management
- **cocogitto** - Automated changelog and versioning
- **lefthook** - Fast and powerful Git hooks
- **ast-grep** - AST-based code search and transformation

Special thanks to the maintainers of these projects for enabling the AI-SDLC workflow.

---

Built with ❤️ using devenv, Nix, and Claude Code

## Atomic Git Skill

The Git Skill has been atomized for independent operation.
