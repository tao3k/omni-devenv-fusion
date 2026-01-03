# Git Operations Skill Prompts

## Smart Commit Prompt

When the user wants to commit changes, follow this protocol:

```
You are about to perform a git commit. Before proceeding:

1. Analyze the current state:
   - Run `git status` to see what's changed
   - Run `git diff --staged` to review staged changes
   - Run `git diff` to see unstaged changes

2. Suggest a commit message:
   - Use `suggest_commit_message` to generate a conventional commit
   - Ensure the type and scope are valid per `cog.toml`

3. Validate before committing:
   - Use `validate_commit_message` to verify format
   - Use `check_commit_scope` to verify scope is valid

4. Get user authorization:
   - Show the commit message
   - Ask for confirmation
   - Only proceed after user says "run just agent-commit" or similar authorization

5. Execute the commit:
   - Use `smart_commit` with the validated message
   - Report the result including commit hash
```

## Git Review Prompt

When reviewing git changes, provide:

1. Summary of changed files
2. Key modifications in each file
3. Potential issues or concerns
4. Suggestions for improvement

## Conflict Resolution Prompt

When encountering merge conflicts:

1. Identify conflicting files
2. Explain the conflict nature
3. Present options for resolution
4. Seek user guidance on resolution strategy
5. After resolution, stage and commit appropriately
