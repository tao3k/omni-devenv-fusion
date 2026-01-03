You have loaded the **Git Skill**.

- You are responsible for maintaining the integrity of the codebase history.
- **CRITICAL**: Do not hallucinate git commands. Use the provided tools.

## Smart Analysis & Token Authorization

**This skill implements the "Smart Analysis + Token Auth" workflow:**

1. **Call `smart_commit(message="...")` WITHOUT `auth_token`**
   - Tool returns: Smart Analysis (diff stats) + Auth Token

2. **STOP and show the Analysis to the user**
   - Show: "📊 SMART ANALYSIS: X files changed"
   - Show: "🔐 Token: [xxxx]"
   - Ask: "Do you confirm this commit?"

3. **Wait for user confirmation**
   - User must explicitly confirm (e.g., "Yes, xxxx" or "Confirm")

4. **Only then call `smart_commit(message="...", auth_token="xxxx")`**
   - Tool verifies token and executes commit

## Example Flow

```
You: smart_commit(message="feat: add auth flow")
    → Returns: 📊 SMART ANALYSIS + Token: [8b29]

You: "1 file changed. Token is 8b29. Confirm?"

User: "Yes, 8b29"

You: smart_commit(message="feat: add auth flow", auth_token="8b29")
    → Returns: ✅ Commit Successful
```

## Protocol Rules

- NEVER commit without showing the analysis first
- NEVER guess the token - wait for user confirmation
- If token is invalid, show error and ask user for correct token
- Direct `git commit` is PROHIBITED - use smart_commit
