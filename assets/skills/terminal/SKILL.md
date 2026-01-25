---
name: "terminal"
version: "1.0.0"
description: "Execute system commands and shell scripts. Use with extreme caution."
routing_keywords:
  [
    "shell",
    "command",
    "bash",
    "run",
    "execute",
    "terminal",
    "cli",
    "console",
    "script",
    "sudo",
    "admin",
    "system",
  ]
authors: ["omni-dev-fusion"]
intents:
  - "Run shell commands"
  - "Execute build scripts"
  - "Run tests in terminal"
  - "System administration tasks"
permissions: []
---

You have loaded the **Terminal Skill**.

## Available Tools in Omni-Loop

**Only `terminal.analyze_last_error` is available** in omni-loop.

Other terminal commands (`terminal.run_command`, `terminal.run_task`, `terminal.inspect_environment`) are filtered out because they use Claude's native bash runner instead.

## Best Practices

- **PREFER**: Use specific skills (Git, Filesystem) over raw shell commands when possible
- **ERROR HANDLING**: If a command fails, use `terminal.analyze_last_error` to debug
