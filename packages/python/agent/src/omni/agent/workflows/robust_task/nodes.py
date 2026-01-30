import re
import json
import asyncio
from typing import Any, Dict, List, Optional
from .state import RobustTaskState, Step
from .prompts import CLARIFICATION_PROMPT, PLANNING_PROMPT, EXECUTION_PROMPT, VALIDATION_PROMPT
from .utils import parse_xml_tag, parse_xml_steps, extract_json_from_action, map_action_data

from omni.foundation.services.llm.client import InferenceClient
from omni.core.kernel import get_kernel

# Initialize Client (Lazy load in real app, but global here for simplicity)
llm_client = InferenceClient()

async def call_llm(prompt: str, system: str = "You are a helpful assistant.") -> str:
    """Real LLM Call using InferenceClient."""
    try:
        result = await llm_client.complete(
            system_prompt=system,
            user_query=prompt,
            max_tokens=4096, # Ensure enough space for plans
        )
        if result["success"]:
            return result["content"]
        else:
            return f"<error>{result['error']}</error>"
    except Exception as e:
        return f"<error>{str(e)}</error>"

def record_event(type: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Helper to create a trace event."""
    return [{"type": type, "data": data}]

async def get_skill_documentation(skill_name: str) -> str:
    """Fetch the protocol content from SKILL.md for a given skill."""
    kernel = get_kernel()
    skill = kernel.skill_context.get_skill(skill_name)
    if skill and hasattr(skill, "protocol_content"):
        return skill.protocol_content
    return "No detailed documentation available."

async def discovery_node(state: RobustTaskState) -> Dict[str, Any]:
    """
    Enhanced Discovery Node - Performs Intent Normalization, Multi-source Recall,
    and Skill Documentation Deep-Dive.
    """
    kernel = get_kernel()
    if not kernel.is_ready:
        await kernel.initialize()
        
    raw_request = state["user_request"]
    trace = []
    
    # 1. Intent Normalization & Translation (LLM Call)
    normalization_prompt = f"""
    You are an Intent Normalizer. Translate and clean the user request into standardized English.
    
    Raw Request: {raw_request}
    
    Output format:
    <thought>Brief reasoning</thought>
    <intent>Cleaned English Intent (Action + Object)</intent>
    <keywords>3-5 specific keywords for search</keywords>
    """
    norm_response = await call_llm(normalization_prompt, system="You are an intent classifier.")
    cleaned_intent = parse_xml_tag(norm_response, "intent") or raw_request
    keywords_str = parse_xml_tag(norm_response, "keywords")
    thought = parse_xml_tag(norm_response, "thought")
    
    trace.extend(record_event("llm_hit", {"task": "intent_normalization", "intent": cleaned_intent}))

    # 2. Multi-query Memory Recall (Subgraph)
    from omni.agent.workflows.memory.graph import build_memory_graph
    memory_app = build_memory_graph()
    
    # Query 1: Context Specific
    # Query 2: Meta-workflow Lessons
    memory_context = ""
    try:
        # Context search
        mem_state_context = await memory_app.ainvoke({"query": cleaned_intent, "mode": "recall"})
        # Meta search
        mem_state_meta = await memory_app.ainvoke({"query": "general workflow lessons error recovery", "mode": "recall"})
        
        memory_context = f"CONTEXTUAL:\n{mem_state_context.get('final_context', '')}\n\nGENERAL LESSONS:\n{mem_state_meta.get('final_context', '')}"
        trace.extend(record_event("memory_op", {"action": "multi_query_recall", "status": "success"}))
    except Exception as e:
        memory_context = f"Memory recall unavailable: {e}"

    # 2. Discover Tools based on Cleaned Intent
    discovery_query = f"{cleaned_intent} {keywords_str or ''}"
    tools = []
    
    try:
        discovery_args = {"intent": discovery_query, "limit": 10}
        trace.extend(record_event("tool_call_start", {"tool": "skill.discover", "args": discovery_args}))
        
        # Use the standard tool execution (now refactored internally)
        discovery_result = await kernel.execute_tool("skill.discover", discovery_args)
        
        if isinstance(discovery_result, dict):
            tools = discovery_result.get("discovered_capabilities", [])
        
        trace.extend(record_event("tool_call_end", {"tool": "skill.discover", "count": len(tools), "success": True}))
    except Exception as e:
        trace.extend(record_event("error", {"msg": f"Discovery failed: {e}"}))

    # 4. Skill Documentation Deep-Dive
    # If we have matches, get the full protocol for the top 2 candidates
    enriched_tools = []
    for i, t in enumerate(tools[:3]):
        skill_id = t.get("tool", "")
        skill_prefix = skill_id.split(".")[0] if "." in skill_id else skill_id
        
        doc = await get_skill_documentation(skill_prefix)
        t["detailed_docs"] = doc[:2000] # Truncate to save context
        enriched_tools.append(t)
        trace.extend(record_event("discovery_enrichment", {"skill": skill_prefix}))

    # Add Essential tools if missing
    essential_tool_ids = ["skill.discover", "note_taker.summarize_session"]
    current_tool_ids = {t.get("tool") for t in tools}
    for et_id in essential_tool_ids:
        if et_id not in current_tool_ids:
            et_handler = kernel.skill_context.get_command(et_id)
            if et_handler:
                enriched_tools.append({
                    "tool": et_id,
                    "description": "Essential tool.",
                    "usage": f'@omni("{et_id}", {{...}})',
                    "detailed_docs": "Standard tool protocol."
                })

    return {
        "discovered_tools": enriched_tools, 
        "last_thought": thought, 
        "trace": trace, 
        "memory_context": memory_context,
        "clarified_goal": cleaned_intent
    }

def format_tools_for_prompt(tools: List[Dict[str, Any]]) -> str:
    """Format discovered_tools for LLM consumption (Compact + Score + Detailed Docs)."""
    lines = []
    for t in tools:
        tool_id = t.get('tool')
        score = t.get('score', 0.0)
        desc = t.get('description', '')
        desc_short = desc.split("\n")[0][:150]
        usage = t.get('usage', '')
        
        tool_block = f"### Tool: {tool_id} (Match Score: {score:.3f})\nDescription: {desc_short}\nUsage: {usage}"
        
        if "detailed_docs" in t and t["detailed_docs"] != "No detailed documentation available.":
            # Include a snippet of the detailed docs/protocol
            doc_snippet = t["detailed_docs"][:1000]
            tool_block += f"\nDetailed Protocol/Guidelines:\n{doc_snippet}"
            
        lines.append(tool_block)
    return "\n\n".join(lines)

async def clarify_node(state: RobustTaskState) -> Dict[str, Any]:
    # print("--- Clarify Node ---")
    
    tools_str = format_tools_for_prompt(state.get("discovered_tools", []))
    memory_str = state.get("memory_context", "No prior knowledge available.")
    
    prompt = CLARIFICATION_PROMPT.format(
        user_request=state["user_request"],
        memory_context=memory_str,
        tools=tools_str
    )
    
    # Inject tool awareness into clarification
    system_prompt = "You are an expert requirement analyst."
    
    response = await call_llm(prompt, system=system_prompt)
    
    # print(f"[LLM Response Preview]: {response[:100]}...")

    goal = parse_xml_tag(response, "goal")
    question = parse_xml_tag(response, "question")
    thought = parse_xml_tag(response, "thought")
    # print(f"[Clarification Thought]: {thought}")
    
    trace = record_event("llm_hit", {"task": "clarification", "goal": goal or "Awaiting clarification"})

    if goal:
        return {"clarified_goal": goal, "status": "planning", "last_thought": thought, "trace": trace}
    else:
        # Real-world: Ask user. Simulation: Fail or retry.
        # print(f"Need clarification: {question}")
        if state["retry_count"] > 2:
             return {"status": "failed", "error": f"Clarification failed: {question}", "last_thought": thought, "trace": trace}
        return {"status": "clarifying", "retry_count": state["retry_count"] + 1, "last_thought": thought, "trace": trace} 

async def plan_node(state: RobustTaskState) -> Dict[str, Any]:
    # print("--- Plan Node ---")
    
    tools_str = format_tools_for_prompt(state.get("discovered_tools", []))
    memory_str = state.get("memory_context", "No prior knowledge available.")
    user_feedback = state.get("user_feedback", "No feedback provided.")
    
    # DEBUG: Check if feedback is received
    trace = record_event("system_log", {"msg": f"Planning with feedback: {user_feedback}"})
    
    prompt = PLANNING_PROMPT.format(
        goal=state["clarified_goal"], 
        context=str(state.get("context_files", [])),
        memory_context=memory_str,
        user_feedback=user_feedback,
        tools=tools_str
    )
    response = await call_llm(prompt, system="You are an expert software architect.")
    
    thought = parse_xml_tag(response, "thought")
    steps = parse_xml_steps(response)
    
    if not steps:
         # print("Failed to parse plan steps. Using single step fallback.")
         steps.append({"id": "1", "description": f"Execute goal: {state['clarified_goal']}", "status": "pending", "result": "", "tool_calls": []})

    trace.extend(record_event("llm_hit", {"task": "planning", "steps": len(steps)}))
    
    # We return the new plan and CLEAR the feedback so it's not reused unless provided again
    return {
        "plan": {"steps": steps, "current_step_index": 0}, 
        "status": "executing", 
        "last_thought": thought, 
        "trace": trace,
        "user_feedback": "" # Reset feedback
    }

async def execute_node(state: RobustTaskState) -> Dict[str, Any]:
    # print("--- Execute Node ---")
    plan = state["plan"]
    index = plan["current_step_index"]
    
    if index >= len(plan["steps"]):
        return {"status": "validating"}
        
    step = plan["steps"][index]
    # print(f"Executing Step {step['id']}: {step['description']}")
    
    # We use the tools discovered in the Discovery phase
    tools_str = format_tools_for_prompt(state.get("discovered_tools", []))
    
    prompt = EXECUTION_PROMPT.format(
        step_description=step["description"], 
        context=f"Goal: {state['clarified_goal']}", 
        history="\n".join(state.get("execution_history", [])),
        tools=tools_str
    )
    response = await call_llm(prompt, system="You are an expert developer. Output only valid XML.")
    
    action_json_str = parse_xml_tag(response, "action")
    thought = parse_xml_tag(response, "thought")
    # print(f"[Thought]: {thought}")
    
    execution_result = ""
    trace = record_event("llm_hit", {"task": "execution_strategy", "step": step["id"]})
    
    if action_json_str:
        action_raw = extract_json_from_action(action_json_str)
        if action_raw:
            tool_name, tool_args = map_action_data(action_raw)
            
            if tool_name:
                trace.extend(record_event("tool_call_start", {"tool": tool_name, "args": tool_args}))
                
                # Ensure kernel is ready
                kernel = get_kernel()
                if not kernel.is_ready:
                    await kernel.initialize()
                
                try:
                    # Kernel execute_tool expects args as dict
                    tool_output = await kernel.execute_tool(tool_name, tool_args)
                    execution_result = f"Tool {tool_name} Output: {str(tool_output)}"
                    trace.extend(record_event("tool_call_end", {"tool": tool_name, "status": "success"}))
                except Exception as e:
                    execution_result = f"Tool Execution Failed: {str(e)}"
                    trace.extend(record_event("tool_call_end", {"tool": tool_name, "status": "failed", "error": str(e)}))
            else:
                execution_result = f"Failed to identify tool name in JSON: {action_raw}"
                trace.extend(record_event("error", {"msg": "Missing tool name", "raw": action_raw}))
        else:
             execution_result = f"Failed to parse action JSON: {action_json_str}"
             trace.extend(record_event("error", {"msg": "JSON parse error", "raw": action_json_str}))
    else:
        execution_result = "No executable action found in LLM response."
        trace.extend(record_event("warning", {"msg": "No action tag found"}))
    
    # print(f"[Result]: {execution_result[:200]}...")

    # Update step
    step["result"] = execution_result
    step["status"] = "completed"
    
    # Return updates
    return {
        "plan": plan, 
        "execution_history": [f"Step {step['id']} Result: {execution_result}"],
        "status": "executing_check_next",
        "last_thought": thought,
        "trace": trace
    }

def check_execution_progress(state: RobustTaskState) -> str:
    plan = state["plan"]
    if plan["current_step_index"] >= len(plan["steps"]) - 1:
        return "validate"
    return "continue"

def advance_step(state: RobustTaskState) -> Dict[str, Any]:
    plan = state["plan"]
    plan["current_step_index"] += 1
    return {"plan": plan}

async def validate_node(state: RobustTaskState) -> Dict[str, Any]:
    # print("--- Validate Node ---")
    prompt = VALIDATION_PROMPT.format(goal=state["clarified_goal"], history="\n".join(state["execution_history"]))
    response = await call_llm(prompt, system="You are a QA engineer.")
    
    verdict = parse_xml_tag(response, "verdict")
    feedback = parse_xml_tag(response, "feedback")
    thought = parse_xml_tag(response, "thought")
    
    is_valid = "PASS" in verdict.upper()
    trace = record_event("validation", {"verdict": verdict})
    
    # Automatic Lesson Learning
    if is_valid and state.get("retry_count", 0) > 0:
        try:
            lesson_content = f"Task: {state['user_request']}.\nOutcome: Initially failed, then succeeded.\nFix Strategy: {thought}"
            trace.extend(record_event("learning", {"msg": "Storing lesson from failure recovery"}))
            from omni.agent.workflows.memory.graph import build_memory_graph
            memory_app = build_memory_graph()
            await memory_app.ainvoke({
                "content": lesson_content, 
                "mode": "store", 
                "query": "lesson learned error recovery"
            })
        except Exception as e:
            trace.extend(record_event("error", {"msg": f"Failed to store lesson: {e}"}))
    
    return {
        "validation_result": {"is_valid": is_valid, "feedback": feedback},
        "status": "completed" if is_valid else "failed",
        "last_thought": thought,
        "trace": trace
    }

async def summary_node(state: RobustTaskState) -> Dict[str, Any]:
    """Generate a final Markdown summary of the session."""
    # print("--- Summary Node ---")
    
    # Check if we already have a success report from validate_node
    history = "\n".join(state.get("execution_history", []))
    goal = state["clarified_goal"]
    status = state["status"]
    
    prompt = f"""
    You are a Technical Writer. Create a final summary report for the following task execution session.
    
    Goal: {goal}
    Final Status: {status}
    
    Execution History:
    {history}
    
    Format the report in Markdown with the following sections:
    1. **Task Overview**: Original request and clarified goal.
    2. **Execution Steps**: Brief list of what was done.
    3. **Key Discoveries/Achievements**: What was found or accomplished.
    4. **Lessons Learned**: Any mistakes made and how they were corrected (referencing reflections if applicable).
    5. **Final Verdict**: Clear statement on whether the goal was achieved.
    
    Keep it professional and concise.
    """
    
    response = await call_llm(prompt, system="You are a professional technical writer.")
    
    return {"final_summary": response}
