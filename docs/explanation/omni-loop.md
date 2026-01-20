# Omni Loop: CCA Runtime Architecture

> **Summary**: The Omni Loop is the core runtime orchestrator that implements the CCA (Context-Command-Action) pattern, enabling intelligent agent behavior through Observe-Decide-Act-Reflect cycles with built-in anti-confusion mechanisms.

---

## 1. The Context (The "Why")

### The Pain Point

Early agent implementations suffered from the **Agent Confusion Loop**:

- Agents repeatedly read the same files without taking action
- No state tracking led to redundant operations
- Tool calls were not validated, causing wasted LLM calls
- Hardcoded logic made the system rigid and unmaintainable

### The Goal

Build a runtime that:

- Prevents redundant operations through intelligent state tracking
- Uses interceptor patterns for clean separation of concerns
- Enables dynamic skill injection based on task intent
- Maintains clean architecture for easy testing and extension

---

## 2. The Mental Model (The "What")

### The Analogy

Think of the Omni Loop as an **intelligent conductor** for an orchestra:

- **LoopState** is the conductor's score sheet, tracking what has been played (read) and modified
- **ActionGuard** is the rehearsal director, blocking repetitive passages
- **SkillInjector** dynamically invites the right musicians (skills) for each piece (task)
- **OmniLoop** conducts the performance through the OODA cycle

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        OmniLoop (CCA Runtime)                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    OODA Loop Cycle                       │   │
│  │  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐  │   │
│  │  │ Observe │ → │ Decide  │ → │   Act   │ → │ Reflect │  │   │
│  │  │ Build   │   │ LLM     │   │ Execute │   │ Distill │  │   │
│  │  │ Context │   │ Reason  │   │ Tools   │   │ Wisdom  │  │   │
│  │  └─────────┘   └─────────┘   └─────────┘   └─────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐    │
│  │ LoopState   │  │ ActionGuard │  │   SkillInjector     │    │
│  │ - visited   │  │ - check()   │  │   - Name Boosting   │    │
│  │ - modified  │  │ - update()  │  │   - Hybrid Search   │    │
│  └─────────────┘  └─────────────┘  └─────────────────────┘    │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              ToolLoader (Rust Scanner)                  │   │
│  │  - JIT execution via omni_core_rs                       │   │
│  │  - Schema generation for LLM                            │   │
│  │  - Tool aliases management                              │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. How It Works (The Mechanics)

### Core Components

#### LoopState (State Pattern)

Tracks session state using Sets for O(1) lookups:

```python
class LoopState:
    visited_files: Set[str]   # Files that have been read
    modified_files: Set[str]  # Files that have been modified

    def is_redundant_read(self, path: str) -> bool:
        """Read is redundant if: read before AND not modified since."""
        return path in self.visited_files and path not in self.modified_files
```

**Value**: Prevents repeated file reads, reducing token waste and LLM confusion.

#### ActionGuard (Interceptor Pattern)

Intercepts tool calls before execution:

```python
class ActionGuard:
    def check(self, tool_name: str, tool_input: dict) -> Optional[str]:
        """Return warning message if action is redundant."""
        if "read_file" in tool_name:
            path = self._extract_path(tool_name, tool_input)
            if path and self._state.is_redundant_read(path):
                return self._block_message(path)  # Block and warn
        return None
```

**Value**: Provides actionable feedback to the LLM instead of silently failing.

#### SkillInjector (Hybrid Discovery)

Dynamically loads relevant skills based on task intent:

1. **Name Boosting**: Detect explicit skill mentions (e.g., "use git to...")
2. **Hybrid Search**: Vector + keyword search for relevance
3. **JIT Loading**: Load unloaded skills on-demand

**Value**: Only loads necessary skills, reducing context bloat.

### The CCA Loop Flow

```
User Task → OmniLoop.run()
    │
    ├─→ [Plan] AdaptivePlanner estimates steps
    │
    ├─→ [Observe] ContextOrchestrator builds layered context
    │   └─→ SkillInjector provides skill prompts
    │
    ├─→ [Decide] LLM reasons with context + tools
    │
    ├─→ [Act] Execute tools with ActionGuard validation
    │   ├─→ Guard.check() ──→ Block if redundant read
    │   └─→ Guard.update_state() ──→ Track visited/modified
    │
    ├─→ [Reflect] Note-Taker distills session wisdom
    │
    └─→ Return summary + active skills
```

---

## 4. Runtime vs Evolution: omni run exec vs Meta-Agent

A common question: **What's the difference between `omni run exec` and `Meta-Agent`?**

The answer is fundamental to understanding the architecture:

> **`omni run exec` is the Driver; `Meta-Agent` is the Engineer.**

| Aspect              | omni run exec (Runtime)                              | Meta-Agent (Evolution)                                |
| ------------------- | ---------------------------------------------------- | ----------------------------------------------------- |
| **Core Engine**     | `OmniLoop` / `Orchestrator`                          | `MetaAgent` / `TDD Cycle`                             |
| **Primary Goal**    | **Solve problems** (Task Execution)                  | **Generate/fix capabilities** (Capability Generation) |
| **Work Mode**       | **Dispatch**: Route → Find Tool → Execute → Feedback | **TDD**: Write Test → Run → Fail → Fix → Pass         |
| **Missing Tool**    | Fails or uses generic LLM to "guess"                 | **Creates** a new tool from scratch                   |
| **Output**          | Answer, file edits, operation results                | Python code (`.py`), tests, fixed system              |
| **Codebase Access** | Read-Only (typically)                                | Read-Write (creates new files)                        |

### The Driver Analogy

```
┌─────────────────────────────────────────────────────────────────┐
│                    omni run exec (Driver)                       │
│                                                                 │
│  User: "Parse this .pcab file"                                  │
│                                                                 │
│  1. Check skill registry → No .pcab parser exists              │
│  2. Options:                                                    │
│     - FAIL: "I don't know .pcab format"                        │
│     - or: Use generic LLM to guess (unreliable)                │
│                                                                 │
│  Result: Cannot complete the task                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Meta-Agent (Engineer)                         │
│                                                                 │
│  Request: "Create a .pcab parser skill"                         │
│                                                                 │
│  1. TDD Cycle:                                                  │
│     - Write test: parse_sample() should extract IP addresses    │
│     - Run test → FAIL                                          │
│     - Generate code: `class PcabParser`                         │
│     - Run test → FAIL                                          │
│     - Analyze error → Fix code                                  │
│     - Repeat until PASS                                         │
│                                                                 │
│  2. Output:                                                     │
│     - `skills/network/pcab_parser.py` (new skill!)              │
│     - `skills/network/tests/test_pcab_parser.py`                │
│                                                                 │
│  Result: New capability created!                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    The Fusion: Self-Evolving Agent              │
│                                                                 │
│  User: "Parse this .pcab file"                                  │
│                                                                 │
│  1. omni run exec checks skills → .pcab parser NOT found        │
│  2. TRIGGERS Meta-Agent → "Create .pcab parser skill"          │
│  3. Meta-Agent generates skill → JIT loads into registry       │
│  4. omni run exec retries → SUCCESS                            │
│                                                                 │
│  Outcome: User gets result, system gains new capability        │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Distinction Matters

**`omni run exec` is the Conscious Mind** (handles tasks directly)

- Fast, focused, action-oriented
- Limited to existing tools
- Optimized for execution speed

**`Meta-Agent` is the Subconscious** (self-evolves and repairs)

- Slow, thorough, correctness-oriented
- Creates new tools when needed
- Optimized for code quality

Together, they form **F4: Self-Evolving Agent**:

- Fulfills immediate tasks (omni run exec)
- Adapts to new challenges (Meta-Agent)

---

## 6. Value Scenarios

### Scenario 1: Anti-Confusion Loop Prevention

**Problem**: Agent keeps re-reading the same file without acting.

```
Step 1: read_file("README.md")      → Allowed, tracked in visited_files
Step 2: read_file("README.md")      → BLOCKED by ActionGuard
         → Returns: "You already read README.md. Use write_file to modify."
Step 3: write_file("README.md", ...) → Allowed, tracked in modified_files
```

**Outcome**: Agent takes action instead of looping.

### Scenario 2: Dynamic Skill Injection

**Problem**: Loading all skills bloats context.

```
Task: "Fix the bug in auth.py with git commit"

1. Name Boosting detects: "git" skill mention
2. Hybrid search finds: "filesystem", "writer" relevant
3. JIT loads: git, filesystem, writer skills only

Context includes: Only 3 skill prompts (~1KB vs ~50KB for all)
```

**Outcome**: 50x context reduction for skill prompts.

### Scenario 3: Session State Tracking

**Problem**: Agent doesn't know what files it has already processed.

```
With LoopState:
- visited_files = {"README.md", "auth.py"}
- modified_files = {"auth.py"}

is_redundant_read("README.md") → True (read, not modified)
is_redundant_read("auth.py") → False (was modified)
```

**Outcome**: Agent can make informed decisions about re-reading files.

---

## 7. Design Decisions & Trade-offs

| Decision                   | Why We Chose It                     | What We Sacrificed        |
| -------------------------- | ----------------------------------- | ------------------------- |
| **State Pattern**          | Testable, reusable state logic      | Slightly more abstraction |
| **Interceptor Pattern**    | Clean separation, composable guards | Additional method calls   |
| \*\*Set-based O(1) lookups | Performance for large file counts   | Memory overhead (Sets)    |
| \*\*Rust Scanner for Tools | Fast tool discovery, type safety    | Rust dependency           |

---

## 8. Usage Examples

### Basic Execution

```python
from agent.core.omni import OmniLoop, run_sync

# Async usage
loop = OmniLoop()
result = await loop.run("Fix the login bug in auth.py", max_steps=4)

# Sync wrapper
result = run_sync("Add error handling to parser.py")
```

### Custom Configuration

```python
# With custom max steps
result = await loop.run("Refactor the entire module", max_steps=8)

# Access state after execution
loop.state.get_stats()
# {'visited_files': 3, 'modified_files': 1}
```

---

## 9. Performance Metrics

| Metric         | Before     | After     | Improvement     |
| -------------- | ---------- | --------- | --------------- |
| **Runtime**    | ~94s       | ~24s      | 74% faster      |
| **Tokens**     | ~60k       | ~7k       | 87% reduction   |
| **File Reads** | 4+ repeats | 1-2 reads | No redundancy   |
| **Actions**    | 0 writes   | 1+ writes | Task completion |

---

## 10. Future Roadmap

- [ ] Persistent state across sessions
- [ ] Multi-agent coordination support
- [ ] Custom guard implementations
- [ ] Performance profiling integration

---

## Related Documentation

- [Trinity Architecture](./trinity-architecture.md) - System architecture overview
- [Context Orchestrator](../reference/mcp-orchestrator.md) - Layered context building
- [Skill Discovery](../llm/skill-discovery.md) - Dynamic skill loading
- [API Reference](../reference/cli.md) - OmniLoop CLI commands

---

_Built on standards. Not reinventing the wheel._
