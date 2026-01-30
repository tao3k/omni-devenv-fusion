from typing import Any, Dict, List
from .state import AgentState
from omni.foundation.services.llm import InferenceClient
from omni.agent.core.omni.react import ArgumentValidator, OutputCompressor
import json
import hashlib

# Singleton for now, should be injected
engine = InferenceClient()

async def think_node(state: AgentState) -> Dict[str, Any]:
    print("🧠 Thinking...")
    
    response = await engine.complete(
        system_prompt=state["system_prompt"],
        user_query=state["user_query"], # Or use last message?
        messages=state["messages"],
        tools=state.get("available_tools")
    )
    
    content = response.get("content", "")
    tool_calls = response.get("tool_calls", [])
    
    # Check for exit signals
    exit_reason = None
    if "EXIT_LOOP_NOW" in content or "TASK_COMPLETED_SUCCESSFULLY" in content:
        exit_reason = "completed"
    
    return {
        "last_response": content,
        "tool_calls": tool_calls,
        "exit_reason": exit_reason,
        "messages": [{"role": "assistant", "content": content}],
        "step_count": state["step_count"] + 1
    }

async def act_node(state: AgentState) -> Dict[str, Any]:
    print("⚙️ Acting...")
    tool_results = []
    messages = []
    consecutive_errors = state["consecutive_errors"]
    tool_hash_history = state.get("tool_hash_history", [])
    
    # Execute tool (Mock logic for now, needs Kernel injection)
    # In real implementation, we'd use state["kernel"].execute_tool
    
    # We need to access Kernel here. 
    # For now, let's assume it's passed in via a context variable or we get it globally
    from omni.core.kernel import get_kernel
    kernel = get_kernel()
    if not kernel.is_ready:
        await kernel.initialize()

    for tool_call in state["tool_calls"]:
        tool_name = tool_call.get("name")
        tool_input = tool_call.get("input", {})
        
        # 1. Loop Detection
        s = f"{tool_name}:{json.dumps(tool_input, sort_keys=True)}"
        call_hash = hashlib.md5(s.encode()).hexdigest()
        
        if call_hash in tool_hash_history:
            result = "[System Warning] Loop Detected: You have already executed this tool with these exact arguments."
            is_error = True
            consecutive_errors += 1
        else:
            tool_hash_history.append(call_hash)
            
            # 2. Execution
            try:
                print(f"  > Executing: {tool_name}")
                # Use Kernel to execute
                result = await kernel.execute_tool(tool_name, tool_input)
                is_error = False
                consecutive_errors = 0 # Reset
            except Exception as e:
                result = f"Runtime Error: {str(e)}"
                is_error = True
                consecutive_errors += 1
        
        # 3. Format Result
        prefix = "Error" if is_error else "Result"
        formatted = f"[Tool: {tool_name}] {prefix}: {result}"
        compressed = OutputCompressor.compress(formatted)
        
        tool_results.append({"name": tool_name, "result": result, "error": is_error})
        messages.append({"role": "user", "content": compressed})

    return {
        "tool_results": tool_results,
        "messages": messages,
        "consecutive_errors": consecutive_errors,
        "tool_hash_history": tool_hash_history,
        "tool_calls_count": state["tool_calls_count"] + len(state["tool_calls"])
    }

async def reflect_node(state: AgentState) -> Dict[str, Any]:
    # Simple check for stagnation
    if state["consecutive_errors"] >= 3:
        print("🛑 Max errors reached")
        return {"exit_reason": "max_errors"}
    
    return {}
