---
name: omniCell
description: Use when executing system commands, running Nushell scripts, querying system state, or performing OS interactions with structured JSON output.
metadata:
  author: omni-dev-fusion
  version: "1.0.0"
  source: "https://github.com/tao3k/omni-dev-fusion/tree/main/assets/skills/omniCell"
  routing_keywords:
    - "nushell"
    - "nu"
    - "execute"
    - "command"
    - "shell"
    - "terminal"
    - "system"
    - "os"
    - "run"
    - "process"
  intents:
    - "Execute system commands"
    - "Run Nushell scripts"
    - "Query system state"
    - "Perform OS interactions"
---

# OmniCell

**OmniCell** transforms the Operating System into a structured data source. Instead of parsing raw text from `stdout`, you receive **JSON objects**.

## Tools

### `execute`

Executes a command in the system's Nushell environment.

**Parameters**:

- `command` (string): The Nushell command.
  - **Read**: `open config.json` (Returns parsed JSON/Dict directly)
  - **List**: `ls **/*.py | sort-by size` (Returns List[Dict])
  - **Query**: `ps | where cpu > 10`
- `intent` (string):
  - `"observe"` (Safe, Read-only. Returns JSON data).
  - `"mutate"` (Write operations. Returns execution status).

## Best Practices

1. **Structured Data First**: Always prefer `open` over `cat`. OmniCell automatically parses JSON, YAML, TOML, XML, and CSV into Python dictionaries.
2. **Pipelines**: Use Nu pipes (`|`) to filter data _before_ it reaches the LLM context.
   - _Bad_: `ls -R` (returns huge text block)
   - _Good_: `ls **/* | where size > 1mb | to json` (returns clean data)
