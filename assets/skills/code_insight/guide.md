# Code Insight Skill

This skill provides static analysis capabilities for the codebase.
It allows the Agent to "see" the structure of code (classes, functions, decorators) without executing it.

## When to use

- When you need to count how many tools are registered in a file.
- When you need to understand the class hierarchy of a module.
- When you want to check if a specific function exists before editing.

## Tools

- `analyze_code_structure`: Parses a Python file and returns a summary of symbols.
