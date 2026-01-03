# Spec: Phase 11 - The Neural Matrix (RAG-Enhanced Self-Evolving System)

> **Status**: Approved
> **Complexity**: L3
> **Owner**: @omni-orchestrator

## 1. Context & Goal (Why)

_Building a RAG-enhanced, self-evolving system with persistent state and human-in-the-loop authorization._

The original system lacked:

1. **Type-safe AI outputs**: Prompt-based responses without schema validation
2. **Persistent workflow state**: Token-based auth that required manual copy-paste
3. **Neural memory**: No semantic retrieval of past decisions and patterns

**Goal**: Create a "Neural Matrix" that:

- Uses Pydantic for type-safe, structured AI outputs
- Uses LangGraph for persistent, interruptible workflows
- Supports RAG-based memory recall for context-aware decisions

## 2. Architecture & Interface (What)

### 2.1 File Changes

| File                                      | Action   | Purpose                                        |
| ----------------------------------------- | -------- | ---------------------------------------------- |
| `src/agent/core/schema.py`                | Created  | Pydantic models for type-safe outputs          |
| `src/agent/core/workflows/commit_flow.py` | Created  | LangGraph workflow for Smart Commit V2         |
| `src/agent/capabilities/product_owner.py` | Modified | Added `start_spec` tool with Pydantic patterns |
| `src/agent/main.py`                       | Modified | Added `smart_commit`, `confirm_commit` tools   |

### 2.2 Data Structures / Schema

```python
# agent/core/schema.py

class SpecGapAnalysis(BaseModel):
    """Analysis of spec completeness gaps."""
    spec_exists: bool
    spec_path: Optional[str]
    completeness_score: int = Field(..., ge=0, le=100)
    missing_sections: List[str]
    has_template_placeholders: bool
    test_plan_defined: bool

class LegislationDecision(BaseModel):
    """Final gatekeeper decision for new work."""
    decision: Literal["allowed", "blocked"]
    reasoning: str
    required_action: Literal["create_spec", "update_spec", "proceed_to_code"]
    gap_analysis: SpecGapAnalysis

class CommitState(TypedDict):
    """LangGraph state for commit workflow."""
    diff: str
    context: str
    analysis: str
    risk_level: Literal["low", "medium", "high"]
    user_decision: Literal["pending", "approved", "rejected"]
    commit_hash: Optional[str]
    error: Optional[str]
```

### 2.3 API Signatures (Pseudo-code)

```python
# Phase 11 Smart Commit V2

async def smart_commit(context: str = "") -> dict:
    """
    Start LangGraph workflow for human-in-the-loop commit.

    Flow: Analyze -> Interrupt -> User Decision -> Execute

    Returns:
        {
            "status": "authorization_required",
            "session_id": "abc123",
            "analysis": "...",
            "risk_level": "low",
            "suggested_message": "feat(core): add Phase 11"
        }
    """

async def confirm_commit(session_id: str, decision: str, final_msg: str = "") -> dict:
    """
    Resume suspended workflow with user decision.

    Returns:
        {
            "status": "success",
            "commit_hash": "abc1234"
        }
    """
```

## 3. Implementation Plan (How)

1. [x] **Step 1: PydanticAI Schema Foundation**
   - [x] Created `src/agent/core/schema.py` with type-safe models
   - [x] Added `start_spec` tool with structured output in `product_owner.py`

2. [x] **Step 2: LangGraph Workflow Implementation**
   - [x] Created `src/agent/core/workflows/commit_flow.py`
   - [x] Implemented `analyze` -> `human_gate` -> `execute` flow
   - [x] Added `interrupt_before=["execute"]` for human approval
   - [x] Integrated `smart_commit`, `confirm_commit` tools in `main.py`

3. [ ] **Step 3: Vector Memory (Future)**
   - [ ] Add ChromaDB integration for RAG
   - [ ] Implement `RecallHook` for automatic context injection
   - [ ] Create `Harvester` for pattern extraction

## 4. Verification Plan (Test)

_How do we know it works? Matches `agent/standards/feature-lifecycle.md` requirements._

### 4.1 Unit Tests

```python
# tests/test_phase11_schema.py

def test_spec_gap_analysis():
    """Verify spec gap analysis calculates score correctly."""
    gap = _analyze_spec_gap("agent/specs/existing_spec.md")
    assert gap["completeness_score"] >= 0
    assert gap["completeness_score"] <= 100

def test_commit_workflow_graph():
    """Verify LangGraph workflow compiles correctly."""
    workflow = create_commit_workflow()
    assert workflow is not None

def test_smart_commit_no_staged():
    """Verify error when no staged changes."""
    result = await smart_commit()
    assert result["status"] == "error"
```

### 4.2 Integration Tests

```python
def test_full_commit_flow():
    """Test complete Analyze -> Wait -> Execute flow."""
    # 1. Start workflow
    result = await smart_commit(context="Test commit")
    assert result["status"] == "authorization_required"
    session_id = result["session_id"]

    # 2. Confirm (simulate user approval)
    result = await confirm_commit(session_id, "approved")
    assert result["status"] == "success"
    assert "commit_hash" in result
```

### 4.3 Test Commands

```bash
# Run Phase 11 specific tests
pytest src/agent/tests/test_phase11.py -v

# Run all agent tests
pytest src/agent/tests/ -v

# Verify schema imports
python -c "from core.schema import *; print('Schema OK')"
```
