# Phase 16: The Neural Bridge (Active RAG for Agents)

**Status**: Implemented
**Type**: Architecture Enhancement
**Owner**: BaseAgent (The Foundation)
**Vision**: Agents retrieve relevant project knowledge before execution

## 1. Problem Statement

**The Pain: Blank Slate Agents**

```
User: "Follow our Python coding standards."

Agent: "What standards? Let me read_file the docs..."
→ Wastes 3 tool calls just to understand the rules
```

**What's Wasted:**

- Agents start with zero project context
- Must manually call read_file for every document reference
- No awareness of coding standards, patterns, or conventions
- Repeated "read_file standards" calls across sessions

**Root Cause:**
Agents have no built-in mechanism to retrieve project knowledge automatically.

## 2. The Solution: Active RAG

Before executing, agents automatically retrieve relevant knowledge:

```
User: "Fix SQL injection in login"

1. BaseAgent.prepare_context()
2. VectorStore.search("Fix SQL injection in login")
3. Found: security.md, lang-python.md standards
4. Inject knowledge into system prompt
5. Agent executes with full context
```

### Result

```
# ROLE: Senior Python Architect

## 🧠 RELEVANT PROJECT KNOWLEDGE
- **agent/skills/knowledge/standards/lang-python.md**:
  Use Pydantic for type validation. Write docstrings for all public functions.

- **agent/knowledge/security.md**:
  Security Standard: Always hash passwords with bcrypt before logging.

## 📋 CURRENT MISSION
Fix SQL injection vulnerability in login function
```

## 3. Architecture Specification

### 3.1 Settings Configuration

```yaml
# agent/settings.yaml
knowledge:
  directories:
    - path: "agent/knowledge"
      domain: "knowledge"
      description: "Project knowledge base"
    - path: "agent/how-to"
      domain: "workflow"
      description: "How-to guides"
    - path: "docs/explanation"
      domain: "architecture"
      description: "Architecture docs"
    - path: "agent/skills/knowledge/standards"
      domain: "standards"
      description: "Coding standards"
```

### 3.2 RAG Method in BaseAgent

```python
async def _retrieve_relevant_knowledge(
    self,
    query: str,
    n_results: int = 3
) -> str:
    """
    Phase 16: Retrieve relevant project knowledge from VectorStore.

    Returns formatted string for system prompt injection.
    """
    vm = get_vector_memory()
    results = await vm.search(query, n_results=n_results)

    if not results:
        return ""

    # Filter by similarity (distance < 0.3 means high similarity)
    # ChromaDB distance: 0.0 = identical, smaller = more similar
    filtered = [r for r in results if r.distance < 0.3]

    if not filtered:
        return ""

    # Format as markdown sections
    sections = []
    for r in filtered:
        source = r.metadata.get("source_file", r.metadata.get("title", "Knowledge"))
        # Truncate to prevent context explosion (800 chars per doc)
        content = r.content[:800] + ("..." if len(r.content) > 800 else "")
        sections.append(f"- **{source}**:\n  {content}")

    return "\n## 🧠 RELEVANT PROJECT KNOWLEDGE\n" + "\n".join(sections)
```

### 3.3 AgentContext Enhancement

```python
class AgentContext(BaseModel):
    system_prompt: str
    tools: List[Dict[str, Any]] = []
    mission_brief: str
    constraints: List[str] = []
    relevant_files: List[str] = []
    knowledge_context: str = ""  # Phase 16: RAG knowledge injection
```

### 3.4 RAG Control per Agent Type

| Agent             | RAG Enabled   | Rationale                                |
| ----------------- | ------------- | ---------------------------------------- |
| **CoderAgent**    | Yes (default) | Needs patterns, standards, existing code |
| **ReviewerAgent** | No (explicit) | Uses own quality tools, not patterns     |

```python
class ReviewerAgent(BaseAgent):
    async def prepare_context(
        self,
        mission_brief: str,
        constraints: List[str] = None,
        relevant_files: List[str] = None
    ) -> AgentContext:
        """Phase 16: Reviewer doesn't need RAG - uses own quality tools."""
        return await super().prepare_context(
            mission_brief=mission_brief,
            constraints=constraints,
            relevant_files=relevant_files,
            enable_rag=False  # Disable RAG
        )
```

## 4. File Changes

### 4.1 New Files

| File                                                                  | Purpose                   |
| --------------------------------------------------------------------- | ------------------------- |
| `packages/python/agent/src/agent/tests/test_phase16_neural_bridge.py` | RAG tests (10 test cases) |

### 4.2 Modified Files

| File                                                                 | Change                                  |
| -------------------------------------------------------------------- | --------------------------------------- |
| `packages/python/agent/src/agent/capabilities/knowledge_ingestor.py` | Add settings.yaml support, Rich output  |
| `packages/python/agent/src/agent/core/agents/base.py`                | Add RAG method, knowledge_context field |
| `packages/python/agent/src/agent/core/agents/reviewer.py`            | Disable RAG in prepare_context          |

## 5. Knowledge Directories

### Default Directories

| Path                               | Domain       | Description            |
| ---------------------------------- | ------------ | ---------------------- |
| `agent/knowledge`                  | knowledge    | Project knowledge base |
| `agent/how-to`                     | workflow     | How-to guides          |
| `docs/explanation`                 | architecture | Architecture docs      |
| `agent/skills/knowledge/standards` | standards    | Coding standards       |

### Knowledge Ingestion

```python
# Usage
from agent.capabilities.knowledge_ingestor import ingest_all_knowledge

await ingest_all_knowledge()  # Ingest all configured directories
```

## 6. Implementation Plan

### Step 1: Knowledge Ingestor Enhancement

- [x] Add `get_knowledge_dirs()` with settings.yaml support
- [x] Add Rich-powered terminal output
- [x] Implement concurrent ingestion with asyncio.gather

### Step 2: BaseAgent RAG Integration

- [x] Add `AgentContext.knowledge_context` field
- [x] Add `_retrieve_relevant_knowledge()` method
- [x] Update `prepare_context()` with `enable_rag` parameter
- [x] Update `_build_system_prompt()` to inject knowledge

### Step 3: Agent-Specific Configuration

- [x] CoderAgent: RAG enabled by default
- [x] ReviewerAgent: Explicitly disable RAG

### Step 4: Testing

- [x] Test knowledge injection
- [x] Test no results handling
- [x] Test similarity filtering (distance < 0.3)
- [x] Test Reviewer skips RAG
- [x] Test error handling (RAG failure doesn't crash)

## 7. Success Criteria

1. **Knowledge Retrieval**: Agents retrieve relevant docs before execution
2. **Configurability**: Users can configure knowledge directories via settings.yaml
3. **Similarity Filtering**: Low-similarity results (< 0.7) are filtered out
4. **Content Truncation**: Long documents truncated to 800 chars
5. **Test Coverage**: All 10 Phase 16 tests pass

## 8. Before vs After Comparison

### ❌ Before (Phase 15)

```
Agent: "What coding standards? Let me read_file lang-python.md..."
→ 3 tool calls wasted just to get context
```

### ✅ After (Phase 16)

```
Agent: (Automatically retrieves relevant knowledge)
→ Context already in system prompt
→ No wasted tool calls
→ Immediate execution with full context
```

## 9. Performance Impact

| Metric            | Before   | After                  |
| ----------------- | -------- | ---------------------- |
| First execution   | Baseline | +10-50ms (RAG search)  |
| Tool calls saved  | 0        | 2-5 per task           |
| Context awareness | None     | Full project knowledge |

## 10. Example Output

### System Prompt with Knowledge Injection

```
# ROLE: Senior Python Architect

## 📋 CURRENT MISSION (From Orchestrator)
==================================================
Fix the auth bug in login.py
==================================================

## 🧠 RELEVANT PROJECT KNOWLEDGE
- **agent/skills/knowledge/standards/lang-python.md**:
  Use Pydantic for type validation. Write docstrings for all public functions.

- **agent/knowledge/security.md**:
  Security Standard: Always hash passwords with bcrypt before logging.

## 🛠️ YOUR CAPABILITIES
- [filesystem]: File system operations
- [file_ops]: Read, write, edit files
- [python_engineering]: Python development

## ⚠️ CONSTRAINTS
- Follow Python coding standards
- Write tests for new code
- Update documentation

## 📁 RELEVANT FILES
- src/auth/login.py

## 🎯 EXECUTION RULES
- Focus ONLY on the mission above
- Use the provided tools precisely
- If unclear, ask for clarification
```

## 11. Related Documentation

- `docs/explanation/mcp-architecture-roadmap.md` - Phase 16 section
- `packages/python/agent/src/agent/core/agents/base.py` - BaseAgent, RAG implementation
- `packages/python/agent/src/agent/capabilities/knowledge_ingestor.py` - Knowledge ingestion
- `packages/python/agent/src/agent/tests/test_phase16_neural_bridge.py` - Test suite
- `agent/how-to/rag-usage.md` - How to use RAG
