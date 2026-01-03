# Phase 13: The Skill-First Reformation

**Status**: Draft
**Created**: 2026-01-02
**Author**: Claude Code

## 1. Vision

Transform Omni-DevEnv from a tool-centric architecture to a **Skill-centric architecture**.

Instead of monolithic "Agents" with 20+ scattered tools, we build composable **Skills** that include:

- Procedural knowledge (How-to guides)
- Specific tools (MCP tool definitions)
- Validation rules (Best practices)

This follows Anthropic's "Don't Build Agents, Build Skills"理念.

## 2. The "Skill" Anatomy (Standardized Structure)

```
agent/skills/
├── git_operations/
│   ├── manifest.json              # Metadata: name, version, description
│   ├── guide.md                   # Procedural Knowledge (How-to)
│   ├── tools.py                   # MCP Tools (Execution Logic)
│   └── prompts.md                 # Skill-specific system prompts
├── python_engineering/
│   ├── manifest.json
│   ├── guide.md
│   └── tools.py
└── task_management/               # The new Task Weaver
    ├── manifest.json
    ├── guide.md
    ├── tools.py
    └── prompts.md
```

### 2.1 manifest.json Schema

```json
{
  "name": "git_operations",
  "version": "1.0.0",
  "description": "Version control operations using Git",
  "category": "development",
  "dependencies": [],
  "tools": ["git_status", "git_diff", "smart_commit"],
  "context_files": ["agent/how-to/git-workflow.md"]
}
```

### 2.2 guide.md

Procedural knowledge - step-by-step instructions for the skill.

### 2.3 tools.py

MCP tool implementations specific to this skill.

### 2.4 prompts.md

Skill-specific system prompts for LLM context.

## 3. Core Components to Build

### 3.1 The Skill Registry (New Capability)

**Location**: `src/agent/capabilities/skill_registry.py`

```python
class SkillManifest(BaseModel):
    name: str
    version: str
    description: str
    category: str
    tools: List[str]
    context_files: List[str] = []
    dependencies: List[str] = []

class SkillRegistry:
    """Discover and manage available skills."""
    def list_skills() -> List[SkillManifest]
    def get_skill_manifest(name: str) -> SkillManifest
    def load_skill(name: str) -> SkillContext
    def unload_skill(name: str) -> None
```

### 3.2 The Dynamic Loader (Orchestrator Upgrade)

**Problem**: Loading ALL tools into context consumes too many tokens.

**Solution**: Orchestrator dynamically loads/unloads skills based on user intent.

- User: "Fix this bug." → Load `debugging_skill` + `git_skill`
- User: "Design system." → Load `architecture_skill`

### 3.3 Skill Context

When a skill is loaded, it provides:

1. MCP tools defined in `tools.py`
2. Procedural knowledge from `guide.md`
3. System prompts from `prompts.md`

## 4. Migration Plan

The migration will proceed in 5 phases:

### Phase 1: Base Structure

The project must first establish the `agent/skills/` directory structure and the `SkillRegistry` capability in `src/agent/capabilities/skill_registry.py`. This foundational work defines the `SkillManifest` and `SkillContext` models that all skills will follow.

### Phase 2: Git Operations Skill

The first skill to port will be Git Operations, consisting of `agent/skills/git_operations/manifest.json` for metadata, `agent/skills/git_operations/guide.md` containing git workflow procedures, `agent/skills/git_operations/tools.py` with MCP tool implementations, and `agent/skills/git_operations/prompts.md` providing git-specific system prompts.

### Phase 3: Python Engineering Skill

The second skill will be Python Engineering, including `agent/skills/python_engineering/manifest.json`, `agent/skills/python_engineering/guide.md` with PEP8 and Pydantic standards, and `agent/skills/python_engineering/tools.py` for linting and testing utilities.

### Phase 4: FileSystem Skill

The third skill will be FileSystem operations, mirroring the Coder capabilities in `agent/skills/filesystem/manifest.json`, `agent/skills/filesystem/guide.md`, and `agent/skills/filesystem/tools.py`.

### Phase 5: Dynamic Loading Implementation

Finally, the Orchestrator will be updated to use the Skill Registry for dynamic loading and unloading of skills based on user intent, with new `load_skill` and `unload_skill` tools added.

## 5. First New Skill: The Task Weaver

Instead of a separate "Phase", the **Task Weaver** becomes the first complex **Skill** we build:

```
agent/skills/task_management/
├── manifest.json
├── guide.md          # Planning methodology
├── tools.py          # Task CRUD, sqlite persistence
└── prompts.md        # Planner prompts
```

## 6. Success Criteria

### Technical Requirements Met

The project succeeds when `agent/skills/` directory contains at least 3 core skills (Git, Python, FileSystem). The `SkillRegistry` capability must be fully implemented with `list_skills()` and `get_skill_manifest()` functions operational. The Orchestrator must demonstrate the ability to dynamically load a skill's tools into context while keeping unloaded skills invisible to the LLM, and inject skill-specific prompts from `prompts.md` files.

### Quality Requirements Met

Each skill must have a complete manifest containing name, version, and description fields. Every skill must include `guide.md` with actionable procedures and `tools.py` with properly decorated MCP tools. The Harvester capability must be able to suggest improvements to specific Skills.

### Migration Requirements Met

All existing functionality must be preserved during the migration with no breaking changes to MCP tool interfaces. The system must maintain backward compatibility with existing `consult_*` tools throughout the transition.

## 7. Implementation Order

1. Create `agent/skills/` and base manifest schema
2. Build `SkillRegistry` capability
3. Port Git Operations as first skill
4. Implement dynamic loading in Orchestrator
5. Port remaining skills (Python, FileSystem)
6. Create Task Management skill

## 8. Anticipated Challenges

1. **Token Optimization**: Ensure dynamic loading actually reduces context size
2. **Dependency Resolution**: Skills may depend on other skills
3. **Migration Path**: Gradually move existing capabilities without breaking

## 9. Related Documentation

- `agent/how-to/git-workflow.md` - To be ported to git_operations/guide.md
- `agent/standards/lang-python.md` - To be ported to python_engineering/guide.md
