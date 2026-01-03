# Skill: Git Operations

## Overview
This skill provides standardized Git version control capabilities. It enforces the **Smart Commit Protocol** and ensures a clean history.

## Capabilities
- **Status Check**: Inspect modified files (`git_status`).
- **Diff Inspection**: Review changes before committing (`git_diff_staged`).
- **Smart Commit**: The ONLY allowed way to save changes (`smart_commit`).
- **History**: View recent log (`git_log`).

## Workflow Rules
1. **Never use `git commit` directly.** Always use `smart_commit`.
2. **Check before you commit.** Always run `git_status` and `git_diff_staged` to verify what you are about to save.
3. **Atomic Commits.** Try to keep commits focused on a single logical change (Single Responsibility Principle).
4. **Conventional Commits.** Messages must follow the format: `<type>(<scope>): <subject>`.
   - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
