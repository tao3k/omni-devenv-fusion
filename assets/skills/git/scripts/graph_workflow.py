"""
git/scripts/graph_workflow.py - Smart Commit Workflow

Simplified implementation without LangGraph interrupt pattern:
1. start: Stage files, scan, return diff for LLM analysis
2. approve: Direct commit execution with message
3. status: Check workflow status

Uses simple in-memory state (no checkpointer needed).
"""

from typing import Dict, Any, Optional
import asyncio
import uuid

from .commit_state import create_initial_state


async def _start_smart_commit_async(
    project_root: str = ".",
) -> Dict[str, Any]:
    """Start smart commit workflow - stage and scan files."""
    from agent.core.skill_manager.manager import SkillManager

    skill_manager = SkillManager()
    wf_id = str(uuid.uuid4())[:8]

    # Run stage_and_scan to get data
    result_raw = await skill_manager.run("git", "stage_and_scan", {"root_dir": project_root})

    # Handle both dict and string return types
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

    # Create initial state
    initial_state = create_initial_state(project_root=project_root, workflow_id=wf_id)
    initial_state["staged_files"] = staged_files
    initial_state["diff_content"] = diff
    initial_state["security_issues"] = security_issues

    # Set status based on results
    if not staged_files:
        initial_state["status"] = "empty"
    elif lefthook_error:
        initial_state["status"] = "lefthook_failed"
        initial_state["error"] = lefthook_error
    elif security_issues:
        initial_state["status"] = "security_violation"
    else:
        initial_state["status"] = "prepared"

    result = dict(initial_state)
    result["workflow_id"] = wf_id
    return result


async def _approve_smart_commit_async(
    message: str,
    workflow_id: str,
    project_root: str = ".",
) -> Dict[str, Any]:
    """Approve and execute commit with the given message."""
    from agent.core.skill_manager.manager import SkillManager

    skill_manager = SkillManager()

    # Execute commit directly
    result = await skill_manager.run(
        "git", "git_commit", {"message": message, "project_root": project_root}
    )

    return {
        "status": "committed",
        "final_message": message,
        "workflow_id": workflow_id,
        "commit_result": result,
    }


async def _get_workflow_status_async(workflow_id: str) -> Optional[Dict[str, Any]]:
    """Get workflow status - returns None since we don't persist state."""
    return None


def visualize_workflow() -> str:
    """Generate a Mermaid diagram of the workflow."""
    return """```mermaid
graph TD
    A[Start: git.smart_commit action=start] --> B[Stage & Scan Files]
    B --> C{Results}
    C -->|Empty| D[Show: Nothing to commit]
    C -->|Lefthook Failed| E[Show: Fix errors and retry]
    C -->|Security Issues| F[Show: Review sensitive files]
    C -->|Prepared| G[Return diff for LLM analysis]
    G --> H[User approves with message]
    H --> I[git.smart_commit action=approve]
    I --> J[Execute: git.git_commit]
    J --> K[Done]
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
            result = await _start_smart_commit_async()
            wf_id = result.get("workflow_id", "unknown")
            diff = result.get("diff_content", "")[:1000]
            files = result.get("staged_files", [])
            status = result.get("status", "unknown")

            if status == "empty":
                return "🤷 **Nothing to commit** - No staged files detected."

            if status == "lefthook_failed":
                return (
                    f"❌ **Lefthook Pre-commit Failed**\n\n{result.get('error', 'Unknown error')}"
                )

            if status == "security_violation":
                issues = result.get("security_issues", [])
                return f"⚠️ **Security Issue Detected**\n\nSensitive files detected:\n{', '.join(issues)}\n\nPlease resolve these issues before committing."

            return f"""✅ **Smart Commit Started**

**Workflow ID**: `{wf_id}`

**Files to commit** ({len(files)}):
```
{"\n".join(f"- {f}" for f in files[:10])}
```

**Diff preview** (first 1000 chars):
```
{diff}
```

---
💡 **Next steps**:
1. LLM analyzes diff → generates commit message
2. User reviews and says "Yes" to approve
3. To approve: `git.smart_commit(action="approve", workflow_id="{wf_id}", message="your message")`

📊 Check status: `git.smart_commit(action="status", workflow_id="{wf_id}")`
"""

        elif action == "approve":
            if not workflow_id:
                return "❌ **workflow_id required** for approve action"
            if not message:
                return "❌ **message required** for approve action"

            result = await _approve_smart_commit_async(workflow_id=workflow_id, message=message)

            return f"""✅ **Commit Approved & Executed**

**Status**: {result.get("status", "unknown")}
**Message**: {message}

🗃️ Workflow ID `{workflow_id}` completed."""

        elif action == "reject":
            if not workflow_id:
                return "❌ **workflow_id required** for reject action"
            return f"""❌ **Commit Cancelled**

Workflow `{workflow_id}` has been cancelled."""

        elif action == "status":
            if not workflow_id:
                return "❌ **workflow_id required** for status action"
            return f"""⚠️ **Status tracking requires persistent storage**

Workflow `{workflow_id}` - please use approve or reject action."""

        elif action == "visualize":
            diagram = visualize_workflow()
            return f"📊 **Smart Commit Workflow**\n\n{diagram}"

        else:
            return f"❌ Unknown action: {action}"

    except Exception as e:
        import traceback

        return f"🔥 **Error**: {e}\n\n```\n{traceback.format_exc()}\n```"


__all__ = [
    "start_smart_commit",
    "approve_smart_commit",
    "get_workflow_status",
    "visualize_workflow",
    "smart_commit",
]
