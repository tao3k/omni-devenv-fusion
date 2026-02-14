# Tools vs Resources

> MCP layer: how **Tools** (callable) and **Resources** (readable) differ and when to use each.

## Summary

| Concept      | Purpose                            | MCP protocol                                | Usage                                                     |
| ------------ | ---------------------------------- | ------------------------------------------- | --------------------------------------------------------- |
| **Tool**     | Run a skill command with arguments | `list_tools` → `call_tool(name, arguments)` | Has parameters; LLM decides when to call and what to pass |
| **Resource** | Read content by URI                | `list_resources` → `resources/read(uri)`    | No parameters; fetch content by URI                       |

---

## Tools (`@skill_command`)

- **Definition**: Functions in a skill’s `scripts/*.py` decorated with `@skill_command`.
- **Discovery**: Rust `ToolsScanner` scans scripts → writes to LanceDB `skills` table as `ToolRecord` (no `resource_uri`).
- **Exposure**: MCP `list_tools()` returns the tool list; clients call `call_tool(name, arguments)`.
- **Characteristics**:
  - Has `inputSchema` (parameter names, types, required/optional).
  - LLM uses description and schema to decide whether to call and which arguments to pass.
  - Entry point: `@omni("skill.command")` runs the corresponding command.

**Examples**: `git.commit`, `knowledge.recall`, `researcher.research`.

---

## Resources (`@skill_resource`)

- **Definition**: Functions in a skill’s `scripts/*.py` decorated with `@skill_resource`; optional `resource_uri` (e.g. `omni://skill/{skill}/{name}`).
- **Discovery**: Rust `ResourceScanner` scans → converts to `ToolRecord` with `resource_uri` and writes to `skills` table; MCP uses `list_all_resources()` to read from DB and expose as **Resource**.
- **Exposure**: MCP `list_resources()` returns resource list (with URIs); clients use `resources/read(uri)` to read content.
- **Characteristics**:
  - **No parameters**: only URI is passed when reading.
  - Implementation: resolve URI to the corresponding `@skill_resource` function, run it (no args), and use the return value as resource content (typically JSON or text).
  - Typical use: status, config, read-only data (e.g. `omni://skill/knowledge/best_practices`).

**Examples**: Skill-exposed status pages, doc fragments, best-practice lists.

---

## Comparison

| Aspect      | Tool (`@skill_command`)                    | Resource (`@skill_resource`)        |
| ----------- | ------------------------------------------ | ----------------------------------- |
| Decorator   | `@skill_command`                           | `@skill_resource`                   |
| Scanner     | `ToolsScanner`                             | `ResourceScanner`                   |
| Storage     | `skills` table, no `resource_uri`          | `skills` table, with `resource_uri` |
| MCP list    | `list_tools()`                             | `list_resources()`                  |
| Usage       | `call_tool(name, arguments)`               | `resources/read(uri)`               |
| Parameters  | Yes (inputSchema)                          | No (URI only)                       |
| Typical use | Execute actions (commit, search, research) | Read content (status, docs, config) |

---

## See also

- [MCP Tool Schema](mcp-tool-schema.md) — inputSchema and call contract for tools
- [MCP Orchestrator](mcp-orchestrator.md) — `@omni` entry point and skill.command convention
