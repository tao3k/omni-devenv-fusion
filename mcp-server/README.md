# Orchestrator MCP Server

> Route complex queries to expert personas and tools. Get architectural, platform, DevOps, or SRE guidance without leaving your IDE.

This server exposes three tool categories:

| Tool                 | Purpose                                                                     |
| -------------------- | --------------------------------------------------------------------------- |
| `list_personas`      | Advertises available roles with use cases                                   |
| `consult_specialist` | Routes questions to specialized personas                                    |
| `consult_router`     | [Cortex] Routes queries to Tool Domains (GitOps, ProductOwner, Coder, etc.) |

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

## Configuration

Control client and runtime behavior via environment variables:

| Variable                        | Default                            | Description                                                    |
| ------------------------------- | ---------------------------------- | -------------------------------------------------------------- |
| `ANTHROPIC_API_KEY`             | _required_                         | API key for the orchestrator.                                  |
| `ANTHROPIC_BASE_URL`            | `https://api.minimax.io/anthropic` | Anthropic-compatible endpoint.                                 |
| `ORCHESTRATOR_MODEL`            | `MiniMax-M2.1`                     | Model name. Falls back to `ANTHROPIC_MODEL`.                   |
| `ORCHESTRATOR_TIMEOUT`          | `30`                               | Request timeout in seconds.                                    |
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

| Domain         | Description              | Example Tools                                          |
| -------------- | ------------------------ | ------------------------------------------------------ |
| `GitOps`       | Version control, commits | smart_commit, git_status, git_log                      |
| `ProductOwner` | Specs, requirements      | draft_feature_spec, verify_spec_completeness           |
| `Coder`        | Code exploration         | get_codebase_context, delegate_to_coder                |
| `QA`           | Quality assurance        | review_staged_changes, run_tests, analyze_test_results |
| `Memory`       | Context, tasks           | manage_context, memory_garden                          |
| `DevOps`       | Nix, infra               | community_proxy, consult_specialist, run_task          |
| `Search`       | Code search              | search_project_code                                    |

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
- run_tests: Execute test suite
- smart_commit: Commit with validated message

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
  "tool": "smart_commit",
  "arguments": {
    "type": "feat",
    "scope": "mcp",
    "message": "add new feature for user authentication"
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

A modular, system化 stress testing framework for Phase 9+.

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

**Input:**

```json
{
  "tool": "consult_specialist",
  "arguments": {
    "role": "architect",
    "query": "Help design a multitenant control plane for internal platform APIs.",
    "stream": true
  }
}
```

**Output:**

```json
{
  "content": [
    {
      "type": "text",
      "text": "For a multitenant control plane, consider..."
    }
  ]
}
```

The response includes persona context hints. Set `stream: true` for streaming token delivery.

---

## Register with MCP Client

Configure your MCP client (VS Code, Claude Desktop) to use `orchestrator-tools`. Reference the [Claude cookbooks orchestrator workflow](https://github.com/anthropics/claude-cookbook/tree/main/mcp#orchestrator-pattern).

---

## Writing Standards

This project follows the Omni-DevEnv Technical Writing Standard. See [`design/writing-style/`](../../design/writing-style/) for rules on:

- Clarity and mental models (Feynman)
- Eliminating clutter (Zinsser)
- Engineering precision (Rosenberg)
- LLM-optimized structure (Claude)
