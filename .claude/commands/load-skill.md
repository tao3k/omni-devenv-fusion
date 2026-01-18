---
description: Load a skill into semantic memory
argument-hint: [skill_name]
---

Load the skill into LanceDB for semantic recall:
Call @omni("memory.load_skill", {"skill_name": "$ARGUMENT"})

Examples:

- `/load-skill git`
- `/load-skill terminal`
- `/load-skill memory`
