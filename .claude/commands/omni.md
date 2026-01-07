---
description: Execute an Omni Skill command
argument-hint: [skill.command] [args]
---

Execute Omni Command: $ARGUMENTS
Use the **@omni** MCP tool to perform this action.

Examples (use @omni tool with these arguments):

- `/omni git.status` -> @omni("git.status")
- `/omni skill.discover docker` -> @omni("skill.discover", {"query": "docker"})
- `/omni skill.suggest analyze pcap` -> @omni("skill.suggest", {"task": "analyze pcap"})
- `/omni skill.jit_install docker-ops` -> @omni("skill.jit_install", {"skill_id": "docker-ops"})
- `/omni skill.list_index` -> @omni("skill.list_index")
- `/omni memory.load_skill git` -> @omni("memory.load_skill", {"skill_name": "git"})
- `/omni memory.load_activated_skills` -> @omni("memory.load_activated_skills", {})
- `/omni crawl4ai.crawl_webpage https://example.com` -> @omni("crawl4ai.crawl_webpage", {"url": "https://example.com"})
- `/omni filesystem.read_file README.md` -> @omni("filesystem.read_file", {"path": "README.md"})
