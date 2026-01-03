# Skill: Filesystem Operations

## Overview

Provides safe access to the project's file system. Use this skill to read code, write configuration, and explore the directory structure.

## Capabilities

- **Read**: `read_file`, `read_multiple_files`
- **Write**: `write_file`, `edit_file` (replace block)
- **Explore**: `list_directory`, `search_files`
- **Analyze**: `get_file_info` (size, type)

## Safety Rules

1. **Read Before Write**: Always read a file's content before attempting to edit it to ensure you have the latest context.
2. **Atomic Writes**: `write_file` overwrites the ENTIRE file. Ensure you have the full content ready.
3. **Validation**: Check if a file exists (`list_directory` or `get_file_info`) before accessing it blindly.
4. **Scope**: You are confined to the project root. Do not attempt to access system files (e.g., `/etc/passwd`).
5. **Encoding**: All files are handled as UTF-8.
