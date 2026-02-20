"""
react.py - Resilient ReAct Workflow Engine
Feature: Epistemic Resilience, Validation Guard & Micro-Correction Loop

Architecture:
1. Epistemic Gating (Intent Check) - Done in OmniLoop
2. Validation Guard (Schema Compliance) - Static validation before execution
3. Resilient Execution (Micro-Correction) - Catch invalid args before execution
4. Loop Detection (Stagnation Prevention) - Prevent infinite loops
5. Output Compression - Prevent context overflow
"""

import re
import json
import hashlib
from typing import Any, Dict, List, Set, Optional
from pydantic import BaseModel

from omni.foundation.services.llm import InferenceClient
from omni.foundation.config.logging import get_logger

from .logging import log_completion, log_result, log_step, log_llm_response

logger = get_logger("omni.agent.react")


# ============================================================================
# Validation Guard Components
# ============================================================================


class ValidationResult(BaseModel):
    """Result of parameter validation."""

    is_valid: bool
    error_message: Optional[str] = None
    cleaned_args: Optional[Dict[str, Any]] = None


class OutputCompressor:
    """Compresses large observations to prevent context overflow."""

    @staticmethod
    def compress(content: str, max_len: int = 2000) -> str:
        """Compress content if it exceeds max length."""
        if len(content) <= max_len:
            return content

        head = content[: max_len // 2]
        tail = content[-(max_len // 2) :]
        return (
            f"{head}\n"
            f"... [Output Truncated: {len(content) - max_len} chars hidden] ...\n"
            f"{tail}\n"
            "(Hint: Use a specific tool to read the hidden section if needed)"
        )


class ArgumentValidator:
    """Static Guard: Validates arguments against JSON schema before execution."""

    @staticmethod
    def validate(schema: Dict[str, Any], args: Dict[str, Any]) -> ValidationResult:
        """
        Lightweight validation against JSON schema (parameters).
        Checks for required fields and basic types.
        """
        if not schema or "parameters" not in schema:
            return ValidationResult(is_valid=True, cleaned_args=args)

        params = schema.get("parameters", {})
        required = params.get("required", [])
        properties = params.get("properties", {})

        # 1. Check Required Fields
        missing = [f for f in required if f not in args]
        if missing:
            return ValidationResult(
                is_valid=False, error_message=f"Missing required arguments: {', '.join(missing)}"
            )

        # 2. Type Check (Basic) & Cleaning
        cleaned = args.copy()
        for key, value in args.items():
            if key in properties:
                prop_type = properties[key].get("type")
                # Simple type coercion
                if prop_type == "integer" and isinstance(value, str):
                    if value.isdigit():
                        cleaned[key] = int(value)
                    else:
                        return ValidationResult(
                            is_valid=False, error_message=f"Argument '{key}' must be an integer."
                        )

        return ValidationResult(is_valid=True, cleaned_args=cleaned)


class ToolCallParser:
    """Dual-format tool call parser - ZeroClaw style.

    Supports:
    1. OpenAI JSON format: {"name": "shell", "arguments": {"command": "ls"}}
    2. XML style: <tool_call>{"name": "shell", "arguments": {"command": "ls"}}</tool_call>
    """

    # XML style pattern: <tool_call>...</tool_call>
    XML_PATTERN = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)

    # MiniMax pattern: minimax:tool_call {...}
    MINIMAX_PATTERN = re.compile(r"minimax:tool_call\s*(\{.*?\})", re.DOTALL)

    @classmethod
    def parse(cls, response: str) -> tuple[str, list[dict]]:
        """Parse tool calls from LLM response.

        Supports:
        1. OpenAI JSON: {"tool_calls": [...]}
        2. XML style: <tool_call>{...}</tool_call>
        3. Code blocks with commands: ```ls -la```

        Returns:
            Tuple of (text_content, tool_calls)
        """
        import json
        import re

        text_parts = []
        tool_calls = []

        # First: try OpenAI JSON format
        try:
            data = json.loads(response.strip())
            if "tool_calls" in data and isinstance(data["tool_calls"], list):
                for tc in data["tool_calls"]:
                    if "function" in tc:
                        func = tc["function"]
                        name = func.get("name", "")
                        args = func.get("arguments", {})
                        if isinstance(args, str):
                            args = json.loads(args)
                        if name:
                            tool_calls.append({"name": name, "input": args})

                # Extract text content if present
                if "content" in data and data["content"]:
                    text_parts.append(data["content"].strip())

                if tool_calls:
                    return ("\n".join(text_parts), tool_calls)
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: XML style <tool_call>...</tool_call>
        remaining = response
        while True:
            match = cls.XML_PATTERN.search(remaining)
            if not match:
                break

            # Text before the tag
            before = remaining[: match.start()]
            if before.strip():
                text_parts.append(before.strip())

            # Parse the JSON inside
            try:
                inner = json.loads(match.group(1).strip())
                name = inner.get("name", "")
                args = inner.get("arguments", {})
                if name:
                    tool_calls.append({"name": name, "input": args})
            except (json.JSONDecodeError, ValueError):
                pass

            remaining = remaining[match.end() :]

        # MiniMax format: minimax:tool_call {...}
        if not tool_calls:
            for match in cls.MINIMAX_PATTERN.finditer(response):
                try:
                    inner = json.loads(match.group(1).strip())
                    name = inner.get("name", "")
                    args = inner.get("arguments", {})
                    if name:
                        tool_calls.append({"name": name, "input": args})
                except (json.JSONDecodeError, ValueError):
                    pass

        # If no tool calls found, try to extract commands from code blocks
        if not tool_calls:
            # Match ```bash``` or ```sh``` or ```shell``` blocks
            code_block_pattern = re.compile(r"```(?:bash|sh|shell|zsh)?\n(.*?)```", re.DOTALL)
            for match in code_block_pattern.finditer(response):
                cmd = match.group(1).strip()
                # Remove leading $ or > prompts (common in shell examples)
                cmd = re.sub(r"^[\$>]\\s*", "", cmd)
                if cmd and not cmd.startswith("#"):
                    # Accept any command that looks like a shell command
                    tool_calls.append({"name": "omniCell.nuShell", "input": {"command": cmd}})

            # Also match plain text commands after "I'll run:" or "Running:"
            if not tool_calls:
                cmd_pattern = re.compile(
                    r"(?:I'll run|Running|Executing):\s*\$?\s*(.+?)(?:\n|$)", re.IGNORECASE
                )
                for match in cmd_pattern.finditer(response):
                    cmd = match.group(1).strip()
                    # Remove leading $ or > prompts for nushell
                    cmd = re.sub(r"^[\$>]+\s*", "", cmd)
                    if cmd:
                        tool_calls.append({"name": "omniCell.nuShell", "input": {"command": cmd}})

            # Also match %command% format (some models use this)
            if not tool_calls:
                percent_pattern = re.compile(r"%(.+?)%")
                for match in percent_pattern.finditer(response):
                    cmd = match.group(1).strip()
                    if cmd and any(
                        cmd.startswith(kw)
                        for kw in [
                            "ls",
                            "cat",
                            "git",
                            "cd",
                            "pwd",
                            "echo",
                            "python",
                            "npm",
                            "cargo",
                            "uv",
                            "rm",
                            "mv",
                            "cp",
                            "mkdir",
                            "find",
                            "cargo",
                        ]
                    ):
                        tool_calls.append({"name": "shell", "input": {"command": cmd}})

            # Match $ command format (e.g., "$ cargo test")
            if not tool_calls:
                dollar_pattern = re.compile(r"^\s*\$\s*(.+)$", re.MULTILINE)
                for match in dollar_pattern.finditer(response):
                    cmd = match.group(1).strip()
                    if cmd and any(
                        cmd.startswith(kw)
                        for kw in [
                            "ls",
                            "cat",
                            "git",
                            "cd",
                            "pwd",
                            "echo",
                            "python",
                            "npm",
                            "cargo",
                            "uv",
                            "rm",
                            "mv",
                            "cp",
                            "mkdir",
                            "find",
                            "cargo",
                            "python",
                            "pip",
                        ]
                    ):
                        tool_calls.append({"name": "shell", "input": {"command": cmd}})

        # Remaining text
        if remaining.strip():
            text_parts.append(remaining.strip())

        return ("\n".join(text_parts), tool_calls)


class OmniReplExecutor:
    """Executes Nushell commands from Omni REPL mode.

    Detects tool calls in LLM responses and executes them via OmniCell.
    Supports dual format (ZeroClaw style):
    1. OpenAI JSON: {"name": "shell", "arguments": {"command": "ls"}}
    2. XML style: <tool_call>{"name": "shell", "arguments": {"command": "ls"}}</tool_call>
    """

    def __init__(self):
        self._cell_runner = None

    def _get_cell_runner(self):
        """Lazy-load OmniCell runner."""
        if self._cell_runner is None:
            try:
                from omni.core.skills.runtime.omni_cell import get_runner

                self._cell_runner = get_runner()
            except ImportError:
                logger.warning("OmniCell not available for REPL execution")
                return None
        return self._cell_runner

    async def extract_and_execute(self, content: str) -> tuple[bool, str]:
        """Extract and execute tool calls from content.

        Args:
            content: LLM response that may contain tool calls

        Returns:
            Tuple of (had_commands, execution_results)
        """
        # Use dual-format parser
        text_content, tool_calls = ToolCallParser.parse(content)

        if not tool_calls:
            return False, ""

        runner = self._get_cell_runner()
        if runner is None:
            return True, "[System] OmniCell not available for command execution"

        results = []
        for tc in tool_calls:
            tool_name = tc.get("name", "")
            tool_input = tc.get("input", {})

            # Build command string from arguments
            if tool_name == "shell" and "command" in tool_input:
                cmd = tool_input["command"]
            elif "command" in tool_input:
                cmd = str(tool_input["command"])
            else:
                # Serialize arguments as JSON
                import json

                cmd = json.dumps(tool_input)

            logger.info(f"[Omni REPL] Executing: {tool_name} {cmd[:100]}")
            try:
                response = await runner.run(cmd, ensure_structured=True)
                if response.status.value == "success":
                    result_data = response.data if response.data else "Command completed"
                    results.append(f"[{tool_name}] Result:\n{result_data}")
                else:
                    results.append(f"[{tool_name}] Error: {response.error_message}")
            except Exception as e:
                results.append(f"[{tool_name}] Error: {str(e)}")

        return True, "\n\n".join(results)

    def strip_tags(self, content: str) -> str:
        """Remove tool_call tags from content after execution."""
        # Remove both XML style and the text content that was parsed
        content = ToolCallParser.XML_PATTERN.sub("", content)
        return content


# ============================================================================
# Main ResilientReAct Workflow
# ============================================================================


class ResilientReAct:
    """
    Advanced ReAct Engine with Self-Correction and Loop Detection.

    Architecture:
    1. Epistemic Gating (Intent Check) - Done in OmniLoop
    2. Validation Guard (Schema Compliance) - Static validation before execution
    3. Resilient Execution (Micro-Correction) - Catch invalid args before execution
    4. Loop Detection (Stagnation Prevention) - Prevent infinite loops
    5. Output Compression - Prevent context overflow
    """

    def __init__(
        self,
        engine: InferenceClient,
        get_tool_schemas,
        execute_tool,
        max_tool_calls: int = 15,
        max_consecutive_errors: int = 3,
        verbose: bool = False,
    ):
        self.engine = engine
        self.get_tool_schemas = get_tool_schemas
        self.execute_tool = execute_tool
        self.max_tool_calls = max_tool_calls
        self.max_consecutive_errors = max_consecutive_errors
        self.verbose = verbose

        # State tracking
        self.step_count = 0
        self.tool_calls_count = 0
        self._tool_hash_history: Set[str] = set()
        self._tool_schema_cache: Dict[str, Dict[str, Any]] = {}

        # Omni REPL executor for models without native tool calling
        self._repl_executor = OmniReplExecutor()

    async def _load_schemas(self):
        """Lazy load and cache schemas for validation."""
        schemas = await self.get_tool_schemas()
        self._tool_schema_cache = {s["name"]: s for s in schemas}
        return schemas

    async def run(
        self,
        task: str,
        system_prompt: str,
        messages: List[Dict[str, Any]],
    ) -> str:
        """Execute the ResilientReAct workflow."""
        tools = await self._load_schemas()

        consecutive_errors = 0
        response_content = ""

        while self.tool_calls_count < self.max_tool_calls:
            self.step_count += 1

            # 1. Inference (Think)
            response = await self.engine.complete(
                system_prompt=system_prompt,
                user_query=task,
                messages=messages,
                tools=tools if tools else None,
            )

            raw_content = response.get("content", "")
            response_content = self._clean_artifacts(raw_content)

            messages.append({"role": "assistant", "content": response_content})
            log_llm_response(response_content)

            # 2. Check for Explicit Exit Signal
            if self._check_completion(response_content):
                log_completion(self.step_count, self.tool_calls_count)
                break

            tool_calls = response.get("tool_calls", [])
            logger.info(f"[REPL] tool_calls from response: {len(tool_calls)} items")
            if not tool_calls:
                # Check for Omni REPL commands (for models without native tool calling)
                logger.info(
                    f"[REPL] Checking for tool calls in response (first 300 chars): {response_content[:300]}"
                )
                had_repl_commands, repl_results = await self._repl_executor.extract_and_execute(
                    response_content
                )
                if had_repl_commands:
                    logger.info(
                        f"[REPL] Found and executed tool calls, results: {repl_results[:200] if repl_results else 'empty'}"
                    )
                if had_repl_commands:
                    # Add the execution results to messages and continue the loop
                    clean_content = self._repl_executor.strip_tags(response_content)
                    messages[-1] = {"role": "assistant", "content": clean_content}

                    # Append execution results
                    if repl_results:
                        messages.append({"role": "user", "content": repl_results})
                        log_result(repl_results, is_error=False)

                    # Continue to next iteration to let LLM process results
                    if self.tool_calls_count < self.max_tool_calls:
                        continue
                break

            # 3. Execution Stage
            for tool_call in tool_calls:
                self.tool_calls_count += 1
                tool_name = tool_call.get("name")
                tool_input = tool_call.get("input", {})

                # A. Loop Detection
                call_hash = self._compute_tool_hash(tool_name, tool_input)
                if call_hash in self._tool_hash_history:
                    result = "[System Warning] Loop Detected: You have already executed this tool with these exact arguments. Change your strategy."
                    is_error = True
                    consecutive_errors += 1
                else:
                    self._tool_hash_history.add(call_hash)

                    # B. Validation Guard
                    schema = self._tool_schema_cache.get(tool_name)
                    validation = ArgumentValidator.validate(schema, tool_input)

                    if not validation.is_valid:
                        # Micro-Correction: Catch invalid args before execution
                        result = f"Argument Validation Error: {validation.error_message} (Check tool schema)"
                        is_error = True
                        consecutive_errors += 1
                    else:
                        # C. Execution
                        log_step(
                            self.step_count, self.max_tool_calls, tool_name, validation.cleaned_args
                        )
                        try:
                            result = await self.execute_tool(tool_name, validation.cleaned_args)
                            is_error = False
                            consecutive_errors = 0  # Reset on success
                        except Exception as e:
                            result = f"Runtime Error: {str(e)}"
                            is_error = True
                            consecutive_errors += 1

                log_result(str(result), is_error=is_error)

                # D. Output Compression
                compressed_result = OutputCompressor.compress(str(result))

                # E. Stagnation Check
                if consecutive_errors >= self.max_consecutive_errors:
                    crit_msg = "\n[System Critical] Too many consecutive errors. Aborting execution loop to prevent resource waste."
                    messages.append(
                        {"role": "user", "content": self._format_result(tool_name, crit_msg, True)}
                    )
                    return response_content + f"\n\n(Execution stopped: {crit_msg})"

                messages.append(
                    {
                        "role": "user",
                        "content": self._format_result(tool_name, compressed_result, is_error),
                    }
                )

        return response_content

    def _compute_tool_hash(self, name: str, args: Dict) -> str:
        """Computes a stable hash for loop detection using MD5."""
        s = f"{name}:{json.dumps(args, sort_keys=True)}"
        return hashlib.md5(s.encode()).hexdigest()

    def _clean_artifacts(self, content: str) -> str:
        """Clean thinking blocks and tool call artifacts."""
        if not content:
            return ""
        content = re.sub(r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL)
        content = re.sub(r"\[TOOL_CALL:.*?\]", "", content)
        content = re.sub(r"\[/TOOL_CALL\]", "", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content.strip()

    def _check_completion(self, content: str) -> bool:
        """Checks for protocol-defined strict exit signals."""
        # Check for the specific strict token required by protocol
        if "EXIT_LOOP_NOW" in content:
            return True
        # Fallback for legacy models explicitly stating task is done
        if "TASK_COMPLETED_SUCCESSFULLY" in content:
            return True
        return False

    def _format_result(self, name: str, result: str, is_error: bool) -> str:
        prefix = "Error" if is_error else "Result"
        return f"[Tool: {name}] {prefix}: {result}"

    def get_stats(self) -> Dict[str, Any]:
        """Get workflow statistics."""
        return {
            "step_count": self.step_count,
            "tool_calls_count": self.tool_calls_count,
            "unique_tool_calls": len(self._tool_hash_history),
        }
