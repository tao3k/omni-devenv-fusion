# Modern Python Engineering Standards (3.12+)

> **Version Requirement**: Python >= 3.12
> **Philosophy**: Leverage modern language features for type safety, readability, and performance.

## 1. State & Constants: `StrEnum` (Mandatory)

Do not use "magic strings" or `const` variables for discrete states or options. Use `StrEnum` (Python 3.11+).

**Why?**

- Provides runtime string compatibility (JSON serialization works out-of-the-box).
- Enforces type safety in function signatures.
- Enables IDE autocompletion.

```python
# ❌ Old Pattern
STATUS_ACTIVE = "active"
STATUS_PENDING = "pending"

def set_status(status: str): ...

# ✅ Modern Standard
from enum import StrEnum, auto

class UserStatus(StrEnum):
    ACTIVE = auto()
    PENDING = auto()
    ARCHIVED = auto()

def set_status(status: UserStatus): ...

```

## 2. Control Flow: Structural Pattern Matching (Recommended)

Prefer `match/case` (Python 3.10+) over chains of `if/elif/else`, especially for:

- State machines
- Parsing commands/actions
- Destructuring data

**Why?**

- Faster execution (jump tables optimization).
- Cannot "fall through" accidentally.
- Powerful destructuring capabilities.

```python
# ❌ Old Pattern
if action == "start":
    handle_start()
elif action == "stop":
    handle_stop()
else:
    raise ValueError(f"Unknown: {action}")

# ✅ Modern Standard
match action:
    case UserStatus.ACTIVE:
        handle_start()
    case UserStatus.PENDING | UserStatus.ARCHIVED:  # OR pattern
        check_permissions()
    case _:
        raise ValueError(f"Unknown: {action}")

```

## 3. Class Hierarchy: Explicit Overrides (Mandatory)

Use the `@override` decorator (Python 3.12+) whenever redefining a method from a parent class.

**Why?**

- Prevents bugs where a parent method is renamed but the child is not.
- Acts as documentation for intent.
- Static type checkers (Pyright/Mypy) will flag errors immediately.

```python
from typing import override

class BaseLoader:
    def load(self): ...

class FileLoader(BaseLoader):
    # ✅ Modern Standard
    @override
    def load(self):
        super().load()
        ...

```

## 4. Generics: New Type Parameter Syntax (Recommended)

Use the Python 3.12+ generic syntax (`class Class[T]`) instead of `TypeVar`.

**Why?**

- Cleaner, more readable syntax.
- Eliminates boilerplate `TypeVar` declarations.

```python
# ❌ Old Pattern
from typing import TypeVar, Generic
T = TypeVar("T")

class Registry(Generic[T]):
    def register(self, item: T): ...

# ✅ Modern Standard
class Registry[T]:
    def register(self, item: T): ...

```

## 5. Concurrency: Structured Concurrency (Recommended)

Prefer `asyncio.TaskGroup` (Python 3.11+) over `asyncio.gather()`.

**Why?**

- Safer error handling (propagates `ExceptionGroup`).
- Prevents "dangling tasks" (if one fails, others are cancelled automatically).

```python
# ✅ Modern Standard
try:
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(fetch_a())
        task2 = tg.create_task(fetch_b())
    # Both tasks are guaranteed to be done here
    results = [task1.result(), task2.result()]
except* ValueError as eg:  # Handle ExceptionGroups
    logger.error(f"Validation errors: {eg.exceptions}")

```

## 6. Type System Improvements

### 6.1 Unions (`|`)

Use `X | Y` instead of `Union[X, Y]`.

### 6.2 Self Type

Use `Self` (Python 3.11) for methods returning the instance (fluent interfaces).

### 6.3 Built-in Generics

Use standard collections (`list[str]`, `dict[str, int]`) instead of `typing.List` or `typing.Dict`.

### 6.4 PEP 695: Type Alias Syntax (Mandatory for New Code)

Use the `type` keyword (Python 3.12) for defining type aliases.

**Why?**

- Explicit syntax distinguishes aliases from variables.
- Native support for generic aliases without `TypeVar`.
- Lazy evaluation (supports recursive types naturally).

```python
# ❌ Old Pattern
from typing import TypeAlias, Callable, Awaitable
Vector: TypeAlias = list[float]
Middleware: TypeAlias = Callable[[Request], Awaitable[Response]]

# ✅ Modern Standard
type Vector = list[float]
type Middleware[R, T] = Callable[[R], Awaitable[T]]  # Generic support!

# ODF Standard Example (from omni.foundation.api.types)
type SkillContext = dict[str, Any]
type RouteHandler = Callable[[SkillContext], Awaitable[dict]]

```

## 7. File System: Modern Path Operations

### 7.1 Modern Walking (`pathlib.Path.walk`)

Use `Path.walk()` (Python 3.12) instead of `os.walk`.

**Why?**

- Yields `Path` objects directly (no more `os.path.join`).
- Object-oriented API consistent with the rest of `pathlib`.
- Often faster than manual `os.walk` + instantiation.

```python
from pathlib import Path

# ✅ Modern Standard
def scan_skills(root: Path):
    for dirpath, dirnames, filenames in root.walk():
        # dirpath is a Path object
        if ".git" in dirnames:
            dirnames.remove(".git")  # Pruning works the same way

        for file in filenames:
            process_file(dirpath / file)

```

### 7.2 Native Batching (`itertools.batched`)

Use `itertools.batched()` (Python 3.12) for chunking data.

**Why?**

- Zero-dependency (no need for `more_itertools` or custom helpers).
- Optimized C implementation.

```python
from itertools import batched

# ✅ Modern Standard
async def ingest_documents(docs: list[str]):
    # Process in batches of 100
    for batch in batched(docs, 100):
        await vector_store.add_many(batch)

```

## 8. Pattern Matching Best Practices

When using `match/case`, prefer **Guards** over nested `if` statements inside cases.

```python
match response:
    case {"status": 200, "data": data} if len(data) > 0:
        process(data)
    case {"status": 200}:
        logger.info("Empty response")

```

## 9. Migration Checklist

When refactoring legacy code, check off these items:

- [ ] **Enums**: Convert string constants to `StrEnum`.
- [ ] **Flow**: Replace complex `if/elif` chains with `match/case`.
- [ ] **Typing**:
- [ ] Add `@override` to overridden methods.
- [ ] Convert `TypeVar` to new generic syntax `class Foo[T]`.
- [ ] Convert `TypeAlias` to `type Alias = ...`.
- [ ] Replace `Union[A, B]` with `A | B`.

- [ ] **Files**: Replace `os.walk` with `Path.walk()`.
- [ ] **Loops**: Replace custom chunking logic with `itertools.batched()`.
- [ ] **Async**: Replace `asyncio.gather` with `TaskGroup` where strict error handling is needed.

## 10. Related Documentation

| Document                                                      | Purpose                                     |
| ------------------------------------------------------------- | ------------------------------------------- |
| `assets/skills/knowledge/references/standards/lang-python.md` | Core Python Standards (Style, Docstrings)   |
| `packages/python/foundation/src/omni/foundation/api/types.py` | Centralized Type Definitions (ODF Standard) |
| `pyproject.toml`                                              | Toolchain Configuration (Ruff, Pyright)     |
