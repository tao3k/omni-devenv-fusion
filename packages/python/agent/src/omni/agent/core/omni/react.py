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
            if not tool_calls:
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
