# Git Skill Backlog

This backlog tracks the evolution of the Git Skill from basic wrapper to full-fledged Version Control Agent.

## Priority 1: Context Management (The "Stash" Gap)

- [x] **Stash Support**: `git_stash_list`, `git_stash_save`, `git_stash_pop`
- [x] **Checkout/Branch**: `git_checkout`, `git_branch`

## Priority 2: History and Correction (The "Undo" Button)

- [x] **Reset Capabilities**: `git_reset` (soft/hard), `git_revert`
- [ ] **Rebase Support**: Interactive rebase planner

## Priority 3: Submodules and Monorepo Support

- [ ] **Submodule Sync**: `git submodule update --init --recursive`

## Priority 4: Advanced Operations

- [ ] **Auto-commit Message**: Generate conventional commit messages using LLM
- [ ] **Diff Pagination**: Handle large diffs with pagination/summary

## Completed

- [x] Basic Status (`git_status_report`)
- [x] Basic Commit (`git_commit`)
- [x] Diff Viewing (`git_smart_diff`)
- [ ] **Self-Evolution**: `git_read_backlog()` (pending implementation)
