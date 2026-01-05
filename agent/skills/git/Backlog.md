# Git Skill Backlog

## 🚀 Enhancements (To Do)
- [ ] **Support Stash**: Implement `git_stash_save` and `git_stash_pop` tools. Useful when context switching.
- [ ] **Support Undo**: Implement `git_reset_soft` to undo the last commit but keep changes.
- [ ] **Branch Management**: Implement `git_create_branch` and `git_checkout` for multi-feature workflow.

## 🐛 Bugs
- [ ] `git_diff` output can be too large for context window. Need to add pagination or summary mode.

## 💡 Ideas
- Auto-generate commit messages using LLM based on `git diff` content directly in the tool.
