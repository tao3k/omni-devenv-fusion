# agent/core/workflows/commit_flow.py
"""
LangGraph workflow for Smart Commit with Human-in-the-loop.

Phase 11: The Neural Matrix - Step 2: Nervous System

Features:
- State persistence across interruptions
- Human-in-the-loop authorization
- Structured state machine for commit workflow

Flow: Analyze -> Wait Authorization -> Execute
"""
import logging
import subprocess
from pathlib import Path
from typing import TypedDict, Literal, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger("commit_flow")

# =============================================================================
# State Definition
# =============================================================================

class CommitState(TypedDict):
    """State for the Smart Commit workflow."""
    # Input
    diff: str
    context: str

    # Intermediate
    analysis: str  # Immune system analysis result
    risk_level: Literal["low", "medium", "high"]
    suggested_msg: str  # Suggested commit message

    # Decision (Human-in-the-loop)
    user_decision: Literal["pending", "approved", "rejected"]
    final_msg: Optional[str]

    # Output
    commit_hash: Optional[str]
    error: Optional[str]


# =============================================================================
# Node Functions
# =============================================================================

def node_analyze(state: CommitState) -> CommitState:
    """
    [Analyze Node]
    1. Calls the Immune System (Reviewer) to analyze the diff
    2. Generates risk assessment and commit message
    """
    logger.info("🤖 Analyzing diff and assessing risk...")
    diff = state.get("diff", "")
    context = state.get("context", "")

    # Real implementation: Call reviewer.py for analysis
    try:
        from capabilities.product_owner import COMPLEXITY_LEVELS, heuristic_complexity
        from capabilities import reviewer

        # Get changed files from diff
        changed_files = _extract_files_from_diff(diff)

        # Analyze complexity
        complexity = heuristic_complexity(changed_files, diff)

        # Risk assessment based on complexity
        risk_map = {"L1": "low", "L2": "low", "L3": "medium", "L4": "high"}
        risk = risk_map.get(complexity, "low")

        # Generate commit message suggestion
        suggested_msg = _generate_commit_suggestion(changed_files, complexity, context)

        analysis = f"Analysis completed. Changed {len(changed_files)} file(s). Complexity: {complexity}."

    except Exception as e:
        logger.warning(f"Analysis failed, using fallback: {e}")
        risk = "low"
        if "FORCE" in diff or "rm -rf" in diff or "delete" in diff.lower():
            risk = "high"
        analysis = f"Analysis completed. Risk Level: {risk}"
        suggested_msg = "chore: update via langgraph workflow"

    return {
        "analysis": analysis,
        "risk_level": risk,
        "suggested_msg": suggested_msg,
        "user_decision": "pending"
    }


def node_human_gate(state: CommitState) -> CommitState:
    """
    [Interrupt Node]
    LangGraph will suspend before entering execute node.
    This node serves as a checkpoint.
    """
    logger.info("⏳ Waiting for human authorization...")
    return state


def node_execute(state: CommitState) -> CommitState:
    """
    [Execute Node]
    Execute Git commit based on user decision.
    """
    decision = state.get("user_decision")
    final_msg = state.get("final_msg") or state.get("suggested_msg", "")
    logger.info(f"🚀 Executing with decision: {decision}")

    if decision == "approved":
        try:
            # Get the actual staged diff for commit
            commit_hash = _git_commit(final_msg)
            return {"commit_hash": commit_hash, "error": None}
        except Exception as e:
            return {"error": str(e), "commit_hash": None}

    elif decision == "rejected":
        return {"error": "User rejected the commit.", "commit_hash": None}

    else:
        return {"error": "Invalid state: missing decision", "commit_hash": None}


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_files_from_diff(diff: str) -> list:
    """Extract file names from git diff."""
    files = []
    for line in diff.split('\n'):
        if line.startswith('+++ b/') or line.startswith('--- a/'):
            path = line[6:] if line.startswith('+++ b/') else line[6:]
            if path and path != '/dev/null':
                files.append(path)
    return list(set(files))


def _generate_commit_suggestion(files: list, complexity: str, context: str) -> str:
    """Generate a conventional commit message suggestion."""
    # Determine commit type based on files
    type_map = {
        ("md",): "docs",
        ("nix",): "chore",
        ("py",): "feat" if complexity in ["L3", "L4"] else "fix",
    }

    commit_type = "chore"
    for ext, t in type_map.items():
        if any(f.endswith(ext) for f in files):
            commit_type = t
            break

    # Generate scope from first file
    scope = "core"
    if files:
        first_file = files[0]
        if "mcp" in first_file.lower():
            scope = "mcp"
        elif "agent" in first_file.lower():
            scope = "agent"
        elif "docs" in first_file.lower():
            scope = "docs"

    # Subject from context or files
    subject = context[:50] if context else f"{commit_type}: {scope} update"
    subject = subject.strip().rstrip('.')

    return f"{commit_type}({scope}): {subject}"


def _git_commit(message: str) -> str:
    """Execute git commit and return hash."""
    # First, ensure files are staged
    subprocess.run(["git", "add", "."], check=True, capture_output=True)

    # Get staged diff for the message
    result = subprocess.run(
        ["git", "diff", "--cached", "--stat"],
        capture_output=True, text=True
    )
    stats = result.stdout.strip() if result.stdout else ""

    # Build commit message
    full_msg = f"{message}\n\n[Auto-generated by LangGraph Smart Commit]"

    # Execute commit
    result = subprocess.run(
        ["git", "commit", "-m", full_msg],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        raise Exception(result.stderr)

    # Get commit hash
    hash_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True
    )
    return hash_result.stdout.strip()[:7]


# =============================================================================
# Graph Construction
# =============================================================================

def create_commit_workflow() -> StateGraph:
    """Create and configure the commit workflow graph."""
    workflow = StateGraph(CommitState)

    # Add nodes
    workflow.add_node("analyze", node_analyze)
    workflow.add_node("human_gate", node_human_gate)
    workflow.add_node("execute", node_execute)

    # Set entry point
    workflow.set_entry_point("analyze")

    # Add edges
    workflow.add_edge("analyze", "human_gate")
    workflow.add_edge("human_gate", "execute")
    workflow.add_edge("execute", END)

    return workflow


# Compile with persistence
_checkpointer = MemorySaver()
_commit_workflow = create_commit_workflow().compile(
    checkpointer=_checkpointer,
    interrupt_before=["execute"]  # Suspend before execute node
)


def get_workflow():
    """Get the compiled workflow instance."""
    return _commit_workflow


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "CommitState",
    "create_commit_workflow",
    "get_workflow",
]
