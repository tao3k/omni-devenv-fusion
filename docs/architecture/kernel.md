# Kernel Architecture - Omni-Dev-Fusion

> Microkernel Core for Omni-Dev-Fusion
> Last Updated: 2026-01-26

---

## Table of Contents

1. [Overview](#overview)
2. [Kernel Class](#kernel-class)
3. [Lifecycle Management](#lifecycle-management)
4. [Component Registry](#component-registry)
5. [Skill Discovery](#skill-discovery)
6. [ScriptLoader Integration](#scriptloader-integration)
7. [Semantic Router](#semantic-router)
8. [Intent Sniffer](#intent-sniffer)
9. [Event Reactor (v5.0)](#event-reactor-v50)
10. [Hot Reload](#hot-reload)

---

## Overview

The **Kernel** is the single entry point for the Omni-Dev-Fusion core. It provides:

- **Unified lifecycle management** - Initialize, start, shutdown
- **Component registry** - Dependency injection for core components
- **Skill discovery** - Rust-powered high-performance scanning
- **Semantic routing** - Intent-to-action mapping
- **Event-driven reactor** - Reactive architecture via Rust Event Bus (v5.0)
- **Hot reload** - Live skill development without restart

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        Kernel                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  Lifecycle  │  │ Components  │  │  Skill Context  │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  Discovery  │  │   Router    │  │    Sniffer      │  │
│  │  (Rust)     │  │  (Cortex)   │  │     (Nose)      │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
│  ┌─────────────┐                                         │
│  │   Reactor   │  ◄── Event-Driven Architecture (v5.0)   │
│  │  (Async)    │                                         │
│  └─────────────┘                                         │
└─────────────────────────────────────────────────────────┘
```

### The Grand Integration (v5.0)

Steps 3-5 of the Trinity Architecture connect core components to the Rust Event Bus:

```
Rust GLOBAL_BUS.publish("source", "topic", payload)
              ↓
KernelReactor._consumer_loop() [Python async]
              ↓
┌─────────────┼─────────────┬─────────────┐
│             │             │             │
↓             ↓             ↓             ↓
Cortex    Checkpoint    Sniffer     (reserved)
Indexer   Saver         Context
```

| Step | Component  | Event Topic                    | Behavior                   |
| ---- | ---------- | ------------------------------ | -------------------------- |
| 3    | Cortex     | `file/changed`, `file/created` | Auto-increment indexing    |
| 4    | Checkpoint | `agent/step_complete`          | Async state persistence    |
| 5    | Sniffer    | `context/updated`              | Reactive context detection |

---

## Kernel Class

**Location**: `packages/python/core/src/omni/core/kernel/engine.py`

### Key Properties

| Property        | Type             | Description                     |
| --------------- | ---------------- | ------------------------------- |
| `state`         | `LifecycleState` | Current lifecycle state         |
| `is_ready`      | `bool`           | Kernel is initialized and ready |
| `is_running`    | `bool`           | Kernel is running               |
| `project_root`  | `Path`           | Project root directory          |
| `skills_dir`    | `Path`           | Skills directory                |
| `skill_context` | `SkillContext`   | Skill execution context         |
| `router`        | `OmniRouter`     | Semantic router                 |
| `sniffer`       | `IntentSniffer`  | Context detector                |

### Lifecycle Methods

```python
kernel = Kernel()

# Initialize kernel and all components
await kernel.initialize()

# Start kernel (transition to running)
await kernel.start()

# Shutdown kernel and cleanup
await kernel.shutdown()
```

### Component Methods

```python
# Register a component
kernel.register_component("my_component", component_instance)

# Get a component
component = kernel.get_component("my_component")

# Check if component exists
if kernel.has_component("my_component"):
    pass
```

---

## Lifecycle Management

**Location**: `packages/python/core/src/omni/core/kernel/lifecycle.py`

### State Machine

```
UNINITIALIZED ──► INITIALIZING ──► READY ──► RUNNING
                              │         │
                              │         │
                              ▼         ▼
                         SHUTTING_DOWN ◄── STOPPED
```

### States

| State           | Description                           |
| --------------- | ------------------------------------- |
| `UNINITIALIZED` | Kernel not yet initialized            |
| `INITIALIZING`  | Initialization in progress            |
| `READY`         | All components loaded, ready to start |
| `RUNNING`       | Kernel is active                      |
| `SHUTTING_DOWN` | Shutdown in progress                  |
| `STOPPED`       | Kernel has stopped                    |

### Usage

```python
from omni.core.kernel.engine import get_kernel

kernel = get_kernel()
await kernel.initialize()

if kernel.is_ready:
    print("Kernel is ready!")
    await kernel.start()

await kernel.shutdown()
```

---

## Component Registry

The kernel provides a simple dependency injection system:

```python
class MyComponent:
    def __init__(self, kernel: Kernel):
        self.kernel = kernel

kernel = Kernel()
kernel.register_component("my_component", MyComponent(kernel))
```

### Pre-registered Components

| Component           | Description                  |
| ------------------- | ---------------------------- |
| `skill_context`     | Skill execution context      |
| `discovery_service` | Rust-powered skill discovery |
| `router`            | Semantic router              |
| `sniffer`           | Intent sniffer               |

---

## Skill Discovery

**Location**: `packages/python/core/src/omni/core/skills/discovery.py`

The kernel uses Rust-powered scanning for high-performance skill discovery:

```python
# Discover all skills
skills = kernel.discover_skills()

# Get discovery service
service = kernel.discovery_service

# Load a specific skill
skill = kernel.load_universal_skill("git")

# Load all skills
skills = kernel.load_all_universal_skills()
```

### Discovery Flow

```
Kernel.discover_skills()
        │
        ▼
SkillDiscoveryService.discover_all()
        │
        ▼
Rust Scanner (omni-scanner crate)
        │
        ▼
skill_index.json (generated)
        │
        ▼
DiscoveredSkill objects
```

### ScriptLoader Integration

**Location**: `packages/python/core/src/omni/core/skills/script_loader.py`

The ScriptLoader reads `@skill_command` decorators and auto-registers commands:

```python
from omni.core.skills.script_loader import ScriptLoader
from omni.foundation.api.decorators import get_script_config

loader = ScriptLoader(
    scripts_path="assets/skills/git/scripts",
    skill_name="git"
)
loader.load_all()

# Commands are auto-registered from @skill_command decorators
for name, cmd in loader.commands.items():
    config = get_script_config(cmd)
    print(f"{name}: {config['category']}")
```

#### Decorator Attributes

The `@skill_command` decorator (from Foundation) sets:

| Attribute           | Description                                                    |
| ------------------- | -------------------------------------------------------------- |
| `_is_skill_command` | Marker flag (`True`)                                           |
| `_skill_config`     | Dict with name, description, category, input_schema, execution |
| `_command_name`     | Command name (defaults to function name)                       |
| `_category`         | Command category (e.g., "read", "write")                       |

---

## Semantic Router

**Location**: `packages/python/core/src/omni/core/router/`

The **Cortex** provides intent-to-action mapping:

```python
# Get the router
router = kernel.router

# Search for matching skills
results = await router.route("commit git changes")
```

### Router Types

| Router           | Purpose               |
| ---------------- | --------------------- |
| `OmniRouter`     | Unified entry point   |
| `SemanticRouter` | Vector-based matching |
| `HiveRouter`     | Multi-hive routing    |
| `FallbackRouter` | Default routing       |

---

## Intent Sniffer

**Location**: `packages/python/core/src/omni/core/router/sniffer.py`

The **Nose** detects context from the file system:

```python
# Get the sniffer
sniffer = kernel.sniffer

# Load rules from index
count = kernel.load_sniffer_rules()

# Check context
context = sniffer.detect_context("/project/path")
```

### Sniffer Rules

Rules are loaded from `skill_index.json` (generated by Rust scanner):

```json
{
  "rules": [
    {
      "pattern": ".git/**",
      "skill": "git"
    },
    {
      "pattern": "**/*.py",
      "skill": "python_engineering"
    }
  ]
}
```

---

## Event Reactor (v5.0)

**Location**: `packages/python/core/src/omni/core/kernel/reactor.py`

The **Event Reactor** enables reactive architecture by consuming events from the Rust Event Bus and dispatching to Python handlers.

### Architecture

```
Rust GLOBAL_BUS.publish("source", "topic", payload)
              ↓
KernelReactor (Python async consumer)
              ↓
┌─────────────┼─────────────┬─────────────┐
│             │             │             │
↓             ↓             ↓             ↓
Cortex    Checkpoint    Sniffer     Watcher
Indexer      Saver     Context    (Python)
```

### Event Topics

| Topic                 | Source       | Description            |
| --------------------- | ------------ | ---------------------- |
| `file/changed`        | Rust Watcher | File was modified      |
| `file/created`        | Rust Watcher | File was created       |
| `file/deleted`        | Rust Watcher | File was deleted       |
| `agent/step_complete` | Agent Loop   | Agent completed a step |
| `context/updated`     | Sniffer      | Context changed        |
| `system/ready`        | Kernel       | System initialized     |
| `system/shutdown`     | Kernel       | System shutting down   |

### KernelReactor API

```python
from omni.core.kernel.reactor import KernelReactor, get_reactor, EventTopic

# Get global reactor
reactor = get_reactor()

# Register handler
@reactor.register_handler("file/changed")
async def handle_file_change(event):
    payload = event.get("payload", {})
    path = payload.get("path")
    print(f"File changed: {path}")

# Start consuming events
await reactor.start()

# Check stats
stats = reactor.stats
print(f"Events processed: {stats.events_processed}")
```

### Handler Priority

Handlers execute in priority order (higher = runs first):

```python
# High priority (Cortex - auto indexing)
reactor.register_handler(EventTopic.FILE_CHANGED, cortex_handler, priority=10)

# Normal priority (Sniffer - context detection)
reactor.register_handler(EventTopic.FILE_CREATED, sniffer_handler, priority=5)
```

### Integration in Kernel

The Kernel initializes the reactor in `_on_ready()`:

```python
# Initialize reactor
self._reactor = get_reactor()

# Wire Cortex to file events
self._reactor.register_handler(
    EventTopic.FILE_CHANGED,
    self._on_file_changed_cortex,
    priority=10
)

# Wire Sniffer to file events
self.sniffer.register_to_reactor()

# Start consumer loop
await self._reactor.start()
```

### Shutdown Cleanup

```python
async def _on_shutdown(self):
    # Unregister sniffer first
    if self._sniffer is not None:
        self._sniffer.unregister_from_reactor()

    # Stop reactor
    if self._reactor is not None and self._reactor.is_running:
        await self._reactor.stop()
```

---

## Hot Reload

**Location**: `packages/python/core/src/omni/core/kernel/watcher.py`

Enable hot reload for development:

```python
# Enable hot reload
kernel.enable_hot_reload()
```

### Watches

| Path                       | Reload Trigger       |
| -------------------------- | -------------------- |
| `assets/skills/*/scripts/` | Skill script changes |
| `skill_index.json`         | Sniffer rule changes |

### Reload Flow

```
File Change Detected
        │
        ▼
KernelWatcher callback
        │
        ▼
Reload Skill or Sniffer
        │
        ▼
SkillContext.update()
        │
        ▼
Active Commands Updated
```

---

## Initialization Sequence

```python
await kernel.initialize()
```

1. **Initialize Skill Context**
   - Create `SkillContext`
   - Connect to skills directory

2. **Load Universal Skills**
   - Discover skills via Rust scanner
   - Load each skill with `UniversalScriptSkill`
   - Register in skill context

3. **Build Semantic Cortex**
   - Index all skills
   - Build vector index for routing

4. **Initialize Intent Sniffer**
   - Load rules from `skill_index.json`
   - Activate sniffer

---

## Related Documentation

- [Codebase Structure](codebase-structure.md)
- [Router Architecture](router.md)
- [Skills System](skills.md)
- [Rust Crates](rust-crates.md)
