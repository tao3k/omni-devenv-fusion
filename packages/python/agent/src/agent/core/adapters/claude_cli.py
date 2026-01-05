"""
src/agent/core/adapters/claude_cli.py
Claude Code CLI Adapter - Omni's Tactical Execution Hand.

Phase 19.6 Rev: Omni-Claude Symbiosis
Wraps the official Claude CLI for execution while Omni handles strategy.

Phase 19.7 Enhancements:
- Context compression (Dynamic Context Compression)
- Post-Mortem audit (Output Loop Closing)

Features:
- Context injection (dynamic CLAUDE.md generation with compression)
- Session tracking (Black Box for mission-level events)
- Output streaming (real-time feedback to Omni TUI)
- Post-Mortem auditing (automatic review after execution)
- MCP integration (Omni skills available to Claude Code)

Usage:
    from agent.core.adapters.claude_cli import ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter(session=session_manager)
    result = await adapter.run_mission(
        brief="Fix the threading bug in bootstrap.py",
        context_files=["agent/core/bootstrap.py"]
    )
"""

import asyncio
import subprocess
import tempfile
import json
from pathlib import Path
from typing import AsyncIterator, Dict, Any, Optional, List
from datetime import datetime
import structlog

from common.mcp_core.settings import get_setting
from agent.core.session import SessionManager, SessionEvent
from agent.core.telemetry import CostEstimator, TokenUsage

logger = structlog.get_logger()

# Default context compression settings (fallbacks when settings.yaml not available)
DEFAULT_MAX_CONTEXT_TOKENS = 4000  # Claude 3.5 Sonnet context window is ~200K, but we want to save tokens
DEFAULT_MAX_FILE_SIZE_KB = 50
DEFAULT_COMPRESSION_PROMPT = """
Summarize the following project context into a concise brief (max 500 words).
Focus on:
1. What the project is about
2. Key architectural patterns
3. Important conventions and rules
4. Current task context

Context:
{context}
"""


class ContextCompressor:
    """
    Compresses context using Omni's LLM before passing to Claude Code.

    Phase 19.7: Dynamic Context Compression
    Prevents context bloat by summarizing excessive RAG results.

    Configuration:
    - Reads from settings.yaml: context_compression.enabled
    - Reads from settings.yaml: context_compression.max_context_tokens
    - Reads from settings.yaml: context_compression.method
    """

    def __init__(
        self,
        max_tokens: int = None,
        compression_method: str = None,
    ):
        """
        Initialize compressor with settings from config or defaults.

        Args:
            max_tokens: Maximum tokens before compression (default from settings)
            compression_method: "llm" or "truncate" (default from settings)
        """
        self.max_tokens = max_tokens or get_setting(
            "context_compression.max_context_tokens",
            DEFAULT_MAX_CONTEXT_TOKENS
        )
        self.method = compression_method or get_setting(
            "context_compression.method",
            "llm"
        )
        self.enabled = get_setting("context_compression.enabled", True)

        logger.info(
            "context.compressor.initialized",
            enabled=self.enabled,
            max_tokens=self.max_tokens,
            method=self.method,
        )

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        return len(text) // 3.5  # Approximate for English

    async def compress_context(
        self,
        context: str,
        mission_brief: str,
        inference_client=None,
    ) -> str:
        """
        Compress context if it exceeds token threshold.

        Args:
            context: Original context text
            mission_brief: The mission task
            inference_client: Optional LLM client for summarization

        Returns:
            Compressed context (or original if under threshold or disabled)
        """
        # Check if compression is enabled
        if not self.enabled:
            logger.info("context.compression.disabled")
            return context

        token_count = self.estimate_tokens(context)

        if token_count <= self.max_tokens:
            logger.info(
                "context.compression.skipped",
                reason="under_threshold",
                tokens=token_count,
                max_tokens=self.max_tokens,
            )
            return context

        logger.info(
            "context.compression.started",
            tokens=token_count,
            max_tokens=self.max_tokens,
        )

        # If no inference client, just truncate
        if inference_client is None:
            compressed = self._truncate_context(context, self.max_tokens)
            logger.warning(
                "context.compression.truncated",
                reason="no_inference_client",
            )
            return compressed

        # Use LLM to summarize
        try:
            prompt = DEFAULT_COMPRESSION_PROMPT.format(context=context[:10000])
            result = await inference_client.complete(
                system_prompt="You are a context compression assistant. Return only the summarized content, no explanation.",
                user_query=f"Summarize this context for a mission: {mission_brief}\n\n{context[:15000]}",
                max_tokens=1000,
            )

            if result["success"]:
                compressed = result["content"]
                logger.info(
                    "context.compression.completed",
                    original_tokens=token_count,
                    compressed_tokens=self.estimate_tokens(compressed),
                )
                return compressed

        except Exception as e:
            logger.error("context.compression.failed", error=str(e))

        # Fallback to truncation
        return self._truncate_context(context, self.max_tokens)

    def _truncate_context(self, context: str, max_tokens: int) -> str:
        """Truncate context to fit token limit."""
        max_chars = max_tokens * 3.5
        if len(context) <= max_chars:
            return context

        return context[:int(max_chars)] + "\n\n[... context truncated for length]"


class ContextInjector:
    """
    Dynamically generates CLAUDE.md from RAG for context injection.

    Phase 19.7: Now with Dynamic Context Compression.

    Omni's strategic advantage: Claude Code starts with project-specific context
    instead of being "forgetful" and needing to re-read everything.

    Configuration:
    - Reads from settings.yaml: context_compression.enabled
    - Reads from settings.yaml: context_compression.max_context_tokens
    - Reads from settings.yaml: context_compression.max_file_size_kb
    """

    def __init__(
        self,
        inference_client=None,
        max_tokens: int = None,
        max_file_size_kb: int = None,
    ):
        """
        Initialize ContextInjector with settings from config.

        Args:
            inference_client: Optional LLM client for compression
            max_tokens: Override for max context tokens
            max_file_size_kb: Override for max file size before compression
        """
        self.compressor = ContextCompressor(max_tokens=max_tokens)
        self.inference_client = inference_client
        self.max_file_size_kb = max_file_size_kb or get_setting(
            "context_compression.max_file_size_kb",
            DEFAULT_MAX_FILE_SIZE_KB
        )

        logger.info(
            "context.injector.initialized",
            max_file_size_kb=self.max_file_size_kb,
            compression_enabled=self.compressor.enabled,
        )

    def generate_context_file(
        self,
        mission_brief: str,
        relevant_files: List[str],
        relevant_docs: List[str] = None,
        file_contents: Dict[str, str] = None,
    ) -> str:
        """
        Generate a context file that Claude Code will read on startup.

        Phase 19.7: Added file content inclusion and compression.

        This creates a temporary CLAUDE.md that:
        1. Summarizes the mission
        2. Lists the most relevant files (from RAG)
        3. Includes relevant documentation
        4. Provides project-specific conventions
        5. Optionally includes file contents (with compression)

        Args:
            mission_brief: The task to accomplish
            relevant_files: List of file paths relevant to the task
            relevant_docs: List of documentation files
            file_contents: Dict of file_path -> content for key files

        Returns:
            Generated context file content
        """
        context_lines = [
            "# Mission Context",
            "",
            f"**Task**: {mission_brief}",
            f"**Generated**: {datetime.now().isoformat()}",
            "",
            "## Relevant Files",
            "",
        ]

        # Add relevant files
        for i, file in enumerate(relevant_files[:15], 1):
            context_lines.append(f"{i}. `{file}`")

        # Add file contents for top 3 most important files
        if file_contents:
            context_lines.append("")
            context_lines.append("## Key File Contents")
            context_lines.append("")
            for i, (file_path, content) in enumerate(list(file_contents.items())[:3], 1):
                file_size_kb = len(content) / 1024

                # Use config setting for file size threshold
                max_chars = self.max_file_size_kb * 1024

                # Truncate based on config setting
                display_content = content[:int(max_chars)] if len(content) > max_chars else content
                context_lines.append(f"### {file_path}")
                context_lines.append("```")
                context_lines.append(display_content)
                context_lines.append("```")
                if len(content) > max_chars:
                    context_lines.append(
                        f"[... {len(content) - int(max_chars)} more characters truncated "
                        f"(max_file_size_kb: {self.max_file_size_kb})]"
                    )

        # Add documentation hints
        if relevant_docs:
            context_lines.append("")
            context_lines.append("## Documentation References")
            for doc in relevant_docs[:5]:
                context_lines.append(f"- {doc}")

        context_lines.extend(
            [
                "",
                "## Instructions",
                "- Read the relevant files before making changes",
                "- Follow project conventions in CLAUDE.md",
                "- Run tests before committing",
                "- Commit with conventional commit messages",
            ]
        )

        context = "\n".join(context_lines)

        # Phase 19.7: Compress context if needed
        return context


class PostMortemAuditor:
    """
    Performs Post-Mortem audit after Claude Code execution.

    Phase 19.7: Output Loop Closing
    Automatically reviews changes after Claude Code exits.

    Configuration:
    - Reads from settings.yaml: post_mortem.enabled
    - Reads from settings.yaml: post_mortem.confidence_threshold
    """

    def __init__(self, session: SessionManager):
        """
        Initialize auditor with settings from config.

        Args:
            session: SessionManager for logging results
        """
        self.session = session
        self.enabled = get_setting("post_mortem.enabled", True)
        self.confidence_threshold = get_setting("post_mortem.confidence_threshold", 0.8)

        logger.info(
            "post_mortem.auditor.initialized",
            enabled=self.enabled,
            confidence_threshold=self.confidence_threshold,
        )

    async def audit_changes(
        self,
        mission_brief: str,
        claude_output: str,
        diff_summary: str = None,
    ) -> Dict[str, Any]:
        """
        Perform Post-Mortem audit on Claude Code's execution.

        Args:
            mission_brief: Original mission
            claude_output: Claude's output
            diff_summary: Optional git diff summary

        Returns:
            Audit result with issues found
        """
        from agent.core.agents.reviewer import ReviewerAgent

        self.session.log(
            "system",
            "post_mortem",
            "Starting Post-Mortem audit",
        )

        try:
            reviewer = ReviewerAgent()

            # Build audit context
            audit_context = {
                "mission": mission_brief,
                "output_length": len(claude_output),
                "has_diff": diff_summary is not None,
            }

            # Create synthetic "code" to review (the output + diff)
            review_content = f"""
## Mission
{mission_brief}

## Claude Output
{claude_output[:5000]}

## Changes Made
{diff_summary or "No diff summary provided"}
"""

            result = await reviewer.audit(
                task=mission_brief,
                agent_output=review_content,
                context=audit_context,
            )

            # Log audit result
            self.session.log(
                "agent_action",
                "post_mortem_auditor",
                f"Audit {'approved' if result.approved else 'issues found'}",
                metadata={
                    "approved": result.approved,
                    "issues_count": len(result.issues_found),
                    "confidence": result.confidence,
                },
            )

            # If issues found, log them in detail
            if result.issues_found:
                self.session.log(
                    "warning",
                    "post_mortem",
                    f"Found {len(result.issues_found)} issues",
                    metadata={"issues": result.issues_found},
                )

            return {
                "approved": result.approved,
                "issues_found": result.issues_found,
                "suggestions": result.suggestions,
                "feedback": result.feedback,
                "confidence": result.confidence,
            }

        except Exception as e:
            logger.error("post_mortem.audit_failed", error=str(e))
            self.session.log("error", "post_mortem", str(e))
            return {
                "approved": False,
                "issues_found": [f"Audit failed: {str(e)}"],
                "suggestions": [],
                "feedback": str(e),
                "confidence": 0.0,
            }


class ClaudeCodeAdapter:
    """
    Omni's execution hand - wraps Claude CLI.

    Phase 19.7: Now with Post-Mortem auditing.

    This adapter:
    1. Injects dynamic context (Phase 16 RAG)
    2. Launches Claude Code with mission brief
    3. Streams output for Omni TUI
    4. Tracks mission in Black Box
    5. Performs Post-Mortem audit after execution

    Architecture:
        ┌─────────────────────────────────────────────────────────┐
        │                    Omni (Strategic)                     │
        │  ┌─────────────────────────────────────────────────┐   │
        │  │ ContextInjector: Generate CLAUDE.md from RAG   │   │
        │  │   - Dynamic compression (Phase 19.7)           │   │
        │  └─────────────────────────────────────────────────┘   │
        │                          │                             │
        │                          ▼                             │
        │  ┌─────────────────────────────────────────────────┐   │
        │  │ ClaudeCodeAdapter: Wrap Claude CLI             │   │
        │  │   - Context injection                          │   │
        │  │   - Output streaming                           │   │
        │  │   - Session tracking (Black Box)               │   │
        │  │   - Post-Mortem audit (Phase 19.7)             │   │
        │  └─────────────────────────────────────────────────┘   │
        │                          │                             │
        │                          ▼                             │
        │              Claude Code (Tactical Execution)          │
        └─────────────────────────────────────────────────────────┘
    """

    def __init__(
        self,
        session: SessionManager,
        context_injector: ContextInjector = None,
        enable_post_mortem: bool = None,
        inference_client=None,
    ):
        """
        Initialize the adapter.

        Args:
            session: SessionManager for Black Box tracking
            context_injector: Optional ContextInjector (creates default if None)
            enable_post_mortem: Whether to run Post-Mortem audit (default from settings)
            inference_client: Optional LLM client for context compression
        """
        self.session = session
        self.context_injector = context_injector or ContextInjector(
            inference_client=inference_client
        )
        # Read from config if not explicitly set
        if enable_post_mortem is None:
            self.enable_post_mortem = get_setting("post_mortem.enabled", True)
        else:
            self.enable_post_mortem = enable_post_mortem
        self.inference_client = inference_client

        # Default Claude CLI command
        self.claude_cmd = ["claude"]

        # Configuration
        self.use_headless_mode = True  # Use -p for prompt mode
        self.stream_output = True

        # Post-Mortem auditor
        self.auditor = PostMortemAuditor(session) if self.enable_post_mortem else None

        logger.info(
            "claude.adapter.initialized",
            enable_post_mortem=self.enable_post_mortem,
        )

    def _construct_command(
        self,
        mission_brief: str,
        context_file: Path = None,
    ) -> List[str]:
        """
        Construct the Claude CLI command.

        Args:
            mission_brief: The task description
            context_file: Optional path to context file

        Returns:
            Command list for subprocess
        """
        cmd = list(self.claude_cmd)

        if self.use_headless_mode:
            # Headless mode: pass prompt directly
            cmd.extend(["-p", mission_brief])
        else:
            # Interactive mode (not recommended for automation)
            cmd.append(mission_brief)

        # Add common flags
        if context_file:
            cmd.extend(["--context-file", str(context_file)])

        return cmd

    async def run_mission(
        self,
        mission_brief: str,
        relevant_files: List[str] = None,
        relevant_docs: List[str] = None,
        file_contents: Dict[str, str] = None,
        timeout: int = 600,
    ) -> Dict[str, Any]:
        """
        Execute a mission by wrapping Claude CLI.

        Phase 19.6: The Black Box tracks this mission execution.
        Phase 19.7: Added Post-Mortem audit.

        Args:
            mission_brief: Task description
            relevant_files: Files relevant to the task (from RAG)
            relevant_docs: Documentation relevant to the task
            file_contents: Content of key files for context
            timeout: Max execution time in seconds

        Returns:
            Dict with:
            - success: bool
            - output: str (final output)
            - exit_code: int
            - duration_seconds: float
            - events: List[SessionEvent]
            - audit_result: Dict (Post-Mortem result)
        """
        import time

        start_time = time.time()
        events = []
        audit_result = None

        # Phase 1: Generate dynamic context
        self.session.log(
            "system",
            "context_injector",
            "Generating dynamic context from RAG",
            metadata={"relevant_files_count": len(relevant_files or [])},
        )

        context_file = None
        context_content = None

        if relevant_files:
            context_content = self.context_injector.generate_context_file(
                mission_brief=mission_brief,
                relevant_files=relevant_files or [],
                relevant_docs=relevant_docs or [],
                file_contents=file_contents or {},
            )

            # Phase 19.7: Compress context if needed
            if self.inference_client:
                context_content = await self.context_injector.compressor.compress_context(
                    context=context_content,
                    mission_brief=mission_brief,
                    inference_client=self.inference_client,
                )

            # Write to temp file for Claude to read
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".md",
                delete=False,
                prefix="claude_context_",
            ) as f:
                f.write(context_content)
                context_file = Path(f.name)

            self.session.log(
                "system",
                "context_injector",
                f"Context file created: {context_file.name}",
                metadata={
                    "path": str(context_file),
                    "size": len(context_content),
                },
            )

        # Phase 2: Construct command
        cmd = self._construct_command(mission_brief, context_file)

        self.session.log(
            "user",
            "orchestrator",
            f"🚀 Launching Claude Code",
            metadata={
                "command": " ".join(cmd[:3]) + "...",
                "mission": mission_brief[:100],
            },
        )

        logger.info("🚀 Executing mission via Claude Code", command=" ".join(cmd))

        # Phase 3: Execute with streaming
        output_chunks = []
        exit_code = None

        try:
            # Use asyncio subprocess for streaming
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            # Stream output line by line
            async for line in process.stdout:
                decoded = line.decode("utf-8", errors="replace").strip()
                if decoded:
                    output_chunks.append(decoded)
                    # Log significant output events
                    if any(
                        keyword in decoded.lower()
                        for keyword in [
                            "thinking",
                            "reading",
                            "writing",
                            "running",
                            "completed",
                            "error",
                        ]
                    ):
                        self.session.log(
                            "tool",
                            "claude_cli",
                            decoded,
                            metadata={"stream": True},
                        )

            # Wait for completion
            exit_code = await process.wait()

        except Exception as e:
            self.session.log(
                "error",
                "claude_cli",
                str(e),
                metadata={"mission": mission_brief[:100]},
            )
            return {
                "success": False,
                "output": str(e),
                "exit_code": -1,
                "duration_seconds": time.time() - start_time,
                "events": self.session.events,
                "audit_result": None,
            }

        finally:
            # Cleanup temp context file
            if context_file and context_file.exists():
                context_file.unlink()

        # Phase 4: Calculate telemetry
        full_output = "\n".join(output_chunks)
        usage = CostEstimator.estimate(mission_brief, full_output)
        duration = time.time() - start_time

        # Phase 5: Log final result
        self.session.log(
            "agent_action",
            "claude_cli",
            full_output,
            usage=usage,
            metadata={
                "exit_code": exit_code,
                "duration_seconds": round(duration, 2),
                "output_length": len(full_output),
            },
        )

        # Phase 19.7: Post-Mortem Audit
        if self.enable_post_mortem and self.auditor:
            self.session.log(
                "system",
                "post_mortem",
                "Starting Post-Mortem audit",
            )

            audit_result = await self.auditor.audit_changes(
                mission_brief=mission_brief,
                claude_output=full_output,
            )

        # Log summary
        self.session.log(
            "system",
            "session",
            "Mission completed",
            metadata={
                "duration_seconds": round(duration, 2),
                "cost_usd": usage.cost_usd,
                "exit_code": exit_code,
                "audit_approved": audit_result["approved"] if audit_result else None,
            },
        )

        return {
            "success": exit_code == 0,
            "output": full_output,
            "exit_code": exit_code,
            "duration_seconds": duration,
            "cost_usd": usage.cost_usd,
            "events": self.session.events,
            "audit_result": audit_result,
        }

    async def run_mission_streaming(
        self,
        mission_brief: str,
        relevant_files: List[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute mission with real-time streaming output.

        Yields:
            Dict with:
            - type: "output" | "error" | "done"
            - content: str
            - timestamp: float
        """
        import time

        start_time = time.time()

        # Generate context
        context_content = ""
        context_file = None

        if relevant_files:
            context_content = self.context_injector.generate_context_file(
                mission_brief=mission_brief,
                relevant_files=relevant_files or [],
            )

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False, prefix="claude_ctx_"
            ) as f:
                f.write(context_content)
                context_file = Path(f.name)

        # Build command
        cmd = self._construct_command(mission_brief, context_file)

        yield {
            "type": "status",
            "content": f"Launching Claude Code...",
            "timestamp": time.time(),
        }

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            async for line in process.stdout:
                decoded = line.decode("utf-8", errors="replace").strip()
                if decoded:
                    yield {
                        "type": "output",
                        "content": decoded,
                        "timestamp": time.time(),
                    }

            exit_code = await process.wait()

            yield {
                "type": "done",
                "content": f"Completed in {time.time() - start_time:.1f}s",
                "timestamp": time.time(),
                "exit_code": exit_code,
            }

        except Exception as e:
            yield {
                "type": "error",
                "content": str(e),
                "timestamp": time.time(),
            }

        finally:
            if context_file and context_file.exists():
                context_file.unlink()


def create_claude_adapter(session: SessionManager) -> ClaudeCodeAdapter:
    """
    Factory function to create ClaudeCodeAdapter.

    Args:
        session: SessionManager instance

    Returns:
        Configured ClaudeCodeAdapter
    """
    return ClaudeCodeAdapter(session=session)
