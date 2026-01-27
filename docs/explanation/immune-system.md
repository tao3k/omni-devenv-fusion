# Immune System

> Production-grade security defense for auto-generated skills
> Uses Rust core (omni-ast + omni-security) for high-performance protection

## Overview

The Immune System is a **three-layer defense architecture** that protects Omni-Dev-Fusion from malicious or buggy auto-generated skills:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Candidate Skill                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Level 1: Static Analysis      (Rust: omni-ast / ast-grep)       │
│ - Forbidden imports: os, subprocess, socket, ctypes             │
│ - Dangerous calls: eval(), exec(), compile(), open()            │
│ - Suspicious patterns: getattr(), setattr(), globals()          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼ (if passed)
┌─────────────────────────────────────────────────────────────────┐
│ Level 2: Dynamic Simulation   (Rust: omni-security / Sandbox)   │
│ - Docker container or NsJail execution                          │
│ - LLM-generated test cases                                     │
│ - Timeout and resource limits                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼ (if passed)
┌─────────────────────────────────────────────────────────────────┐
│ Level 3: Permission Gatekeeping (Rust: omni-security / Zero Trust) │
│ - Tool execution permissions                                    │
│ - Scope-based access control                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ┌────────┴────────┐
                    │ Promote / Reject │
                    └──────────────────┘
```

## Architecture

### Level 1: Static Analysis (omni-ast)

Uses `ast-grep` for high-performance pattern matching:

```python
from omni.agent.core.evolution.immune import StaticValidator

# Scan a file
is_safe, violations = StaticValidator.scan(Path("skill.py"))

# Scan content directly
is_safe, violations = StaticValidator.scan_content(code, "skill.py")

# Quick boolean check
if StaticValidator.quick_check(code):
    print("Code passed static analysis")
```

**Detected Patterns:**

| Rule ID            | Category | Description                                               |
| ------------------ | -------- | --------------------------------------------------------- |
| SEC-IMPORT-001~006 | Import   | Forbidden import (os, subprocess, socket, ctypes, etc.)   |
| SEC-CALL-001~007   | Call     | Dangerous function call (eval, exec, compile, open, etc.) |
| SEC-PATTERN-001    | Pattern  | Suspicious pattern (getattr, setattr, globals, locals)    |

### Level 2: Dynamic Simulation (omni-security)

Executes skills in isolated containers:

```python
from omni.agent.core.evolution.immune import SkillSimulator

simulator = SkillSimulator(llm_client=llm)
result = await simulator.verify_skill(Path("skill.py"))

if result.passed:
    print(f"Simulation passed in {result.duration_ms}ms")
else:
    print(f"Simulation failed: {result.stderr}")
```

**Sandbox Modes:**

| Platform | Mode      | Container                             |
| -------- | --------- | ------------------------------------- |
| macOS    | Docker    | Docker container                      |
| Linux    | NsJail    | Lightweight Linux namespace isolation |
| CI/CD    | Simulated | No-op for testing                     |

### Level 3: Permission Gatekeeping

Zero-trust access control for skill execution:

```python
from omni.foundation.bridge.rust_immune import check_permission

# Check if tool execution is allowed
allowed = check_permission(
    tool_name="filesystem.read_file",
    permissions=["filesystem:*", "git:status"]
)

if not allowed:
    raise PermissionError("Tool execution not permitted")
```

## Usage

### Full Immune System

```python
from omni.agent.core.evolution.immune import ImmuneSystem

# Initialize (simulation disabled for CI)
immune = ImmuneSystem(
    quarantine_dir=Path("skills/quarantine"),
    require_simulation=False,  # Skip Docker tests in CI
    llm_client=llm,
)

# Process a candidate skill
report = await immune.process_candidate(Path("generated_skill.py"))

if report.promoted:
    print(f"Skill {report.skill_name} promoted!")
else:
    print(f"Skill rejected: {report.rejection_reason}")
    print(f"Violations: {len(report.static_violations)}")
```

### Directory Scanning

```python
# Scan all candidate skills in a directory
reports = await immune.scan_directory(Path("skills/candidates"))

promoted = [r for r in reports if r.promoted]
rejected = [r for r in reports if not r.promoted]

print(f"Promoted: {len(promoted)}, Rejected: {len(rejected)}")
```

### Quick Security Check

```python
from omni.foundation.bridge.rust_immune import scan_code_security, is_code_safe

# Single call check
is_safe, violations = scan_code_security(code)

# Even faster boolean
if is_code_safe(code):
    # Code passed all security checks
    pass
```

## File Structure

```
packages/python/agent/src/omni/agent/core/evolution/immune/
├── __init__.py              # Module exports
├── validator.py             # Level 1: Static analysis
├── simulator.py             # Level 2: Dynamic simulation
└── system.py                # Level 3: System integration

packages/python/foundation/src/omni/foundation/bridge/
└── rust_immune.py           # Rust bridge layer

packages/rust/crates/omni-ast/
└── src/
    └── security.rs          # Rust security scanner

packages/rust/crates/omni-security/
└── src/
    ├── lib.rs               # Sandbox runner
    └── sandbox.rs           # Docker/NsJail execution
```

## Performance

| Operation                 | Python (ast) | Rust (omni-ast) | Speedup      |
| ------------------------- | ------------ | --------------- | ------------ |
| Security scan (1 file)    | ~10ms        | ~1ms            | **10x**      |
| Security scan (100 files) | ~1000ms      | ~50ms           | **20x**      |
| Pattern matching          | O(n²)        | O(n)            | **Scalable** |

## Fallback Mode

If Rust core is unavailable, the system falls back to Python:

```python
# Automatic fallback in rust_immune.py
if not _RUST_AVAILABLE:
    logger.warning("Rust core unavailable - using Python fallback")
    return _python_fallback_scan(code)  # Simple regex-based scanning
```

## Test Suite

```bash
# Run immune system tests
uv run pytest packages/python/agent/tests/unit/test_evolution.py::TestSecurityViolation -v
uv run pytest packages/python/agent/tests/unit/test_evolution.py::TestStaticValidator -v
uv run pytest packages/python/agent/tests/unit/test_evolution.py::TestImmuneSystem -v

# Run all evolution tests (28+ tests)
uv run pytest packages/python/agent/tests/unit/test_evolution.py -v
```

## Integration with Evolution

The Immune System is integrated with the Evolution module:

```python
from omni.agent.core.evolution import Harvester, CandidateSkill, SkillFactory
from omni.agent.core.evolution.immune import ImmuneSystem

# Full workflow
harvester = Harvester(llm)
candidate = await harvester.analyze_session(session_history)

# Generate skill
skill_path = SkillFactory.synthesize(candidate, output_dir)

# Run immune system
immune = ImmuneSystem(require_simulation=False)
report = await immune.process_candidate(Path(skill_path))

if report.promoted:
    # Move to active skills
    move_to_active(skill_path)
else:
    # Quarantine
    quarantine(skill_path, report)
```

## Related Documentation

- [Rust-Python Bridge](./rust-python-bridge.md)
- [Rust Crates](./rust-crates.md)
- [Permission Gatekeeper](./permission-gatekeeper.md)
- [Skills Architecture](../human/architecture/skills-architecture.md)
