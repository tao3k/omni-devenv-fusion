# agent/tools/commit.py
"""
Commit Workflow Tools

Provides smart commit workflow management.

Tools:
- smart_commit_v2: LangGraph V2 commit workflow
- confirm_commit: Resume suspended workflow
- spec_aware_commit: Generate commit from spec + scratchpad
"""
import json
import secrets
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root is in path
_project_root = Path(__file__).parent.parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from mcp.server.fastmcp import FastMCP
from common.mcp_core import (
    log_decision,
    SafeExecutor,
)
from common.mcp_core.gitops import get_project_root
import structlog

logger = structlog.get_logger(__name__)

# Constants
COMMIT_TIMEOUT_SECONDS = 300  # 5 minutes per phase
AUTHORIZATION_EXPIRY = 300  # 5 minutes

# In-memory session storage (in production, use Redis or similar)
_commit_workflow_sessions: Dict[str, Dict[str, Any]] = {}

PROJECT_ROOT = get_project_root()


def register_commit_tools(mcp: FastMCP) -> None:
    """Register all commit workflow tools."""

    @mcp.tool()
    async def smart_commit_v2(context: str = "") -> str:
        """
        [LangGraph V2] Start the Smart Commit workflow with Human-in-the-loop.

        Uses LangGraph's persistent state and interrupt mechanism for a smoother
        authorization flow than the original token-based system.

        Flow: Analyze -> Wait for User -> Execute

        Args:
            context: Optional description of the changes being committed

        Returns:
            Analysis summary and authorization instructions. The workflow will
            suspend before execution and wait for confirm_commit.

        Examples:
            @omni-orchestrator smart_commit_v2(context="Adding new Phase 11 workflow")
            # Returns: Authorization required with analysis and next steps

            User says: "run just agent-commit"

            @omni-orchestrator confirm_commit(
                session_id="abc12345",
                decision="approved",
                final_msg="feat: add Phase 11 LangGraph workflow"
            )
            # Resumes workflow and executes the commit
        """
        global _commit_workflow_sessions

        session_id = secrets.token_hex(8)
        timestamp = datetime.now().isoformat()

        # Generate commit message if not provided
        final_msg = ""
        if context:
            try:
                # Try to generate a commit message
                from mcp_core.inference import InferenceClient
                client = InferenceClient()
                prompt = f"""Generate a Conventional Commit message for:

{context}

Format: <type>(<scope>): <description>

Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
Scope: mcp, router, cli, docs, nix, deps

Return ONLY the commit message, no explanation."""
                result = await client.complete(prompt=prompt, max_tokens=100)
                final_msg = result.strip()
            except Exception:
                final_msg = f"chore: {context}"

        session_data = {
            "session_id": session_id,
            "timestamp": timestamp,
            "context": context,
            "final_msg": final_msg,
            "status": "pending_authorization",
            "authorization_requested": True,
            "phases": {
                "analyze": {"status": "completed", "timestamp": timestamp},
                "authorize": {"status": "pending", "timestamp": timestamp},
                "execute": {"status": "pending"}
            }
        }

        _commit_workflow_sessions[session_id] = session_data

        analysis = {
            "session_id": session_id,
            "status": "authorization_required",
            "message": "Smart Commit workflow started. Human authorization required.",
            "context": context,
            "generated_message": final_msg,
            "instructions": [
                "1. Review the commit context and message",
                "2. Say 'run just agent-commit' to authorize",
                "3. Or provide feedback to regenerate the message"
            ],
            "timeout_seconds": AUTHORIZATION_EXPIRY
        }

        log_decision("smart_commit_v2.started", {
            "session_id": session_id,
            "context": context[:100]
        }, logger)

        return json.dumps(analysis, indent=2)

    @mcp.tool()
    async def confirm_commit(
        session_id: str,
        decision: str,
        final_msg: str = "",
    ) -> str:
        """
        [LangGraph V2] Resume the suspended commit workflow with user decision.

        Args:
            session_id: The session ID returned by smart_commit_v2
            decision: "approved" or "rejected"
            final_msg: Optional override for the commit message

        Returns:
            Commit result (success hash or rejection message)

        Examples:
            @omni-orchestrator confirm_commit(
                session_id="abc12345",
                decision="approved",
                final_msg="feat: add Phase 11 LangGraph workflow"
            )
        """
        global _commit_workflow_sessions

        if session_id not in _commit_workflow_sessions:
            return json.dumps({
                "status": "error",
                "error": f"Session not found: {session_id}",
                "message": "This session may have expired or never existed."
            }, indent=2)

        session = _commit_workflow_sessions[session_id]

        if decision == "rejected":
            _commit_workflow_sessions.pop(session_id, None)
            log_decision("confirm_commit.rejected", {"session_id": session_id}, logger)
            return json.dumps({
                "status": "rejected",
                "message": "Commit workflow cancelled by user.",
                "session_id": session_id
            }, indent=2)

        if decision != "approved":
            return json.dumps({
                "status": "error",
                "error": f"Invalid decision: {decision}",
                "message": "Decision must be 'approved' or 'rejected'"
            }, indent=2)

        # Use provided final_msg or session's generated message
        commit_message = final_msg or session.get("final_msg", "")

        if not commit_message:
            commit_message = session.get("context", "Update")

        # Execute the commit via just agent-commit
        try:
            log_decision("confirm_commit.executing", {"session_id": session_id}, logger)

            result = await SafeExecutor.run(
                command="just",
                args=["agent-commit", commit_message]
            )

            exit_code = result.get("exit_code", -1)

            if exit_code == 0:
                commit_hash = ""
                stdout = result.get("stdout", "")

                # Try to extract commit hash from output
                import re
                hash_match = re.search(r'[a-f0-9]{8,40}', stdout)
                if hash_match:
                    commit_hash = hash_match.group(0)

                final_state = {
                    "commit_hash": commit_hash,
                    "status": "success",
                    "message": f"✅ Commit Successful! Hash: {commit_hash}"
                }

                _commit_workflow_sessions.pop(session_id, None)

                log_decision("confirm_commit.success", {
                    "session_id": session_id,
                    "commit_hash": commit_hash
                }, logger)

                return json.dumps({
                    "status": "success",
                    "commit_hash": commit_hash,
                    "message": f"✅ Commit Successful! Hash: {commit_hash}"
                }, indent=2)

            else:
                error_msg = result.get("stderr", "Unknown error")
                final_state = {
                    "error": error_msg,
                    "status": "rejected",
                    "message": f"❌ Commit Failed/Rejected: {error_msg}"
                }

                _commit_workflow_sessions.pop(session_id, None)

                log_decision("confirm_commit.failed", {
                    "session_id": session_id,
                    "error": error_msg
                }, logger)

                return json.dumps({
                    "status": "rejected",
                    "error": error_msg,
                    "message": f"❌ Commit Failed: {error_msg}"
                }, indent=2)

        except Exception as e:
            log_decision("confirm_commit.error", {"session_id": session_id, "error": str(e)}, logger)
            _commit_workflow_sessions.pop(session_id, None)
            return json.dumps({
                "status": "error",
                "error": str(e),
                "message": f"Failed to execute commit: {str(e)}"
            }, indent=2)

    @mcp.tool()
    async def spec_aware_commit(
        spec_path: Optional[str] = None,
        force_execute: bool = False,
    ) -> str:
        """
        [Phase 5 - Smart Commit] Generate commit message from Spec + Scratchpad.

        This tool implements "Spec-Aware GitOps":
        1. Reads the Spec file to extract Context & Goal
        2. Reads Scratchpad for recent activity
        3. Uses AI to generate high-quality commit message (Why, What, How)

        Args:
            spec_path: Optional path to spec file. Auto-detects if not provided.
            force_execute: If True, skips dry-run and directly executes commit

        Returns:
            Generated commit message and execution status
        """
        # Import InferenceClient lazily
        from mcp_core.inference import InferenceClient

        project_root = get_project_root()

        # Auto-detect spec path if not provided
        if not spec_path:
            specs_dir = project_root / "agent/specs"
            if specs_dir.exists():
                specs = sorted(specs_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
                if specs:
                    spec_path = str(specs[0])

        # Read spec content
        spec_content = ""
        if spec_path:
            spec_file = project_root / spec_path
            if spec_file.exists():
                spec_content = spec_file.read_text(encoding="utf-8")

        # Read scratchpad
        scratchpad_path = project_root / ".memory/active_context/SCRATCHPAD.md"
        scratchpad_content = ""
        if scratchpad_path.exists():
            scratchpad_content = scratchpad_path.read_text(encoding="utf-8")
            # Take last 100 lines for context
            lines = scratchpad_content.split("\n")
            scratchpad_content = "\n".join(lines[-100:])

        # Generate commit message
        client = InferenceClient()

        prompt = f"""Generate a Conventional Commit message based on:

=== SPEC ===
{spec_content[:2000]}

=== RECENT ACTIVITY (SCRATCHPAD) ===
{scratchpad_content[:1000]}

Format: <type>(<scope>): <description>

Provide ONLY the commit message line, no markdown, no explanation."""

        try:
            commit_msg = await client.complete(prompt=prompt, max_tokens=100)
            commit_msg = commit_msg.strip()

            log_decision("spec_aware_commit.generated", {
                "spec_path": spec_path,
                "message": commit_msg[:100]
            }, logger)

            if force_execute:
                # Execute commit
                result = await SafeExecutor.run(
                    command="just",
                    args=["agent-commit", commit_msg]
                )
                exit_code = result.get("exit_code", -1)

                if exit_code == 0:
                    return json.dumps({
                        "status": "success",
                        "commit_message": commit_msg,
                        "message": f"✅ Commit executed: {commit_msg}"
                    }, indent=2)
                else:
                    return json.dumps({
                        "status": "failed",
                        "commit_message": commit_msg,
                        "error": result.get("stderr", "Unknown error")
                    }, indent=2)

            return json.dumps({
                "status": "dry_run",
                "commit_message": commit_msg,
                "message": f"Generated commit message (dry run). Say 'run just agent-commit' to execute.",
                "spec_path": spec_path
            }, indent=2)

        except Exception as e:
            log_decision("spec_aware_commit.failed", {"error": str(e)}, logger)
            return json.dumps({
                "status": "error",
                "error": str(e)
            }, indent=2)

    log_decision("commit_tools.registered", {}, logger)
