# Skill Discovery

> **WARNING**: This document is outdated and references deleted modules.
> For current documentation, see the links below.

---

## Migration Guide

### Current Documentation

| Topic               | Documentation                                    |
| ------------------- | ------------------------------------------------ |
| Skills System       | [Skills System](../architecture/skills.md)       |
| Router Architecture | [Router Architecture](../architecture/router.md) |
| Kernel Architecture | [Kernel Architecture](../kernel.md)              |

### Old → New Mappings

| Deleted Module                      | New Module                     |
| ----------------------------------- | ------------------------------ |
| `agent.core.skill_discovery`        | `omni.core.skills.discovery`   |
| `agent.core.router.semantic_router` | `omni.core.router`             |
| `agent/core/router/sniffer.py`      | `omni.core.router.sniffer`     |
| `agent/core.vector_store`           | `omni.foundation.vector_store` |

### Key Classes

| Old                    | New                     |
| ---------------------- | ----------------------- |
| `VectorSkillDiscovery` | `SkillDiscoveryService` |
| `SemanticRouter`       | `OmniRouter`            |
| `ContextSniffer`       | `IntentSniffer`         |

---

## Historical Note

This document previously described the old skill discovery system which has been completely rewritten for the Trinity Architecture (Foundation/Core/MCP-Server). The new system uses:

- **Rust Scanner**: High-performance skill scanning via `skills-scanner` crate
- **Skill Index**: JSON-based index (`skill_index.json`)
- **Intent Sniffer**: Context-aware routing
