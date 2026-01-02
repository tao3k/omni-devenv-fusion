# Why omni-dev-fusion?

> Addressing the real problems in AI-assisted software development.

---

## The Community Pain Points

We built omni-dev-fusion because we faced these problems every day.

### 1. AI is Context-Blind

Every developer has experienced this:

```bash
# You ask the AI
> Add user authentication

# AI creates this (wrong stack!)
> class UserAuth(models.Model):
>     # Uses SQLite!
```

**Our reality**: Nix, PostgreSQL, specific security standards.

**Result**: 30 minutes wasted fighting the AI to use our stack.

> Generic AI doesn't understand your project's **institutional knowledge**—your conventions, your standards, your stack.

### 2. Engineering Rigor Disappears

AI-generated code often lacks:

- Tests
- Documentation
- Type safety
- Security reviews
- Consistent formatting

> AI optimizes for "it works" not "it's maintainable."

### 3. Tool Sprawl

Every project re-invents the wheel:

```
MCP servers for Nix, Docker, GitHub...
Custom scripts for commits
Separate linters for docs
No unified persona system
No project memory
```

> No cohesive architecture.

### 4. AI Can Break Things

```bash
# You ask the AI
> Fix the bug

# AI runs this (destructive!)
> git reset --hard
```

> AI has no safety rails.

### 5. Documentation Debt

AI writes docs that are:

- Verbose ("strip the clutter" - On Writing Well)
- Passive voice (Engineering standard: active voice)
- Inconsistent (No single source of truth)
- Out of date (No enforcement mechanism)

---

## Our Solutions

### Solution 1: The Bridge Pattern

We extend MCP with a policy layer. The Bridge isn't new—it's the **Decorator Pattern** applied to MCP.

```
User Request → Orchestrator (The Bridge) → Personas → Coder → Validate
```

| Capability             | Purpose                                                      |
| ---------------------- | ------------------------------------------------------------ |
| **Context Injection**  | Every query gets project-aware context                       |
| **Policy Enforcement** | Rejects requests that violate `CLAUDE.md`                    |
| **Persona Routing**    | SRE for security, Architect for design, Tech Writer for docs |

### Solution 2: Personas as Guardrails

Use AI to check AI.

| Persona           | Role            | What It Prevents            |
| ----------------- | --------------- | --------------------------- |
| `architect`       | Design review   | Bad architectural decisions |
| `platform_expert` | Nix review      | Broken devenv configs       |
| `devops_mlops`    | CI/CD review    | Failing pipelines           |
| `sre`             | Security review | Vulnerabilities             |
| `tech_writer`     | Docs review     | Verbose, passive docs       |

### Solution 3: Writing Standards System

Automated documentation quality:

1. **Reference**: `design/writing-style/` (modular library)
2. **Persona**: `tech_writer` enforces standards
3. **Tool**: `polish_text` auto-improves drafts
4. **Linter**: Vale catches passive voice, wordiness

### Solution 4: Memory Garden

Long-term project memory in `.memory/`:

| Operation      | Purpose                                      |
| -------------- | -------------------------------------------- |
| `add_decision` | Record ADRs (Architectural Decision Records) |
| `add_task`     | Track technical debt                         |
| `save_context` | Snapshot project state                       |

### Solution 5: Safe Execution

Sandboxed commands with whitelist:

**Allowed:**

```bash
just validate
just test-mcp
git status
nix fmt
```

**Blocked:**

```bash
rm -rf
git reset --hard
curl | sh
```

### Solution 6: Test-First Protocol

Every feature gets tests in the same commit:

```python
# mcp-server/tests/test_basic.py
def test_new_tool():
    # Write the test first
    pass
```

---

## What We Bring to the Community

| Community Problem    | Our Solution                                    |
| -------------------- | ----------------------------------------------- |
| AI is context-blind  | Bridge Pattern with persona delegation          |
| No engineering rigor | Test-First Protocol + Personas as Guardrails    |
| Tool sprawl          | Unified MCP architecture (Orchestrator + Coder) |
| AI breaks things     | Safe execution whitelist                        |
| Documentation debt   | Writing Standards System (Vale + Tech Writer)   |
| No project memory    | Memory Garden for ADRs and lessons              |

---

## Not Reinventing the Wheel

We stand on the shoulders of giants:

| What We Use          | Why                                             |
| -------------------- | ----------------------------------------------- |
| **MCP**              | Standard protocol for AI-tools integration      |
| **Vale**             | Proven prose linter (we integrate, not rewrite) |
| **Claude Cookbooks** | Orchestrator pattern, personas                  |
| **ast-grep**         | Standard AST-based code search                  |
| **Nix**              | Reproducible builds (the foundation)            |
| **On Writing Well**  | Proven writing principles                       |
| **numtide/prj-spec** | Project directory conventions                   |

**Our Contribution**: We synthesized these into a **cohesive, documented, testable system**.

---

## Project Philosophy

> "Don't reinvent the wheel—perfect it."

We don't claim to have invented:

- MCP (Anthropic did)
- Linting (many did)
- Safe execution (Claude-box did)
- Personas (many did)

**What we did**: Synthesized these into a **cohesive, documented, testable system** that you can adopt incrementally.

---

## Who This Is For

### For Individual Developers

- Get AI that understands your stack
- Maintain code quality automatically
- Learn by exploring the patterns

### For Teams

- Enforce standards across all contributors
- Institutional memory that persists
- Safe AI experimentation

### For Tool Builders

- Reference our MCP architecture
- Copy the Writing Standards System
- Use our Test-First Protocol

---

## Next Steps

| Goal                     | Resource                                                     |
| ------------------------ | ------------------------------------------------------------ |
| Get started quickly      | [Tutorial: Getting Started](../tutorials/getting-started.md) |
| Solve a specific problem | [How-to Guides](../how-to/)                                  |
| Browse API commands      | [Reference](../reference/)                                   |

---

_Built on standards. Not reinventing the wheel._
