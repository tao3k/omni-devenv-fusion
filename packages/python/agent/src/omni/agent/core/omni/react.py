"""
react.py - ReAct Workflow Implementation

ReAct (Reasoning + Acting) pattern for tool-augmented LLM:
1. LLM thinks about the task
2. LLM decides to use tools (if needed)
3. Execute tool calls and collect results
4. LLM generates final response

This module can be replaced with LangGraph for more complex workflows.
"""

from typing import Any

from omni.foundation.services.llm import InferenceClient
from omni.foundation.config.logging import get_logger

from .logging import log_completion, log_result, log_step, log_llm_response

logger = get_logger("omni.agent.react")


class ReActWorkflow:
    """ReAct (Reasoning + Acting) workflow executor.

    Features:
    - Iterative LLM + tool execution
    - Step tracking and statistics
    - Tool result formatting for LLM
    - Max tool call limits for safety
    """

    def __init__(
        self,
        engine: InferenceClient,
        get_tool_schemas,
        execute_tool,
        max_tool_calls: int = 10,
        verbose: bool = False,
    ):
        """Initialize ReAct workflow.

        Args:
            engine: InferenceClient for LLM calls
            get_tool_schemas: Function to get tool schemas
            execute_tool: Function to execute a tool call
            max_tool_calls: Safety limit on tool calls
            verbose: Enable verbose logging
        """
        self.engine = engine
        self.get_tool_schemas = get_tool_schemas
        self.execute_tool = execute_tool
        self.max_tool_calls = max_tool_calls
        self.verbose = verbose

        self.step_count = 0
        self.tool_calls_count = 0

    async def run(
        self,
        task: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> str:
        """Execute the ReAct workflow.

        Args:
            task: The user's task description
            system_prompt: System prompt for LLM
            messages: Current conversation messages

        Returns:
            Final LLM response
        """
        tools = await self.get_tool_schemas()

        # DEBUG: Log tools count
        if self.verbose:
            logger.debug(f"ReAct: tools count = {len(tools)}")

        # ReAct loop: continue until no more tool calls
        response: dict[str, Any] = {"content": "", "tool_calls": []}

        while True:
            self.step_count += 1

            if self.verbose:
                logger.debug(
                    f"ReAct: step={self.step_count}, tool_calls={self.tool_calls_count}, max={self.max_tool_calls}"
                )

            # Check safety limit
            if self.tool_calls_count >= self.max_tool_calls:
                if self.verbose:
                    print(f"⚠️  Max tool calls reached ({self.max_tool_calls})")
                break

            # Call LLM with tools (if available)
            response = await self.engine.complete(
                system_prompt=system_prompt,
                user_query=task,
                messages=messages,
                tools=tools if tools else None,
            )

            # Log LLM response (thinking process)
            log_llm_response(response["content"])

            # Clean thinking and tool call artifacts from response for user output
            import re

            clean_content = response["content"]
            # Remove thinking blocks (both for log and user)
            clean_content = re.sub(r"<thinking>.*?</thinking>", "", clean_content, flags=re.DOTALL)
            # Remove tool call artifacts from content
            clean_content = re.sub(r"\[TOOL_CALL:[^\]]*\]", "", clean_content)
            clean_content = re.sub(r"\[/TOOL_CALL\]", "", clean_content)
            clean_content = re.sub(r"\[TOOL_CALL:[^\]]*>\s*", "", clean_content)
            clean_content = re.sub(r"\s*\[/TOOL_CALL\]\s*", "", clean_content)
            clean_content = re.sub(r"\n{3,}", "\n\n", clean_content)
            clean_content = clean_content.strip()

            # Update conversation with cleaned content
            messages.append({"role": "assistant", "content": clean_content})

            # Use cleaned content for final response
            response["content"] = clean_content

            # Check for tool calls
            tool_calls = response.get("tool_calls", [])

            if self.verbose:
                logger.debug(f"ReAct: tool_calls in response = {len(tool_calls)}")
                if tool_calls:
                    logger.debug(f"ReAct: tool_names = {[tc.get('name') for tc in tool_calls]}")

            # Check if LLM declared task complete (allows LLM to self-determine completion)
            content = response.get("content", "")
            completion_patterns = [
                r"✅\s*Completed",
                r"##\s*Summary",
                r"##\s*Reflection",
                r"Task completed",
            ]
            llm_declared_complete = any(
                re.search(p, content, re.IGNORECASE) for p in completion_patterns
            )

            if not tool_calls or llm_declared_complete:
                # No more tools needed OR LLM declared completion - exit loop
                log_completion(self.step_count, self.tool_calls_count)
                break

            # Execute each tool call
            for tool_call in tool_calls:
                self.tool_calls_count += 1

                # Log and execute
                tool_name = tool_call.get("name", "")
                tool_input = tool_call.get("input", {})

                log_step(
                    self.step_count,
                    self.max_tool_calls,
                    tool_name,
                    tool_input,
                )

                try:
                    result = await self.execute_tool(tool_name, tool_input)
                    is_error = False
                except Exception as e:
                    result = str(e)
                    is_error = True

                log_result(result, is_error=is_error)

                # Format result for LLM
                result_content = self._format_tool_result(tool_name, result, is_error)
                messages.append({"role": "user", "content": result_content})

        # Final cleanup of response content before returning
        final_content = response.get("content", "").strip()
        if final_content:
            import re

            # Remove any remaining thinking blocks
            final_content = re.sub(r"<thinking>.*?</thinking>", "", final_content, flags=re.DOTALL)
            # Remove any remaining tool call artifacts
            final_content = re.sub(r"\[TOOL_CALL:[^\]]*\]", "", final_content)
            final_content = re.sub(r"\[/TOOL_CALL\]", "", final_content)
            # Clean up extra whitespace
            final_content = re.sub(r"\n{3,}", "\n\n", final_content)
            final_content = final_content.strip()
            response["content"] = final_content

        return response["content"]

    def _format_tool_result(self, tool_name: str, result: Any, is_error: bool) -> str:
        """Format tool result for LLM consumption."""
        if is_error:
            return f"[Tool: {tool_name}] Error: {result}"

        result_str = str(result) if result is not None else "No result"

        # Truncate long results
        if len(result_str) > 2000:
            result_str = result_str[:2000] + "... [truncated]"

        return f"[Tool: {tool_name}] {result_str}"

    def get_stats(self) -> dict[str, Any]:
        """Get workflow statistics."""
        return {
            "step_count": self.step_count,
            "tool_calls_count": self.tool_calls_count,
        }
