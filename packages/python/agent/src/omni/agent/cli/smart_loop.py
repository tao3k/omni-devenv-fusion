"""
agent/cli/smart_loop.py
[Agentic OS] OODA Loop implementation: Observe, Orient, Decide, Act.
Features: Self-Correction, Argument Validation, Planner State.
"""

import asyncio
import json
import uuid
import re
import ast
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.box import ROUNDED

from omni.foundation.config.logging import get_logger
from omni.foundation.services.llm import InferenceClient
from omni.agent.core.context.manager import ContextManager
from omni.agent.core.context.pruner import ContextPruner, PruningConfig

logger = get_logger("omni.agent.smart_loop")
console = Console()

class SmartAgentLoop:
    """
    Agentic OS OODA Loop implementation with Hard Cognitive Closure.
    """

    def __init__(self, kernel: Any, system_prompt: str = "You are Omni-Dev Fusion, an advanced Agentic OS."):
        self.kernel = kernel
        self.session_id = str(uuid.uuid4())[:8]
        self.engine = InferenceClient()
        
        pruning_config = PruningConfig(max_tokens=32000, retained_turns=10)
        self.context = ContextManager(pruner=ContextPruner(config=pruning_config))
        self.context.add_system_message(system_prompt)
        
        self.plan: Optional[str] = None
        self.history: List[Dict[str, Any]] = []
        self.step_count = 0
        self.last_error: Optional[str] = None
        self.found_paths: List[str] = [] # SSOT for report paths

    async def run(self, task: str, max_steps: int = 10) -> str:
        """Execute OODA loop with guaranteed output extraction."""
        console.print(Panel(f"[bold green]🧠 Agentic OS Booted[/bold green]\n[cyan]Task:[/cyan] {task}", title="OODA Loop", border_style="green"))
        
        await self._inject_historical_lessons(task)
        self.context.add_user_message(task)
        
        self.plan = await self._formulate_plan(task)
        from rich.text import Text
        console.print(Panel(Text(f"Plan: {self.plan}"), title="Strategy", border_style="yellow"))
        
        while self.step_count < max_steps:
            self.step_count += 1
            console.print(f"\n[bold cyan]Step {self.step_count}:[/bold cyan] Thinking...")
            
            reflection = await self._reflect_on_progress()
            self.context.add_system_message(f"[REFLECTION]\n{reflection}")
            
            decision = await self._decide_next_step(task)
            
            # --- CRITICAL: CLOSURE ENFORCEMENT ---
            if decision.get("action") == "finish":
                # If we have a path but haven't successfully read index.md, FORBID finish.
                if self.found_paths and not any("index.md" in str(m.get("content")).lower() for m in self.context.get_active_context() if m.get("role") == "user"):
                    console.print("[bold yellow]⚠️  Closure Guard: You must read the analysis report before finishing.[/bold yellow]")
                    decision = {
                        "action": "tool_call",
                        "tool": "filesystem.read_files",
                        "args": {"paths": [f"{self.found_paths[-1]}/index.md"]}
                    }
                else:
                    return decision.get("answer", "Task completed.")
                
            if decision.get("action") == "tool_call":
                tool_name = decision.get("tool")
                args = decision.get("args", {})
                
                console.print(f"🔧 [bold]Executing:[/bold] {tool_name}({json.dumps(args)})")
                output = await self._safe_execute_tool(tool_name, args)
                
                # --- AUTO PATH DISCOVERY ---
                # Search for harvest_dir in output string using regex (more robust than dict check)
                path_match = re.search(r'/(?:[\w\.\-]+/)*\.data/harvested/[\w\.\-]+', str(output))
                if path_match:
                    path = path_match.group(0).rstrip("'"")
                    if path not in self.found_paths:
                        self.found_paths.append(path)
                        console.print(f"[dim]📍 Captured report path: {path}[/dim]")

                if "error" not in str(output).lower() and self.last_error:
                    await self._harvest_lesson(tool_name, self.last_error)
                    self.last_error = None
                elif "error" in str(output).lower():
                    self.last_error = f"Attempted {tool_name} with {args}, got: {output}"

                self.context.update_last_assistant(f"Action: {tool_name}\nArgs: {json.dumps(args)}")
                # Prune result to keep context clean
                pruned_output = str(output)[:800] + "..." if len(str(output)) > 800 else str(output)
                self.context.add_user_message(f"Tool Result ({tool_name}):\n{pruned_output}")
            
        return "Task reached maximum steps."

    async def _formulate_plan(self, task: str) -> str:
        prompt = f"Task: '{task}'. Formulate a plan. NOTE: If research is performed, the final step MUST be reading the 'index.md' file in the output directory."
        response = await self.engine.complete(system_prompt=self.context.get_system_prompt(), user_query=prompt, max_tokens=512)
        plan = response.get("content", "Execute.")
        self.context.update_last_assistant(f"Initial Plan: {plan}")
        return plan

    async def _reflect_on_progress(self) -> str:
        history = self.context.get_active_context()
        if not history: return "New task."
        prompt = f"Check if a research directory was found. If yes, check if you have read its index.md yet. Concise reflection only."
        response = await self.engine.complete(system_prompt=self.context.get_system_prompt(), messages=history, user_query=prompt, max_tokens=256)
        return response.get("content", "Continuing.")

    async def _decide_next_step(self, task: str) -> Dict[str, Any]:
        decision_prompt = f"""Current Plan: {self.plan}
Discovered Paths: {self.found_paths}

Decide next action. 
If 'researcher' tool has finished, you MUST call `filesystem.read_files` with paths=['{self.found_paths[-1] if self.found_paths else "..."}/index.md'] before finishing.
"""
        response = await self.engine.complete(system_prompt=self.context.get_system_prompt(), messages=self.context.get_active_context(), user_query=decision_prompt, max_tokens=1024)
        return self._parse_llm_response(response.get("content", "{{}}"))

    async def _safe_execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        import ast
        try:
            clean_args = {}
            for k, v in args.items():
                if isinstance(v, str) and v.strip().startswith(('[', '{')):
                    try: v = ast.literal_eval(v.strip())
                    except: pass
                if isinstance(v, str): v = v.strip().strip("'" ).strip('"')
                if isinstance(v, list): v = [i.strip("'" ) if isinstance(i, str) else i for i in v]
                clean_args[k] = v
            return await self.kernel.execute_tool(tool_name, clean_args)
        except Exception as e: return f"ERROR: {str(e)}"

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        content_lower = content.lower()
        
        # 1. JSON Capture
        json_match = re.search(r'{{.*}}', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                if isinstance(data, dict) and ("tool" in data or "action" in data):
                    if "tool" in data and "action" not in data: data["action"] = "tool_call"
                    
                    # 2. ANTI-LAZINESS: If finish but text says "I will read", force read.
                    if data.get("action") == "finish":
                        answer = str(data.get("answer", "")).lower()
                        if any(kw in answer for kw in ["读取", "read", "show", "展示"]):
                            if self.found_paths:
                                return {"action": "tool_call", "tool": "filesystem.read_files", "args": {"paths": [f"{self.found_paths[-1]}/index.md"]}}
                    return data
            except: pass
        
        # 3. TEXT INTENT Capture
        recovery_keywords = ["让我", "读取", "read", "cat ", "show", "分析报告"]
        if any(kw in content_lower for kw in recovery_keywords):
            args = {"intent": "Read analysis results"}
            if self.found_paths: args["paths"] = [f"{self.found_paths[-1]}/index.md"]
            return {"action": "tool_call", "tool": "filesystem.read_files", "args": args}
            
        return {"action": "finish", "answer": content}

    async def _inject_historical_lessons(self, task: str) -> None:
        try:
            lessons = await self.kernel.execute_tool("note_taker.search_notes", {"query": f"pitfall {task}", "category": "techniques"})
            if lessons and "results" in str(lessons):
                self.context.add_system_message(f"[HISTORICAL LESSONS]\n{lessons}")
        except: pass

    async def _harvest_lesson(self, tool_name: str, failed_attempt: str) -> None:
        try:
            await self.kernel.execute_tool("note_taker.update_knowledge_base", {
                "category": "techniques", "title": f"Fix: {tool_name}",
                "content": f"Correction: {tool_name}. Failed: {failed_attempt}", "tags": ["fix"]
            })
        except: pass