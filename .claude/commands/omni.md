---
description: Execute an Omni Skill command
argument-hint: [skill.command] [args]
---

Execute Omni Command: $ARGUMENTS
Use the @omni tool to perform this action.

Examples:

- `/omni git.status` -> omni("git.status")
- `/omni memory.load_skill git` -> omni("memory.load_skill", {"skill_name": "git"})
- `/omni memory.load_activated_skills` -> omni("memory.load_activated_skills", {})
