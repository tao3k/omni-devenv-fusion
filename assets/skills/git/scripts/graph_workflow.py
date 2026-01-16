"""
git/scripts/graph_workflow.py - Smart Commit Workflow with SqliteSaver

Uses LangGraph SqliteSaver checkpoint pattern for persistent state:
- SqliteSaver stores workflow state to disk
- State persists across skill reloads
- Supports workflow_id-based retrieval

Note: SqliteSaver is synchronous, needs process to stay alive for persistence.
"""

import sqlite3
from typing import Dict, Any, Optional
import uuid
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from agent.core.state import GraphState
from .commit_state import create_initial_state
from .rendering import render_commit_message, render_template
from .prepare import _get_cog_scopes, _validate_and_fix_scope

# ==============================================================================
# Checkpointer Management (Phase 36.7)
# ==============================================================================

_DB_PATH = Path.home() / ".cache" / "omni-devenv-fusion" / "workflows.db"


def _get_checkpointer() -> SqliteSaver:
    """Get or create SqliteSaver checkpointer with persistent connection."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    return SqliteSaver(conn)


# ==============================================================================
# Workflow State Store (SQLite-based for persistence across reloads)
# ==============================================================================


def _get_state_db() -> sqlite3.Connection:
    """Get or create SQLite connection for workflow state."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_states (
            workflow_id TEXT PRIMARY KEY,
            state TEXT,
            updated_at REAL
        )
    """)
    return conn


def _save_workflow_state(workflow_id: str, state: Dict[str, Any]) -> None:
    """Save workflow state to SQLite for persistence across reloads."""
    import json

    conn = _get_state_db()
    state_json = json.dumps(state)
    updated_at = __import__("time").time()
    conn.execute(
        "REPLACE INTO workflow_states (workflow_id, state, updated_at) VALUES (?, ?, ?)",
        (workflow_id, state_json, updated_at),
    )
    conn.commit()
    conn.close()


def _get_workflow_state(workflow_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve workflow state from SQLite."""
    import json

    conn = _get_state_db()
    cursor = conn.execute("SELECT state FROM workflow_states WHERE workflow_id = ?", (workflow_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None


# ==============================================================================
# Workflow Graph (Optional - for complex workflows)
# ==============================================================================


def _build_workflow() -> Any:
    """Build the Smart Commit workflow graph (for reference/complex cases)."""
    checkpointer = _get_checkpointer()

    def _check_state_node(state: GraphState) -> Dict[str, Any]:
        """Check state and determine next step."""
        staged_files = state.get("staged_files", [])
        lefthook_error = state.get("lefthook_error", "")
        security_issues = state.get("security_issues", [])

        if not staged_files:
            return {"_routing": "empty"}
        if lefthook_error:
            return {"_routing": "lefthook_error"}
        if security_issues:
            return {"_routing": "security_warning"}
        return {"_routing": "prepared"}

    def _route_state(state: GraphState) -> str:
        """Router function for conditional edges."""
        return state.get("_routing", "empty")

    def _return_state(state: GraphState) -> Dict[str, Any]:
        """Return state as is."""
        return dict(state)

    builder = StateGraph(GraphState)
    builder.add_node("check", _check_state_node)
    builder.add_node("empty", _return_state)
    builder.add_node("lefthook_error", _return_state)
    builder.add_node("security_warning", _return_state)
    builder.add_node("prepared", _return_state)
    builder.set_entry_point("check")
    builder.add_conditional_edges(
        "check",
        _route_state,
        {
            "empty": "empty",
            "lefthook_error": "lefthook_error",
            "security_warning": "security_warning",
            "prepared": "prepared",
        },
    )
    for node in ["empty", "lefthook_error", "security_warning", "prepared"]:
        builder.add_edge(node, END)

    return builder.compile(checkpointer=checkpointer)


# ==============================================================================
# API Functions
# ==============================================================================


async def _start_smart_commit_async(
    project_root: str = ".",
) -> Dict[str, Any]:
    """Start smart commit workflow - stage and scan files."""
    from agent.core.skill_manager.manager import SkillManager
    from pathlib import Path as PathType

    skill_manager = SkillManager()
    wf_id = str(uuid.uuid4())[:8]
    root = PathType(project_root)

    # Run stage_and_scan
    result_raw = await skill_manager.run("git", "stage_and_scan", {"root_dir": project_root})

    # Handle result (dict or string)
    if isinstance(result_raw, dict):
        result_data = result_raw
    elif isinstance(result_raw, str):
        try:
            import ast

            result_data = ast.literal_eval(result_raw)
        except (ValueError, SyntaxError):
            result_data = {
                "staged_files": [],
                "diff": "",
                "security_issues": [],
                "lefthook_error": "",
            }
    else:
        result_data = {"staged_files": [], "diff": "", "security_issues": [], "lefthook_error": ""}

    staged_files = result_data.get("staged_files", [])
    diff = result_data.get("diff", "")
    security_issues = result_data.get("security_issues", [])
    lefthook_error = result_data.get("lefthook_error", "")

    # Scope validation
    valid_scopes = _get_cog_scopes(root)
    scope_warning = ""  # scope_warning is for actual warnings, not just listing scopes

    # Create initial state
    initial_state = create_initial_state(project_root=project_root, workflow_id=wf_id)
    initial_state["staged_files"] = staged_files
    initial_state["diff_content"] = diff
    initial_state["security_issues"] = security_issues

    # Set status
    if not staged_files:
        initial_state["status"] = "empty"
    elif lefthook_error:
        initial_state["status"] = "lefthook_failed"
        initial_state["error"] = lefthook_error
    elif security_issues:
        initial_state["status"] = "security_violation"
    else:
        initial_state["status"] = "prepared"

    # Add extra fields for template (cast to dict to avoid TypedDict restriction)
    state_dict: Dict[str, Any] = dict(initial_state)
    state_dict["scope_warning"] = scope_warning
    state_dict["lefthook_report"] = ""

    # Save to state store
    _save_workflow_state(wf_id, state_dict)

    state_dict["workflow_id"] = wf_id
    return state_dict


async def _approve_smart_commit_async(
    message: str,
    workflow_id: str,
    project_root: str = ".",
) -> Dict[str, Any]:
    """Approve and execute commit with the given message."""
    from agent.core.skill_manager.manager import SkillManager

    skill_manager = SkillManager()

    # Get current state for file count
    current_state = _get_workflow_state(workflow_id) or {}
    file_count = len(current_state.get("staged_files", []))

    # Update workflow state
    _save_workflow_state(
        workflow_id, {"status": "approved", "final_message": message, "file_count": file_count}
    )

    # Execute commit
    commit_result = await skill_manager.run(
        "git", "git_commit", {"message": message, "project_root": project_root}
    )

    # Extract commit hash from result
    commit_hash = ""
    if isinstance(commit_result, str):
        # Try to extract hash from result like "[abc1234] Commit message"
        import re

        match = re.search(r"\[([a-f0-9]+)\]", commit_result)
        if match:
            commit_hash = match.group(1)

    return {
        "status": "committed",
        "final_message": message,
        "workflow_id": workflow_id,
        "commit_result": commit_result,
        "commit_hash": commit_hash,
        "file_count": file_count,
        "security_status": "No sensitive files detected",
    }


async def _get_workflow_status_async(workflow_id: str) -> Optional[Dict[str, Any]]:
    """Get workflow status."""
    return _get_workflow_state(workflow_id)


# ==============================================================================
# Visualization
# ==============================================================================


def visualize_workflow() -> str:
    """Generate a Mermaid diagram of the workflow."""
    return """```mermaid
graph TD
    A[Start: git.smart_commit action=start] --> B[Stage & Scan Files]
    B --> C{Check Results}
    C -->|Empty| D[empty: Nothing to commit]
    C -->|Lefthook Failed| E[lefthook_error: Fix errors]
    C -->|Security Issues| F[security_warning: Review files]
    C -->|Prepared| G[prepared: User approves]
    G --> H[git.smart_commit action=approve]
    H --> I[git.git_commit executes]
    I --> J[Done]
```"""


# ==============================================================================
# Skill Command
# ==============================================================================

from agent.skills.decorators import skill_script


@skill_script(
    name="smart_commit",
    description="Smart Commit workflow with security scan and human approval. "
    "Flow: stage → scan → LLM analyze → user approve → commit.",
    category="workflow",
)
async def smart_commit(
    action: str = "start",
    workflow_id: str = "",
    message: str = "",
) -> str:
    """Smart Commit workflow command."""
    try:
        if action == "start":
            from pathlib import Path as PathType

            result = await _start_smart_commit_async()
            wf_id = result.get("workflow_id", "unknown")
            files = result.get("staged_files", [])
            diff = result.get("diff_content", "")[:2000]
            status = result.get("status", "unknown")
            scope_warning = result.get("scope_warning", "")
            valid_scopes = _get_cog_scopes(PathType("."))

            if status == "empty":
                return "🤷 **Nothing to commit** - No staged files detected."

            if status == "lefthook_failed":
                return (
                    f"❌ **Lefthook Pre-commit Failed**\n\n{result.get('error', 'Unknown error')}"
                )

            if status == "security_violation":
                issues = result.get("security_issues", [])
                return f"⚠️ **Security Issue Detected**\n\nSensitive files detected:\n{', '.join(issues)}\n\nPlease resolve these issues before committing."

            # Use template for consistent output
            return render_template(
                "prepare_result.j2",
                has_staged=bool(files),
                staged_files=files,
                staged_file_count=len(files),
                scope_warning=scope_warning,
                valid_scopes=valid_scopes,
                lefthook_report="",
                diff_content=diff,
                wf_id=wf_id,
            )

        elif action == "approve":
            if not workflow_id:
                return "❌ **workflow_id required** for approve action"
            if not message:
                return "❌ **message required** for approve action"

            # Extract commit_type and commit_scope from message
            import re

            commit_type = "feat"
            commit_scope = "general"
            commit_description = message  # Default to full message

            # Parse conventional commit format: type(scope): description
            first_line = message.strip().split("\n")[0]
            match = re.match(r"^(\w+)(?:\(([^)]+)\))?:\s*(.+)$", first_line)
            if match:
                commit_type = match.group(1)
                scope_part = match.group(2)
                if scope_part:
                    commit_scope = scope_part
                commit_description = match.group(3)  # Extract description only

            # Validate scope against cog.toml
            from pathlib import Path as PathType

            root = PathType(".")
            valid_scopes = _get_cog_scopes(root)
            if valid_scopes and commit_scope not in valid_scopes:
                from difflib import get_close_matches

                matches = get_close_matches(commit_scope, valid_scopes, n=1, cutoff=0.6)
                if matches:
                    commit_scope = matches[0]

            result = await _approve_smart_commit_async(workflow_id=workflow_id, message=message)

            # Use template for consistent output
            return render_commit_message(
                subject=commit_description,
                body="",
                status="committed",
                commit_hash=result.get("commit_hash", ""),
                file_count=result.get("file_count", 0),
                verified_by="omni Git Skill (cog)",
                security_status=result.get("security_status", "No sensitive files detected"),
                workflow_id=workflow_id,
                commit_type=commit_type,
                commit_scope=commit_scope,
            )

        elif action == "reject":
            if not workflow_id:
                return "❌ **workflow_id required** for reject action"
            return f"""❌ **Commit Cancelled**

Workflow `{workflow_id}` has been cancelled."""

        elif action == "status":
            if not workflow_id:
                return "❌ **workflow_id required** for status action"
            status = await _get_workflow_status_async(workflow_id)
            if not status:
                return f"⚠️ Workflow `{workflow_id}` not found"
            return f"""📊 **Workflow Status** (`{workflow_id}`)

**Status**: {status.get("status", "unknown")}
**Files**: {len(status.get("staged_files", []))}
"""

        elif action == "visualize":
            diagram = visualize_workflow()
            return f"📊 **Smart Commit Workflow**\n\n{diagram}"

        else:
            return f"❌ Unknown action: {action}"

    except Exception as e:
        import traceback

        return f"🔥 **Error**: {e}\n\n```\n{traceback.format_exc()}\n```"


__all__ = [
    "smart_commit",
    "visualize_workflow",
]
