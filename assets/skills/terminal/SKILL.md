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

- You can execute arbitrary shell commands.
- **WARNING**: You have root/user level access. Do not delete project files without verification.
- **BEST PRACTICE**: Prefer using specific skills (Git, Filesystem) over raw shell commands when possible.
- **ERROR HANDLING**: If a command fails, read the `stderr` carefully before retrying.
