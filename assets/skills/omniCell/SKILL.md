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
    - "nuShell"
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

### `nuShell`

Universal shell tool - use for ANY terminal command.

**Parameters**:

- `command` (string): Any terminal command (auto-detects observe vs mutate)
  - **Examples**: `ls -la`, `cargo test`, `git status`, `npm run build`
  - **Read**: `open config.json` (Returns parsed JSON/Dict directly)
  - **List**: `ls **/*.py | sort-by size` (Returns List[Dict])
  - **Query**: `ps | where cpu > 10`
- `intent` (string, optional): Explicitly force `observe` or `mutate`
- `chunked` (bool, default `false`): Enable chunked delivery for very large payloads
- `action` (string, optional): `start` or `batch`
- `session_id` (string): Required for `action=batch`
- `batch_index` (int, default `0`): Required batch index for `action=batch`
- `batch_size` (int, default `28000`): Character window per batch

**Usage**:

```xml
<tool_call>{"name": "omniCell.nuShell", "arguments": {"command": "cargo test"}}</tool_call>
```

Chunked mode (large output):

```xml
<tool_call>{"name":"omniCell.nuShell","arguments":{"command":"ls **/*","chunked":true}}</tool_call>
```

```xml
<tool_call>{"name":"omniCell.nuShell","arguments":{"action":"batch","session_id":"abc123","batch_index":1}}</tool_call>
```

## Best Practices

1. **Structured Data First**: Always prefer `open` over `cat`. OmniCell automatically parses JSON, YAML, TOML, XML, and CSV into Python dictionaries.
2. **Pipelines**: Use Nu pipes (`|`) to filter data _before_ it reaches the LLM context.
   - _Bad_: `ls -R` (returns huge text block)
   - _Good_: `ls **/* | where size > 1mb | to json` (returns clean data)
3. **Large Output**: For huge results, prefer `chunked=true` and read all `batch_index` values instead of truncating content.
