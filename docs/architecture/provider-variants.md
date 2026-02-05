# Provider Variants Architecture

> Omni-Dev-Fusion Architecture Improvement - Provider Pattern Abstraction

## Why Variants?

### Problem Analysis

| Problem                | Impact                             | Traditional Solution                 |
| ---------------------- | ---------------------------------- | ------------------------------------ |
| Single implementation  | Cannot leverage optimal tech stack | Rewrite entire module                |
| Hardcoded dependencies | Difficult environment adaptation   | Conditional branches + feature flags |
| Migration risk         | High risk of breaking changes      | Maintain two codebases               |

### Value of Variants

```
┌────────────────────────────────────────────────────────────┐
│                    Variants Solution                        │
├────────────────────────────────────────────────────────────┤
│ 1. Abstract interface: Define unified behavior contract    │
│ 2. Multiple implementations: Coexist different approaches │
│ 3. Dynamic selection: Choose optimal based on environment │
│ 4. Progressive migration: Smooth transition to new impl   │
└────────────────────────────────────────────────────────────┘
```

## Architecture Design

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                      VariantProvider                          │
├─────────────────────────────────────────────────────────────┤
│ + variant_name: str        # Unique identifier             │
│ + variant_description: str  # Description                  │
│ + variant_status: Status    # Availability status          │
│ + variant_priority: int      # Selection priority          │
│ + execute(**kwargs) -> ToolResponse  # Execution entry    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     VariantRegistry                          │
├─────────────────────────────────────────────────────────────┤
│ + register(command, provider)    # Register variant       │
│ + get(command, variant_name)      # Get specific variant  │
│ + get_best(command)               # Get best variant      │
│ + list_variants(command)          # List all variants     │
└─────────────────────────────────────────────────────────────┘
```

### Status and Priority

```python
class VariantStatus(Enum):
    AVAILABLE = "available"     # Available - preferred
    DEGRADED = "degraded"     # Available but degraded - secondary
    UNAVAILABLE = "unavailable"  # Unavailable - skip

# Selection order:
# 1. By status: AVAILABLE > DEGRADED > UNAVAILABLE
# 2. By priority: lower priority value = higher preference
```

## Directory Structure

```
scripts/
├── search.py              # Default implementation (local)
└── variants/
    └── code_search/
        ├── rust.py        # Rust-accelerated implementation
        └── remote.py      # Remote API implementation
```

### File Naming Convention

```
scripts/variants/<command_name>/<variant_name>.py

Example:
scripts/variants/code_search/rust.py    → command=code_search, variant=rust
scripts/variants/file_read/mmap.py     → command=file_read, variant=mmap
```

## Usage Guide

### 1. Define a Variant

```python
# scripts/variants/code_search/rust.py
from omni.core.skills.variants import VariantProvider
from omni.core.responses import ToolResponse

class RustCodeSearch(VariantProvider):
    """Rust-accelerated code search implementation."""

    variant_name = "rust"
    variant_priority = 10  # High priority
    variant_description = "Rust-accelerated code search using tree-sitter"

    async def execute(self, query: str, **kwargs) -> ToolResponse:
        # Use Rust bridge
        from omni_core_rs import code_search
        results = code_search(query, **kwargs)
        return ToolResponse.success(data=results)

# Auto-register
from omni.core.skills.variants import register_variant
register_variant("code_search", RustCodeSearch())
```

### 2. Use Variants

```python
from omni.core.skills.variants import get_best_variant, get_variant

# Auto-select best implementation
variant = get_best_variant("code_search")
result = await variant.execute(query="def main")

# Use specific variant
rust_variant = get_variant("code_search", "rust")
result = await rust_variant.execute(query="class.*")

# Exclude certain variants
best = get_best_variant("code_search", exclude=["rust"])
```

### 3. Variant Decorator

```python
# Add metadata to variants
from omni.foundation.api.decorators import skill_command

@skill_command(
    name="code_search",
    variants=["local", "rust", "remote"],
    default_variant="rust",
)
async def code_search(query: str, variant: str = None):
    """Search code patterns in the codebase."""
    # variant parameter allows runtime specification
```

## Migration Strategy

### Progressive Migration Example: Python → Rust

```python
# Phase 1: Add Rust variant, local is default
# scripts/search.py (local)
@skill_command(variants=["local", "rust"], default_variant="local")
async def search(query: str, variant: str = "local"):
    ...

# Phase 2: After Rust variant is stable, switch default
# scripts/variants/code_search/rust.py
@skill_command(variants=["local", "rust"], default_variant="rust")
async def rust_search(query: str, variant: str = "rust"):
    ...

# Phase 3: Mark local as deprecated
# scripts/search.py
@skill_command(variants=["local", "rust"], default_variant="rust")
async def search(query: str, variant: str = "rust"):
    """DEPRECATED: Use rust variant instead."""
    ...
```

### Fault Recovery

```python
async def safe_execute(command: str, **kwargs):
    """Execute command with automatic fallback."""
    from omni.core.skills.variants import get_best_variant

    variant = get_best_variant(command)

    if variant is None:
        raise RuntimeError(f"No available variant for {command}")

    try:
        return await variant.execute(**kwargs)
    except Exception as e:
        # Try fallback variant
        from omni.core.skills.variants import get_variant

        for variant_name in ["local", "remote"]:
            fallback = get_variant(command, variant_name)
            if fallback and fallback.variant_status == "available":
                return await fallback.execute(**kwargs)

        raise  # All variants failed
```

## Best Practices

### 1. Variant Naming

| Variant Name | Usage                           |
| ------------ | ------------------------------- |
| `local`      | Pure Python implementation      |
| `rust`       | Rust-accelerated implementation |
| `remote`     | Remote API call                 |
| `mock`       | Mock implementation for testing |

### 2. Priority Settings

| Priority | Usage                        |
| -------- | ---------------------------- |
| 0-10     | Production-preferred variant |
| 11-50    | Backup variants              |
| 51-100   | Degraded/fallback variants   |

### 3. Status Management

```python
class HealthCheckedVariant(VariantProvider):
    async def health_check(self) -> bool:
        # Check if dependencies are available
        return self._check_dependencies()

    @property
    def variant_status(self) -> VariantStatus:
        if not self._check_dependencies():
            return VariantStatus.UNVAILABLE
        if self._has_degraded_performance():
            return VariantStatus.DEGRADED
        return VariantStatus.AVAILABLE
```

## Monitoring and Debugging

### View Registered Variants

```python
from omni.core.skills.variants import get_variant_registry

registry = get_variant_registry()

# List all commands
print(registry.list_commands())

# List variants for a command
print(registry.list_variants("code_search"))

# Get variant info
info = registry.get_info("code_search", "rust")
print(f"Priority: {info.variant_priority}")
print(f"Status: {info.variant_status}")
```

### Debug Selection Logic

```python
from omni.core.skills.variants import get_best_variant

# Debug: See why this variant was selected
variant = get_best_variant("code_search")
print(f"Selected: {variant.variant_name}")
print(f"Status: {variant.variant_status}")
print(f"Priority: {variant.variant_priority}")
```

## Integration with Existing Systems

### 1. ScriptLoader Integration

```python
# Auto-load variants from scripts/variants/
loader = ScriptLoader("assets/skills/code/scripts", "code")
loader.load_all()

# View loaded variants
print(loader.list_variants("search"))
```

### 2. Router Integration

```python
# Router automatically detects variants
router = HiveRouter()

# Select based on runtime capability
if rust_available:
    use_variant("rust")
else:
    use_variant("local")
```

## Summary

| Feature                  | Traditional                 | Variants                    |
| ------------------------ | --------------------------- | --------------------------- |
| Multiple implementations | Maintain separate codebases | Coexist, select as needed   |
| Environment adaptation   | Hardcoded conditions        | Automatic detection         |
| Migration                | Big-bang                    | Progressive                 |
| Fault recovery           | Manual handling             | Automatic fallback          |
| Testing                  | Integrated tests            | Independent variant testing |

Variants make the system more flexible, extensible, and easier to evolve.
