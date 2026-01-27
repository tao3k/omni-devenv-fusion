# Routing Architecture

> **WARNING**: This document is outdated and references deleted modules.
> For current documentation, see the links below.

---

## Migration Guide

### Current Documentation

| Topic               | Documentation                                    |
| ------------------- | ------------------------------------------------ |
| Router Architecture | [Router Architecture](../architecture/router.md) |
| Kernel Architecture | [Kernel Architecture](../architecture/kernel.md) |

### Old → New Mappings

| Deleted Module                           | New Module                      |
| ---------------------------------------- | ------------------------------- |
| `agent/core/router/semantic_router.py`   | `omni.core.router`              |
| `agent/core/router/sniffer.py`           | `omni.core.router.sniffer`      |
| `agent/core/router/models.py`            | `omni.core.router.models`       |
| `agent/core/context_orchestrator`        | `omni.core.kernel.lifecycle`    |
| `agent/capabilities/knowledge/librarian` | `omni.core.knowledge.librarian` |

### Key Classes

| Old              | New              |
| ---------------- | ---------------- |
| `SemanticRouter` | `OmniRouter`     |
| `ContextSniffer` | `IntentSniffer`  |
| `HiveMindCache`  | `RouterRegistry` |

---

## Historical Note

This document previously described the old routing system with wisdom-aware and state-aware routing. The new Trinity Architecture routing system uses:

- **OmniRouter**: Unified entry point
- **HiveRouter**: Multi-hive routing strategy
- **SemanticRouter**: Vector-based matching
- **IntentSniffer**: Context detection
