# Skill: Terminal / Shell

## Overview

Provides direct access to the system shell to execute commands. This is a high-power, high-risk skill.

## Capabilities

- **Execute**: `execute_command` (Run any shell command)
- **Background**: `run_background_process` (Long-running tasks) [Planned]

## Safety Rules

1.  **Non-Interactive**: Commands must run non-interactively. Do not run commands that wait for user input (like `nano`, `vim`, or interactive `python`).
2.  **Timeouts**: All commands have a hard timeout (default 60s). Do not run persistent servers here.
3.  **Destructive Actions**: Triple-check `rm`, `mv`, and `dd` commands.
4.  **Output**: Output is captured (stdout/stderr). If output is too large, it may be truncated.
5.  **CWD**: Commands run in the project root by default.
