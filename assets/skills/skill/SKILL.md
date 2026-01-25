---
name: "Skill Manager"
version: "1.0.0"
description: "Manage skills - discover, install, and update from remote repositories"
routing_keywords:
  - "skill"
  - "discovery"
  - "discover"
  - "search"
  - "find"
  - "lookup"
  - "install"
  - "jit"
  - "reload"
  - "unload"
  - "list"
  - "analyze" # For analyzing project capabilities
  - "learn" # For learning about project structure
  - "what can" # For "what can you do" queries
  - "capability"
  - "available"
  - "tools"
  - "commands"
  - "@omni" # All tool calls must go through discover first
authors: ["omni-dev"]
intents:
  - "Discover or search skills"
  - "Find available tools and commands"
  - "Analyze project capabilities"
  - "Learn what tools are available"
  - "Install new skill"
  - "Reload skill"
  - "List available skills"
  - "Get tool usage before calling @omni"
---

# Skill Manager

The Skill Manager provides tools for discovering, installing, and managing skills in the Omni-Dev-Fusion system.

## Commands

### discover

**[CRITICAL] Tool Registry Lookup** - The ONLY way to call @omni commands!

**MANDATORY RULE:** Before calling ANY `@omni(...)` command, you MUST call `skill.discover` first to get the exact tool name and usage template. Direct `@omni` calls are FORBIDDEN.

**When to use:**

- ANY time you want to call a tool via `@omni(...)`
- You are unsure which tool to use
- You need the exact tool name and arguments schema
- You are starting any new task that requires a tool

**Example:**

```
User: "I want to analyze this GitHub repo"
→ Call skill.discover(intent="analyze github repository structure")
→ Returns: @omni("software_engineering.analyze_project_structure", {"depth": 3})
→ NOW call the tool with confidence
```

### jit_install

Install and load a new skill from the remote repository.

### list_index

List all available skills in the system.
