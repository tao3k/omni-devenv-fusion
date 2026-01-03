# Phase 13: Skill-Centric Architecture Reformation

**Status**: Draft
**Type**: Architecture Refactor
**Owner**: Orchestrator (The Brain)
**Vision**: `docs/explanation/vision-skill-centric-os.md`

## 1. Problem Statement

Current Tri-MCP architecture loads ALL tools into the Orchestrator's context at startup:

1. **Token Waste**: The "Git" tools are loaded even when we are just doing "Python" work.
2. **Cognitive Load**: The LLM gets confused by having too many unrelated tools available.
3. **Rigidity**: Adding a new domain (e.g., Kubernetes) requires modifying the core `orchestrator.py`.

## 2. The Solution: Dynamic Skills

Refactor the system to treat capabilities as **"Skills"** that are dynamically loaded/unloaded by the Orchestrator Runtime.

```
Skill = Manifest + Tools + Knowledge
```

## 3. Architecture Specification

### 3.1 Directory Structure (`agent/skills/`)

Move away from `mcp-server/*.py` monoliths:

```text
agent/skills/
├── _template/              # Template for new skills
├── git/                    # The "Git" Skill (Refactored from git_ops.py)
│   ├── manifest.json       # Metadata (name, description, tool_definitions)
│   ├── tools.py            # The executable MCP tools
│   ├── guide.md            # "How to use" (Procedural Knowledge)
│   └── prompts.md          # System prompt injection
├── filesystem/             # The "Coder" Skill (Refactored from coder.py)
└── ...
```

### 3.2 The Skill Registry (`src/agent/core/skill_registry.py`)

A new core module responsible for:

- Scanning `agent/skills/` for valid manifests.
- Providing `list_skills()` and `get_skill_context(name)`.
- Managing the lifecycle of skills.

### 3.3 The Dynamic Loader (Orchestrator Update)

Update `src/agent/main.py` to support dynamic tool registration.

**Current**: Static `register_git_ops_tools(mcp)`

**New**:
```python
@mcp.tool()
async def load_skill(skill_name: str):
    """Dynamically loads a skill's tools and context."""
    registry.load(skill_name, mcp_server)
```

## 4. Migration Plan

### Step 1: Infrastructure (The Foundation)

- Create `src/agent/core/skill_registry.py`.
- Define `SkillManifest` schema in `src/agent/core/schema.py`.

### Step 2: The Pilot (Refactor GitOps)

- Create `agent/skills/git/`.
- Move logic from `mcp-server/git_ops.py` to `agent/skills/git/tools.py`.
- Move knowledge from `agent/how-to/git-workflow.md` to `agent/skills/git/guide.md`.

### Step 3: The Brain Transplant

- Update `orchestrator.py` to use the Registry.
- Remove hardcoded `git_ops` registration.

## 5. Success Criteria

1. **Zero Initial Load**: Orchestrator starts with no skills loaded (only `load_skill` tool)
2. **Dynamic Loading**: `load_skill("git")` makes git tools available
3. **Context Injection**: Skill guide.md content is injected into LLM context
4. **Git Ops Preserved**: All git operations work exactly as before

## 6. Skill Template

### 6.1 manifest.json Schema

```json
{
  "name": "git",
  "version": "1.0.0",
  "description": "Version control operations using Git",
  "category": "development",
  "dependencies": [],
  "tools": ["git_status", "git_diff", "smart_commit"],
  "context_files": ["agent/skills/git/guide.md"]
}
```

### 6.2 File Structure

```
agent/skills/{skill_name}/
├── manifest.json              # Metadata
├── guide.md                   # Procedural Knowledge
├── tools.py                   # MCP Tools
└── prompts.md                 # System prompts
```

## 7. Related Documentation

- `docs/explanation/vision-skill-centric-os.md` - The vision
- `agent/how-to/git-workflow.md` - To be ported to git/guide.md
- `src/agent/capabilities/skill_registry.py` - The registry implementation
