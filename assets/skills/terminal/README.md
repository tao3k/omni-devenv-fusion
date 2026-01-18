# Skill: Terminal / Shell

## Overview

Provides direct access to the system shell to execute commands. This is a high-power, high-risk skill.

## Capabilities

- **Execute**: `run_task` / `run_command` (Run any shell command)
- **Background**: `run_background_process` (Long-running tasks) [Planned]

## Usage

### run_command

```python
@omni("terminal.run_command", {
    "command": "git",
    "args": ["status"],
    "timeout": 120,
    "tail_lines": 50  # Only show last 50 lines (useful for large output)
})
```

## Safety Rules

1.  **Non-Interactive**: Commands must run non-interactively. Do not run commands that wait for user input (like `nano`, `vim`, or interactive `python`).
2.  **Timeouts**: All commands have a hard timeout (default 60s). Do not run persistent servers here.
3.  **Destructive Actions**: Triple-check `rm`, `mv`, and `dd` commands.
4.  **Large Output**: Use `tail_lines` parameter to limit output (e.g., `tail_lines: 50` for last 50 lines).
5.  **CWD**: Commands run in the project root by default.
