---
description: "[MASTER] Call omni tools via MCP in Cursor"
---

# Omni MCP Toolset

In Cursor, omni tools are exposed as `mcp_omniAgent_*`. Map **skill.command** to the MCP tool name by replacing dots with underscores: `skill.command` → `mcp_omniAgent_skill_command`.

---

## `/omni <task or requirement>`

When the user invokes **`/omni`** followed by a **task description, requirement, or complex scenario** (in any language), treat that as the single source of intent. Your job is to fulfill that need and to call the right tools with the best parameters.

1. **Normalize to clear English (if not already)**  
   If the text is not in English, or is vague or ambiguous, **first rephrase or translate it into unambiguous English** without changing what the user wants. Use concrete verbs and nouns so there is no room for misinterpretation. Everything you do next is based on this normalized intent.

2. **Discover tools with `skill.discover`**  
   **Before** picking a tool, call **`mcp_omniAgent_skill_discover`** (or `@omni("skill.discover", {"intent": "…"})`) with the **normalized English intent**. Use the returned `discovered_capabilities` (tool names, `usage` strings, descriptions, scores) to see which tools match. This scan ensures you choose from the actual available toolset and use the exact parameter names and usage patterns returned.

3. **Choose tool(s) and parameters from the discover result**  
   From the discover response, select the best-matching tool(s) and set arguments using the **exact `usage` strings** provided (e.g. `@omni("knowledge.stats", {"collection": "…"})`). Infer scope, topic, and options from the user’s words and the tool descriptions. Do not guess parameters—use the usage strings from discover. Aim for **precise tool selection and optimal parameters** so the outcome matches the user’s goal.

4. **Execute and respond**  
   Call the chosen MCP tool(s), then respond to the user. You may reply in the user’s language even when the internal intent was normalized to English.

**Summary**: Normalize input to unambiguous English → **run skill.discover with that intent** → use the returned tool list and usage to pick and call the best tool(s) with correct parameters. All of this is in service of completing the user’s task and getting the best result from the toolset.

**Design and adapt the plan around what’s available.** Skill tools may cover only part of the workflow or the whole workflow—it depends on the task and what `skill.discover` (and other capabilities) give you. Use the available tools to **design and adjust your plan**: use omni tools where they fit, and where there is **no suitable tool** for a step, **adjust the plan** and use the best alternative (editing code, running commands, reading/writing files, search, etc.) so you still **deliver on the user’s goal**. Always aim for the best possible solution to meet the user’s requirement; adapt the plan as needed rather than sticking to a single approach.

---

## General Rules

| Format                                         | Description                                         |
| ---------------------------------------------- | --------------------------------------------------- |
| `@omni("skill.command", { "param": "value" })` | Claude Desktop / natural-language entry             |
| `mcp_omniAgent_skill_command`                  | Actual MCP tool name in Cursor (dots → underscores) |

**Find tools**: Use `skill.discover` or read resource `omni://skill/skill/list_tools`, then convert to the MCP tool name above.

---

## Intent normalization (non‑English → English)

When the user’s request is in a language other than English, **normalize it to English before choosing or calling tools** so the model can resolve the right tool and parameters without ambiguity.

- **Preserve meaning**: Translate or paraphrase into clear, literal English. Do not change the user’s intent (e.g. “查一下知识库有多少条” → “get knowledge base / collection document count” or “show knowledge stats”).
- **Avoid ambiguity**: Prefer concrete verbs and nouns (e.g. “run tests” vs “看一下测试”, “commit with message X” vs “提交一下”). This reduces wrong tool or wrong arguments.
- **Infer parameters from the request**: If the user implies scope, topic, or options (e.g. “查文档里关于 git 的说明” → `knowledge_search` with `query` about git and `scope` docs), set the corresponding tool arguments from that normalized intent.
- **Then call the tool**: Use the normalized English intent to pick the MCP tool (and `intent` / `query` / other params) and invoke it. Reply to the user in their language if they wrote in another language.

This “escape” layer keeps tool calls precise while still accepting multilingual input.

---

## Knowledge Tools (common)

| Purpose                                             | MCP tool name                                      | Typical arguments                             |
| --------------------------------------------------- | -------------------------------------------------- | --------------------------------------------- |
| Collection stats                                    | `mcp_omniAgent_knowledge_stats`                    | `collection`: `"knowledge_chunks"` (optional) |
| Project dev context (Git, guardrails, architecture) | `mcp_omniAgent_knowledge_get_development_context`  | none                                          |
| ZK note stats                                       | `mcp_omniAgent_knowledge_zk_stats`                 | none                                          |
| Semantic recall                                     | `mcp_omniAgent_knowledge_recall`                   | `query`, `limit`, optional `keywords`         |
| Doc/spec search                                     | `mcp_omniAgent_knowledge_search`                   | `query`, `scope`: `"docs"` / `"all"`          |
| Architecture RAG                                    | `mcp_omniAgent_knowledge_consult_architecture_doc` | `topic`                                       |
| Best practices                                      | `mcp_omniAgent_knowledge_get_best_practice`        | `topic`                                       |

---

## Git Tools

| Purpose               | MCP tool name                        | Typical arguments                              |
| --------------------- | ------------------------------------ | ---------------------------------------------- |
| Smart commit workflow | `mcp_omniAgent_git_smart_commit`     | `action`: `"start"` / `"approve"` / `"reject"` |
| Commit                | `mcp_omniAgent_git_commit`           | `message`                                      |
| Commit without hooks  | `mcp_omniAgent_git_commit_no_verify` | `message`                                      |
| Revert a commit       | `mcp_omniAgent_git_revert`           | `commit` (e.g. `HEAD~1`)                       |

---

## Skill / Routing Tools

| Purpose                 | MCP tool name                     | Typical arguments          |
| ----------------------- | --------------------------------- | -------------------------- |
| Discover tool by intent | `mcp_omniAgent_skill_discover`    | `intent`: natural language |
| List installed skills   | `mcp_omniAgent_skill_list_index`  | none                       |
| Install skill on demand | `mcp_omniAgent_skill_jit_install` | `skill_id`                 |

---

## Other Common Tools

| Purpose             | MCP tool name                                              | Typical arguments                                     |
| ------------------- | ---------------------------------------------------------- | ----------------------------------------------------- |
| Run Nushell command | `mcp_omniAgent_omniCell_execute`                           | `command`, `intent`: `"observe"` / `"mutate"`         |
| Batch regex replace | `mcp_omniAgent_advanced_tools_batch_replace`               | `pattern`, `replacement`, `file_glob`, `dry_run`      |
| File/content search | `mcp_omniAgent_advanced_tools_smart_find` / `smart_search` | see tool schema                                       |
| Crawl URL           | `mcp_omniAgent_crawl4ai_crawl_url`                         | `url`, `action`: `"smart"` / `"skeleton"` / `"crawl"` |

---

## How to Use in Cursor

1. **When handling `/omni <user request>`**: Normalize the request to clear English, then **call `mcp_omniAgent_skill_discover`** with that intent. Use the returned `discovered_capabilities` (tool names, `usage`, descriptions) to select the best tool(s) and parameters, then call them. Do not guess parameters—use the usage strings from discover.
2. **Call directly** (when you already know the tool): Use the MCP tool name (e.g. `mcp_omniAgent_knowledge_get_development_context`) with arguments from the tables or from a previous discover result.
3. **Full tool list**: Use MCP `resources/read` with URI `omni://skill/skill/list_tools` to get all tools and parameters.
