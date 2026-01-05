"""
src/agent/core/workflows/dev_mode.py
Phase 20: The Self-Evolution Engine - The `omni dev` Command.

Orchestrates the lifecycle of a feature implementation:
Plan -> Contextualize -> Execute (Claude) -> Verify (Reviewer).

Features:
- RAG-powered context retrieval (Phase 16)
- Claude Code CLI integration (Phase 19.6)
- Post-Mortem audit (Phase 19.7)
- Black Box session tracking (Phase 19.6)

Usage:
    from agent.core.workflows.dev_mode import DevWorkflow

    workflow = DevWorkflow(inference=inference, session=session, ux=ux)
    await workflow.run("Add a hello-world script to scripts/")
"""

import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import structlog

from agent.core.session import SessionManager
from agent.core.ux import UXManager
from agent.core.vector_store import VectorMemory, get_vector_memory
from agent.core.adapters.claude_cli import ClaudeCodeAdapter
from agent.core.adapters.claude_cli import ContextInjector
from agent.core.agents.reviewer import ReviewerAgent
from agent.core.telemetry import CostEstimator, TokenUsage

logger = structlog.get_logger()


class DevWorkflow:
    """
    Phase 20: The Self-Evolution Engine.

    Orchestrates the complete feature development lifecycle:
    1. Plan & Retrieve - Use RAG to find relevant context
    2. Contextualize - Generate CLAUDE.md with project knowledge
    3. Execute - Launch Claude Code for implementation
    4. Verify - Post-Mortem audit with ReviewerAgent

    Architecture:
        ┌─────────────────────────────────────────────────────────────────┐
        │                    DevWorkflow (Orchestrator)                   │
        │                                                                 │
        │   ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐  │
        │   │ VectorMemory│──►│ContextInjector│──►│  ClaudeCodeAdapter  │  │
        │   │   (RAG)     │   │  (CLAUDE.md) │   │    (CLI Wrapper)    │  │
        │   └─────────────┘   └─────────────┘   └─────────────────────┘  │
        │                                                    │            │
        │                                                    ▼            │
        │   ┌─────────────────────────────────────────────────────────┐  │
        │   │                 ReviewerAgent                            │  │
        │   │                 (Post-Mortem Audit)                      │  │
        │   └─────────────────────────────────────────────────────────┘  │
        │                                                                 │
        └─────────────────────────────────────────────────────────────────┘
    """

    def __init__(
        self,
        session: SessionManager,
        ux: UXManager,
        vector_memory: VectorMemory = None,
        inference_client=None,
    ):
        """
        Initialize DevWorkflow.

        Args:
            session: SessionManager for Black Box tracking
            ux: UXManager for TUI display
            vector_memory: Optional VectorMemory for RAG (creates default if None)
            inference_client: Optional LLM client for cost estimation
        """
        self.session = session
        self.ux = ux
        self.vector_memory = vector_memory or get_vector_memory()
        self.inference_client = inference_client

        # Initialize components
        self.context_injector = ContextInjector()
        self.claude_adapter = ClaudeCodeAdapter(session=session)

        # Reviewer for post-mortem audit
        self.reviewer = ReviewerAgent()

        logger.info(
            "dev.workflow.initialized",
            session_id=session.session_id,
        )

    async def run(self, feature_request: str) -> Dict[str, Any]:
        """
        Execute the complete development workflow for a feature request.

        Args:
            feature_request: Natural language description of the feature

        Returns:
            Dict with workflow results including audit status
        """
        self.ux.console.rule("[bold magenta]🚀 Omni Dev Mode: Self-Evolution Protocol[/]")

        # Log workflow start
        self.session.log(
            "system",
            "dev_workflow",
            f"Starting DevWorkflow for: {feature_request[:100]}",
        )

        result = {
            "feature_request": feature_request,
            "success": False,
            "context_files": [],
            "claude_output": "",
            "audit_result": None,
            "duration_seconds": 0.0,
        }

        try:
            # Phase 1: Plan & Retrieve (RAG)
            context_info = await self._plan_and_retrieve(feature_request)
            result["context_files"] = context_info.get("files", [])

            # Phase 2: Contextualize (Generate CLAUDE.md)
            mission_brief = self._build_mission_brief(feature_request, context_info)

            # Show routing decision
            self.ux.show_routing_result(
                agent_name="Claude Code CLI",
                mission_brief=mission_brief,
                confidence=0.9,
            )
            self.ux.show_rag_hits([{"path": f} for f in context_info.get("files", [])])

            # Phase 3: Execute (Launch Claude Code)
            await self._execute_with_claude(mission_brief, context_info, result)

            # Phase 4: Verify (Post-Mortem Audit)
            await self._verify_changes(feature_request, result)

            result["success"] = result.get("audit_approved", False)

        except Exception as e:
            logger.error("dev.workflow.error", error=str(e))
            self.session.log("error", "dev_workflow", str(e))
            result["error"] = str(e)

        # Log workflow completion
        self.session.log(
            "system",
            "dev_workflow",
            f"DevWorkflow completed: success={result['success']}",
            metadata=result,
        )

        return result

    async def _plan_and_retrieve(self, feature_request: str) -> Dict[str, Any]:
        """
        Phase 1: Analyze feature request and retrieve relevant context via RAG.

        Args:
            feature_request: The feature description

        Returns:
            Dict with relevant files, docs, and context
        """
        with self.ux.console.status(
            "🧠 Analyzing feature request & retrieving context...", spinner="dots"
        ):
            # Search vector store for relevant context
            search_results = await self.vector_memory.search(
                query=feature_request,
                n_results=10,
            )

            # Extract file paths from results
            relevant_files = []
            relevant_docs = []

            for result in search_results:
                metadata = result.metadata or {}
                path = metadata.get("path", "")
                doc_type = metadata.get("type", "code")

                if path:
                    if doc_type == "docs":
                        relevant_docs.append(path)
                    else:
                        relevant_files.append(path)

            # Deduplicate while preserving order
            seen = set()
            unique_files = []
            for f in relevant_files:
                if f not in seen:
                    seen.add(f)
                    unique_files.append(f)

            seen.clear()
            unique_docs = []
            for d in relevant_docs:
                if d not in seen:
                    seen.add(d)
                    unique_docs.append(d)

            # Log retrieval results
            self.session.log(
                "system",
                "rag_retrieval",
                f"Retrieved {len(unique_files)} files and {len(unique_docs)} docs",
                metadata={
                    "query": feature_request[:100],
                    "files_found": len(unique_files),
                    "docs_found": len(unique_docs),
                },
            )

            logger.info(
                "dev.workflow.rag_retrieval",
                files=len(unique_files),
                docs=len(unique_docs),
            )

            return {
                "files": unique_files[:15],  # Limit to top 15
                "docs": unique_docs[:5],  # Limit to top 5
                "search_results": search_results,
            }

    def _build_mission_brief(self, feature_request: str, context_info: Dict[str, Any]) -> str:
        """
        Phase 2: Build the mission brief for Claude Code.

        Args:
            feature_request: The feature description
            context_info: Retrieved context from RAG

        Returns:
            Formatted mission brief for Claude CLI
        """
        files = context_info.get("files", [])
        docs = context_info.get("docs", [])

        brief_lines = [
            "# Mission Context",
            "",
            f"**Task**: {feature_request}",
            f"**Generated**: {datetime.now().isoformat()}",
            "",
            "## Relevant Files",
            "",
        ]

        # Add relevant files
        for i, file in enumerate(files[:15], 1):
            brief_lines.append(f"{i}. `{file}`")

        # Add documentation references
        if docs:
            brief_lines.extend(["", "## Documentation References"])
            for doc in docs[:5]:
                brief_lines.append(f"- {doc}")

        # Add instructions
        brief_lines.extend(
            [
                "",
                "## Instructions",
                "- Read the relevant files before making changes",
                "- Follow project conventions in CLAUDE.md",
                "- Add or update tests for new functionality",
                "- Run tests to verify the feature works correctly",
                "- Commit with conventional commit messages",
                "",
                "## Project Context",
                "- This is Omni Agentic OS - a modular development environment",
                "- Python package structure: packages/python/agent/src/agent/",
                "- Use 'just validate' to run tests and linting",
            ]
        )

        return "\n".join(brief_lines)

    async def _execute_with_claude(
        self,
        mission_brief: str,
        context_info: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """
        Phase 3: Launch Claude Code for implementation.

        Args:
            mission_brief: The formatted mission brief
            context_info: Retrieved context files
            result: Result dict to update
        """
        self.ux.console.print("\n[bold yellow]🎮 Handing over control to Claude Code...[/]")

        # Log Claude execution start
        self.session.log(
            "system",
            "claude_execution",
            "Starting Claude Code execution",
        )

        # Get file contents for context injection
        file_contents = {}
        for file_path in context_info.get("files", [])[:3]:
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                try:
                    content = file_path_obj.read_text()
                    file_contents[file_path] = content
                except Exception as e:
                    logger.warning("Failed to read file", file=file_path, error=str(e))

        # Run mission with Claude Code
        claude_result = await self.claude_adapter.run_mission(
            mission_brief=mission_brief,
            relevant_files=context_info.get("files", []),
            relevant_docs=context_info.get("docs", []),
            file_contents=file_contents or None,
        )

        # Update result
        result["claude_output"] = claude_result.get("output", "")
        result["claude_success"] = claude_result.get("success", False)
        result["exit_code"] = claude_result.get("exit_code", -1)
        result["duration_seconds"] = claude_result.get("duration_seconds", 0.0)

        # Estimate cost
        if self.inference_client:
            usage = CostEstimator.estimate(mission_brief, result["claude_output"])
            result["cost_usd"] = usage.cost_usd
        else:
            result["cost_usd"] = 0.0

        # Log result
        self.session.log(
            "agent_action",
            "claude_cli",
            result["claude_output"][:500] if result["claude_output"] else "No output",
            metadata={
                "success": result["claude_success"],
                "exit_code": result["exit_code"],
                "cost_usd": result.get("cost_usd", 0.0),
            },
        )

        self.ux.console.print(
            f"\n[bold cyan]Claude Code completed with exit code: {result['exit_code']}[/]"
        )

    async def _verify_changes(self, feature_request: str, result: Dict[str, Any]) -> None:
        """
        Phase 4: Post-Mortem verification with ReviewerAgent.

        Args:
            feature_request: Original feature request
            result: Result dict to update with audit status
        """
        with self.ux.console.status(
            "[bold yellow]🕵️ Running Post-Mortem Audit...[/]", spinner="dots"
        ):
            # Get git diff
            diff_summary = await self._get_git_diff()

            if not diff_summary.strip():
                result["audit_approved"] = False
                result["audit_feedback"] = "No changes detected in git history."
                self.ux.show_audit_result(False, result["audit_feedback"])
                return

            # Perform audit with ReviewerAgent
            audit = await self.reviewer.audit(
                task=feature_request,
                agent_output=f"Git Diff:\n{diff_summary}",
                context={
                    "feature_request": feature_request,
                    "claude_output": result.get("claude_output", "")[:2000],
                },
            )

            # Update result
            result["audit_approved"] = audit.approved
            result["audit_confidence"] = audit.confidence
            result["audit_feedback"] = audit.feedback
            result["audit_issues"] = audit.issues_found
            result["audit_suggestions"] = audit.suggestions

            # Log audit result
            self.session.log(
                "agent_action",
                "post_mortem_audit",
                f"Audit {'approved' if audit.approved else 'issues found'}",
                metadata={
                    "approved": audit.approved,
                    "confidence": audit.confidence,
                    "issues_count": len(audit.issues_found),
                },
            )

            # Show result via UX
            self.ux.show_audit_result(
                approved=audit.approved,
                feedback=audit.feedback,
                issues=audit.issues_found,
                suggestions=audit.suggestions,
            )

            if audit.approved:
                self.ux.console.print("[bold green]✅ Feature Verified & Approved![/]")
            else:
                self.ux.console.print(
                    "[bold red]⚠️ Audit Failed. Consider running 'omni dev' again to fix.[/]"
                )

    async def _get_git_diff(self) -> str:
        """
        Get the git diff of changes made by Claude Code.

        Returns:
            Git diff output as string
        """
        try:
            # Get diff of staged changes or working directory
            diff = subprocess.check_output(
                ["git", "diff", "--staged"],
                text=True,
                stderr=subprocess.DEVNULL,
            )

            # If no staged changes, get working directory diff
            if not diff.strip():
                diff = subprocess.check_output(
                    ["git", "diff"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )

            return diff

        except subprocess.CalledProcessError:
            logger.warning("Failed to get git diff")
            return ""
        except FileNotFoundError:
            logger.warning("Git not available")
            return ""

    async def _get_file_contents(self, file_paths: List[str]) -> Dict[str, str]:
        """
        Read file contents for context injection.

        Args:
            file_paths: List of file paths to read

        Returns:
            Dict mapping file paths to their contents
        """
        contents = {}
        for path in file_paths:
            file_path = Path(path)
            if file_path.exists() and file_path.is_file():
                try:
                    contents[path] = file_path.read_text()
                except Exception as e:
                    logger.warning(f"Failed to read {path}: {e}")
        return contents


def create_dev_workflow(
    session: SessionManager = None,
    ux: UXManager = None,
) -> DevWorkflow:
    """
    Factory function to create DevWorkflow with default dependencies.

    Args:
        session: Optional SessionManager (creates new if None)
        ux: Optional UXManager (creates new if None)

    Returns:
        Configured DevWorkflow instance
    """
    from agent.core.session import SessionManager as SM
    from agent.core.ux import UXManager as UX
    from agent.core.vector_store import get_vector_memory

    session = session or SM()
    ux = ux or UX()

    return DevWorkflow(
        session=session,
        ux=ux,
        vector_memory=get_vector_memory(),
    )
