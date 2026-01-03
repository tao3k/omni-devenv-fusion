# Orchestrator MCP Server

> Route complex queries to expert personas and tools. Get architectural, platform, DevOps, or SRE guidance without leaving your IDE.

This server exposes three tool categories:

| Tool                 | Purpose                                                                     |
| -------------------- | --------------------------------------------------------------------------- |
| `list_personas`      | Advertises available roles with use cases                                   |
| `consult_specialist` | Routes questions to specialized personas                                    |
| `consult_router`     | [Cortex] Routes queries to Tool Domains (GitOps, ProductOwner, Coder, etc.) |
| `start_spec`         | [Legislation Gate] Enforces spec exists before coding new work              |

## The Problem It Solves

Generic AI doesn't understand your project's institutional knowledge—your conventions, your stack, your standards.

```bash
# You ask the AI
> How should I design a multitenant control plane?

# Generic AI creates this (wrong context!)
> class ControlPlane(models.Model):
>     # Uses SQLite!
```

The Orchestrator solves this by routing your query to a persona that understands your project's context.

---

## Quick Start

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Export your API key or load from `.mcp.json`:

   ```bash
   export ANTHROPIC_API_KEY=sk-...
   export ORCHESTRATOR_MODEL=claude-3-opus-20240229   # optional
   ```

3. Start the server:

   ```bash
   python -u mcp-server/orchestrator.py
   ```

Expected output:

```
🚀 Orchestrator Server (Async) starting...
```

---

## Architecture: Bi-MCP

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   Claude Desktop                                               │
│        │                                                       │
│        ├── 🧠 orchestrator (The Brain - HERE)                  │
│        │      └── Planning, Routing, Skills, Reviewing         │
│        │                                                         │
│        └── 📝 coder (File Operations)                          │
│               └── Read/Write/Search files                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

The Orchestrator (`main.py`) is the **Brain** of the system:

- **Planning**: `start_spec`, `draft_feature_spec`, `verify_spec_completeness`
- **Routing**: `consult_router` (decides which tool to use)
- **Skills**: `skill()` (access git, terminal, testing, etc.)
- **Reviewing**: `review_staged_changes` (quality gate)
- **Context**: `manage_context`

It **never** accesses files directly. Those are handled by `coder`.

### Phase 13.9: Modular Entrypoint

The Orchestrator follows the **Composition Root** pattern:

```
main.py (87 lines)
    │
    ├── 1. Core Infrastructure
    │   ├── bootstrap.py → boot_core_skills(), start_background_tasks()
    │   └── context_loader.py → load_system_context()
    │
    ├── 2. Capabilities (Domain Logic)
    │   ├── product_owner, lang_expert, librarian
    │   ├── harvester, skill_manager, reviewer
    │
    ├── 3. Core Tools (Operational)
    │   ├── context, spec, router, execution, status
    │
    └── 4. Skills (Dynamic)
            └── filesystem, git, terminal, testing_protocol (auto-boot)
```

### Skill System

Operations (git, terminal, testing, etc.) are accessed via the `skill()` tool:

```json
{
  "tool": "skill",
  "arguments": {
    "skill": "git",
    "call": "git_status()"
  }
}
```

**Available Skills:**

| Skill | Tools |
|-------|-------|
| `git` | git_status, git_log, git_add, smart_commit |
| `terminal` | execute_command, inspect_environment |
| `testing_protocol` | smart_test_runner, run_test_command |
| `writer` | lint_writing_style, polish_text, load_writing_memory |
| `filesystem` | list_directory, read_file, write_file, search_files |

---

## Configuration

Control client and runtime behavior via environment variables:

| Variable                        | Default                            | Description                                                    |
| ------------------------------- | ---------------------------------- | -------------------------------------------------------------- |
| `ANTHROPIC_API_KEY`             | _required_                         | API key for the orchestrator.                                  |
| `ANTHROPIC_BASE_URL`            | `https://api.minimax.io/anthropic` | Anthropic-compatible endpoint.                                 |
| `ORCHESTRATOR_MODEL`            | `MiniMax-M2.1`                     | Model name. Falls back to `ANTHROPIC_MODEL`.                   |
| `ORCHESTRATOR_TIMEOUT`          | `120`                              | Request timeout in seconds.                                    |
| `ORCHESTRATOR_MAX_TOKENS`       | `4096`                             | Max response tokens.                                           |
| `ORCHESTRATOR_ENABLE_STREAMING` | `false`                            | Set to `true` for streaming responses.                         |
| `ORCHESTRATOR_LOG_LEVEL`        | `INFO`                             | Logging level for JSON output.                                 |
| `ORCHESTRATOR_ENV_FILE`         | `.mcp.json`                        | Preload env from JSON (flat or `mcpServers.orchestrator.env`). |

---

## Available Personas

| Persona           | Role                     | When to Use                                                    |
| ----------------- | ------------------------ | -------------------------------------------------------------- |
| `architect`       | High-level design        | Splitting modules, defining boundaries, refactoring strategies |
| `platform_expert` | Nix/OS infrastructure    | devenv configs, containers, environment variables              |
| `devops_mlops`    | CI/CD and pipelines      | Build workflows, reproducibility, model training               |
| `sre`             | Reliability and security | Error handling, performance, vulnerability checks              |

---

## The Cortex (Tool Router)

The Orchestrator includes **The Cortex** - a semantic tool routing system that maps user intent to the correct Tool Domain.

| Domain         | Description              | Example Tools                                            |
| -------------- | ------------------------ | -------------------------------------------------------- |
| `GitOps`       | Version control, commits | skill("git", "smart_commit(...)")                        |
| `ProductOwner` | Specs, requirements      | start_spec, draft_feature_spec, verify_spec_completeness |
| `Coder`        | Code exploration         | read_file, save_file, search_files                       |
| `QA`           | Quality assurance        | review_staged_changes, skill("testing_protocol", ...)    |
| `Memory`       | Context, tasks           | manage_context, consult_knowledge_base                   |
| `DevOps`       | Nix, infra               | community_proxy, consult_specialist, skill("terminal")   |
| `Search`       | Code search              | ast_search, search_project_code                          |

### Consult the Router

Use `consult_router` when you're unsure which tool to use:

```json
{
  "tool": "consult_router",
  "arguments": {
    "query": "I need to create a new feature for user login"
  }
}
```

**Response:**

```
--- 🧠 Cortex Routing Result ---
Domain: ProductOwner (Confidence: 0.9)
Reasoning: Creating a new feature involves defining requirements and specs.

🛠️ Suggested Tools:
- draft_feature_spec
- verify_spec_completeness
- assess_feature_complexity

Tip: You can use these tools directly.
```

---

## The Legislation Gate (start_spec)

The Orchestrator enforces **Spec-First Development** - you cannot code new work without a verified spec.

### start_spec

Call this tool FIRST when you judge the user is requesting new work:

```json
{
  "tool": "start_spec",
  "arguments": {
    "name": "Feature Name"
  }
}
```

**Response (spec exists):**

```json
{
  "status": "allowed",
  "spec_path": "agent/specs/phase10_hive_architecture.md",
  "message": "Legislation complete for 'Hive Architecture'. Ready for execution."
}
```

**Response (no spec):**

```json
{
  "status": "blocked",
  "reason": "Legislation is MANDATORY for new work",
  "spec_required": true,
  "next_action": "draft_feature_spec"
}
```

**Auto-Spec-Path**: When `start_spec` returns "allowed", it auto-saves the spec path. Subsequent calls to `verify_spec_completeness()` will auto-detect the path without manual input.

---

## The Immune System (Code Review)

The Orchestrator includes **The Immune System** - an AI-powered code review gate that runs before tests or commits.

### review_staged_changes

Call this tool to perform a Tech Lead level code review on staged changes:

```json
{
  "tool": "review_staged_changes",
  "arguments": {}
}
```

**What it checks:**

- **Style**: Alignment with `agent/standards/*`
- **Safety**: Security vulnerabilities
- **Clarity**: Descriptive naming, complexity
- **Docs**: Docstrings and comments

**Response:**

```
--- The Immune System (Code Review) ---

REQUEST CHANGES:
- Function `do_stuff` lacks type hints (see lang-python.md)
- Missing docstring for function
- Variable names `a`, `b` are not descriptive

Guidance:
- If REQUEST CHANGES: Fix issues, then review again
- If APPROVE: Proceed to run_tests or smart_commit
```

---

## Practical Scenario: From Intent to Commit

This section demonstrates how The Cortex (Phase 6) and The Immune System (Phase 7) work together in a real workflow.

### Scenario: Implementing a New Feature

You've just written some code and want to commit it properly. Here's how the tools guide you:

### Step 1: Ask The Cortex Which Tools to Use

**Input:**

```json
{
  "tool": "consult_router",
  "arguments": {
    "query": "I want to review my staged changes before committing"
  }
}
```

**Output:**

```
--- 🧠 Cortex Routing Result ---
Domain: QA (Confidence: 0.9)
Reasoning: Reviewing staged changes for commit is a quality assurance task.

🛠️ Suggested Tools:
- review_staged_changes: AI-powered code review before commit
- skill("testing_protocol", "smart_test_runner()"): Execute test suite
- skill("git", "smart_commit(message='...')"): Commit with validated message

Tip: Use review_staged_changes first to ensure code quality.
```

### Step 2: Run The Immune System (Code Review)

**Input:**

```json
{
  "tool": "review_staged_changes",
  "arguments": {}
}
```

**Example Output (Good Code):**

```
--- The Immune System (Code Review) ---

APPROVE:
- Code follows Python standards (type hints present)
- Function naming is clear and descriptive
- Docstrings are present
- No security issues detected

Guidance:
- If REQUEST CHANGES: Fix issues, then review again
- If APPROVE: Proceed to run_tests or smart_commit
```

**Example Output (Bad Code - Missing Standards):**

```
--- The Immune System (Code Review) ---

REQUEST CHANGES:
- Function `do_stuff` lacks type hints (see agent/standards/lang-python.md)
- Missing docstring for function
- Variable names `a`, `b` are not descriptive
- Complex logic should be simplified

Guidance:
- If REQUEST CHANGES: Fix issues using coder tools, then review again
- If APPROVE: Proceed to run_tests or smart_commit
```

### Step 3: Fix Issues (If Needed)

If the review returned REQUEST CHANGES, use the Coder tools to fix:

```json
{
  "tool": "delegate_to_coder",
  "arguments": {
    "task_type": "refactor",
    "details": "Add type hints and docstring to do_stuff function. Rename parameters from 'a', 'b' to more descriptive names like 'x' and 'y'."
  }
}
```

Then stage the fixes and run `review_staged_changes` again.

### Step 4: Proceed to Commit

Once approved:

```json
{
  "tool": "skill",
  "arguments": {
    "skill": "git",
    "call": "smart_commit(message='feat(mcp): add user authentication feature')"
  }
}
```

---

## Phase 8: Singularity (Self-Evolution)

The Orchestrator supports **Bootstrapping** - it can extend itself by adding new capabilities without human coding.

### The Graduation Test

Give the Agent this prompt to add a new capability:

```json
{
  "tool": "consult_router",
  "arguments": {
    "query": "Add a high-performance code search tool called search_project_code that uses ripgrep"
  }
}
```

The Agent will:

1. Route to ProductOwner → Draft a spec
2. Route to Coder → Implement the tool
3. Route to Immune System → Review the code
4. Run tests → Smart commit

### search_project_code

**High-performance code search using ripgrep:**

```json
{
  "tool": "search_project_code",
  "arguments": {
    "pattern": "def \\w+_context",
    "path": "mcp-server",
    "file_type": "py",
    "context_lines": 3
  }
}
```

**Parameters:**

- `pattern`: Regex pattern to search (required)
- `path`: Search directory (default: ".")
- `file_type`: Filter by extension (e.g., "py", "nix")
- `include_hidden`: Search hidden files (default: false)
- `context_lines`: Lines of context around matches (default: 2)

**Output:**

```
Found 5 matches in 2 files (12.34ms):

mcp-server/orchestrator.py:782:    async def get_codebase_context(target_dir: str = ".", ignore_files: str = "") -> str:
mcp-server/orchestrator.py:795:    async def list_directory_structure(root_dir: str = ".") -> str:
mcp-server/mcp_core/memory.py:45:    def save_context(self) -> dict[str, Any]:
mcp-server/mcp_core/memory.py:89:    def get_context(self, context_type: str) -> dict[str, Any]:
mcp-server/mcp_core/memory.py:156:    def update_context(self, updates: dict[str, Any]) -> dict[str, Any]:
```

---

## Phase 9: Code Intelligence (ast-grep)

The Orchestrator includes **Code Intelligence** capabilities using `ast-grep` for structural code search and refactoring.

### ast_search

**Structural code search using AST patterns:**

```json
{
  "tool": "ast_search",
  "arguments": {
    "pattern": "function_def name:$_",
    "lang": "py",
    "path": "mcp-server"
  }
}
```

**Pattern Examples:**

- `def $NAME` - Find all function definitions
- `async def $NAME` - Find all async functions
- `if $COND:` - Find all if statements
- `print($ARGS)` - Find print calls with any arguments
- `import $MODULE` - Find import statements

### ast_rewrite

**Safe structural refactoring:**

```json
{
  "tool": "ast_rewrite",
  "arguments": {
    "pattern": "print($MSG)",
    "replacement": "logger.info($MSG)",
    "lang": "py",
    "path": "mcp-server"
  }
}
```

**Benefits:**

- **Zero False Positives**: Understands code structure, not just text
- **Safe Refactoring**: Preview changes before applying
- **Language-Aware**: Supports Python, Rust, Go, TypeScript, and more

### When to Use

| Tool                  | Use Case                                                 |
| --------------------- | -------------------------------------------------------- |
| `search_project_code` | General text search across all files                     |
| `ast_search`          | Find code by AST structure (functions, classes, imports) |
| `ast_rewrite`         | Refactor code patterns safely                            |

---

## Stress Test Framework

A modular, systematic stress testing framework for Phase 9+.

### Directory Structure

```
mcp-server/tests/
├── stress/                    # Stress test framework
│   ├── __init__.py            # Core (Config, Runner, Reporter)
│   ├── core/
│   │   └── fixtures.py        # Pytest fixtures
│   ├── suites/
│   │   ├── phase9.py          # Phase 9 test suite
│   │   └── template.py        # Phase X template
│   └── conftest.py            # Pytest configuration
├── conftest.py                # Shared fixtures
└── test_stress.py             # Test entry point
```

### Core Components

| Component             | Purpose                                    |
| --------------------- | ------------------------------------------ |
| `StressConfig`        | Configuration (files, thresholds, cleanup) |
| `BenchmarkRunner`     | Performance benchmarks                     |
| `LogicTestRunner`     | Logic depth tests                          |
| `StabilityTestRunner` | Chaos/stability tests                      |
| `StressReporter`      | Report generation                          |
| `Phase9Suite`         | Complete Phase 9 test suite                |

### Run Tests

```bash
just stress-test          # Run all stress tests
pytest mcp-server/tests/test_stress.py -v  # Verbose
```

### Adding New Phase Tests

1. Copy `stress/suites/template.py` → `stress/suites/phase10.py`
2. Implement `run_benchmarks()`, `run_logic_tests()`, `run_stability_tests()`
3. Register in `stress/suites/__init__.py`
4. Import in `test_stress.py`

### Example: Custom Benchmark

```python
from stress import BenchmarkRunner, StressConfig

runner = BenchmarkRunner(StressConfig())
result = runner.run(
    name="My Benchmark",
    pattern="my_pattern",
    lang="py",
    path="/path/to/code"
)
print(f"Duration: {result.duration}s")
```

---

## Example Calls

### List Available Personas

**Input:**

```json
{
  "tool": "list_personas",
  "arguments": {}
}
```

**Output:**

```json
{
  "content": [
    {
      "type": "text",
      "text": "Available personas:\n- architect: High-level design decisions\n- platform_expert: Nix and infrastructure\n- devops_mlops: CI/CD and pipelines\n- sre: Security and reliability"
    }
  ]
}
```

### Consult a Specialist

Consult expert personas for domain-specific advice. Each persona provides role-specific guidance based on query keywords.

**Input:**

```json
{
  "tool": "consult_specialist",
  "arguments": {
    "role": "architect",
    "query": "How should I structure this feature?",
    "stream": false
  }
}
```

**Available Roles:**

| Role              | Description                               | Best For                              |
| ----------------- | ----------------------------------------- | ------------------------------------- |
| `architect`       | High-level design, refactoring strategies | Structure, patterns, design decisions |
| `platform_expert` | Nix/OS, infrastructure, containers        | Dev environment, nix, docker          |
| `devops_mlops`    | CI/CD, pipelines, reproducibility         | Testing, CI, deployment               |
| `sre`             | Reliability, security, performance        | Error handling, security, monitoring  |

**Output:**

```json
{
  "success": true,
  "role": "architect",
  "persona": "System Architect",
  "query": "How should I structure this feature?",
  "response": "**Expert Opinion from System Architect**\n_Expert in software design..._\n\n**Architecture Guidance:**\n- Consider domain-driven design (DDD) structure\n- Keep related functionality together\n..."
}
```

The response includes persona context and role-specific guidance based on query keywords. Set `stream: false` (only supported value).

---

## Register with MCP Client

Configure your MCP client (VS Code, Claude Desktop) to use `orchestrator-tools`. Reference the [Claude cookbooks orchestrator workflow](https://github.com/anthropics/claude-cookbook/tree/main/mcp#orchestrator-pattern).

---

## Writing Standards

This project follows the Omni-DevEnv Technical Writing Standard. See [`agent/writing-style/`](../../agent/writing-style/) for rules on:

- Clarity and mental models (Feynman)
- Eliminating clutter (Zinsser)
- Engineering precision (Rosenberg)
- LLM-optimized structure (Claude)
