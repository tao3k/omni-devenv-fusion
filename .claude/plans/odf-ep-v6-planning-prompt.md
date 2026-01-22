# ODF-EP v6.0 Planning Prompt

> **The "Python Zenith" Engineering Protocol** | Version 6.0

Use this prompt when planning any code refactoring or implementation task.

---

## Protocol Overview

**Mission**: Write code that is immutable, testable, resilient, and observable.

### The Four Pillars

| Pillar                             | Goal         | Implementation                                   |
| ---------------------------------- | ------------ | ------------------------------------------------ |
| **A: Pydantic Shield**             | Immutability | `ConfigDict(frozen=True)` for all DTOs           |
| **B: Protocol-Oriented Design**    | Testability  | `typing.Protocol` instead of ABC                 |
| **C: Tenacity Pattern**            | Resilience   | `@retry` from tenacity for I/O operations        |
| **D: Context-Aware Observability** | Debugging    | `logger.bind(ctx_key=value)` for structured logs |

---

## Planning Checklist

### Discovery

- [ ] Read existing architecture documentation (`docs/developer/mcp-core-architecture.md`)
- [ ] Identify modules to refactor
- [ ] Map dependencies and imports
- [ ] Note any existing patterns to preserve

### Pillar A - Pydantic Shield

Convert DTOs from `@dataclass` or `BaseModel` to frozen Pydantic:

```python
# Before
@dataclass(slots=True)
class ExecutionResult:
    success: bool
    output: str
    error: str | None = None

# After
from pydantic import BaseModel, ConfigDict

class ExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    success: bool
    output: str
    error: str | None = None
```

### Pillar B - Protocol Design

Define protocols for major interfaces:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class IOrchestrator(Protocol):
    @property
    def session(self) -> SessionManager: ...

    async def dispatch(
        self, user_query: str, history: List[Dict[str, Any]] = None
    ) -> str: ...
```

### Pillar C - Tenacity Resilience

Add retry decorators to I/O operations:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1.0),
    reraise=True,
)
async def _append_to_file(self, event: SessionEvent) -> None: ...
```

### Pillar D - Context Logging

Use lazy logger initialization and context binding:

```python
# Lazy logger
_cached_logger = None

def _get_logger() -> Any:
    global _cached_logger
    if _cached_logger is None:
        import structlog
        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger

# Context-aware logging
logger.bind(session_id=self.session_id, event_type=event.type).info("event_written")
```

---

## Output Template

When creating a plan file, structure it as:

````markdown
# [Project Name] Refactoring Plan

## Context

- Reference architecture docs
- Current issues identified
- Goals for this refactoring

## Files to Modify

### 1. `path/to/file.py`

**Current Issues:**

- Issue 1
- Issue 2

**Changes:**

- [ ] Pillar A: ...
- [ ] Pillar B: ...
- [ ] Pillar C: ...
- [ ] Pillar D: ...

## Implementation Order

1. File A - Foundation
2. File B - Dependencies
3. File C - Integration

## Pattern Examples

### Before

```python
# existing code
```
````

### After

```python
# refactored code
```

## Testing

- [ ] Run `just test` for regression tests
- [ ] Run stress tests if applicable

```

---

## Critical Rules

1. **Never break imports**: Maintain backward compatibility through `__init__.py` exports
2. **Keep protocols runtime-checkable**: Use `@runtime_checkable`
3. **Use exponential backoff**: For retry wait times
4. **Never log without context**: Every log line needs `bind()`
5. **Test after each file**: Run tests between refactoring steps

---

## Quick Reference

| Pattern | Implementation |
|---------|----------------|
| Frozen DTO | `model_config = ConfigDict(frozen=True)` |
| Protocol | `@runtime_checkable class IName(Protocol): ...` |
| Retry | `@retry(stop=stop_after_attempt(3), wait=wait_exponential(...))` |
| Lazy Logger | `_get_logger()` function with module-level cache |
| Context Log | `logger.bind(key=value).info("event")` |

---

*Generated for ODF-EP v6.0 Compliance*
```
