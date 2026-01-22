# CLI Developer Guide

> **WARNING**: This document is outdated and references deleted modules.
> For current documentation, see the links below.

---

## Migration Guide

### Current Documentation

| Topic               | Documentation                                            |
| ------------------- | -------------------------------------------------------- |
| MCP Server          | [MCP-Server Architecture](../architecture/mcp-server.md) |
| Kernel Architecture | [Kernel Architecture](../architecture/kernel.md)         |

### Old → New Mappings

| Deleted Module                 | New Module                           |
| ------------------------------ | ------------------------------------ |
| `agent/cli/commands/route.py`  | See `omni.core.router`               |
| `agent/cli/commands/ingest.py` | See `omni.core.knowledge.librarian`  |
| `agent/cli/commands/skill.py`  | See `omni.core.skills.discovery`     |
| `agent/cli/runner.py`          | See `omni.core.skills.runtime`       |
| `agent/core/module_loader.py`  | See `omni.core.skills.script_loader` |

### Key Classes

| Old            | New                  |
| -------------- | -------------------- |
| `SkillRunner`  | `SkillContext`       |
| `ModuleLoader` | `ScriptLoader`       |
| `print_result` | See `omni.mcp.types` |

---

## Historical Note

This document previously described the CLI commands (`omni route`, `omni ingest`, `omni mcp`, etc.). The new Trinity Architecture CLI system uses:

- **MCP Server**: Standard MCP protocol via `omni.mcp-server`
- **Skill Commands**: Via MCP tools
- **Kernel API**: Programmatic access via `omni.core.kernel`
