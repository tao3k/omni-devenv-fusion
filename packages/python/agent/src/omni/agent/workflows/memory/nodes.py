from typing import Any, Dict, List
from .state import MemoryState
from omni.core.kernel import get_kernel
from omni.foundation.services.llm.client import InferenceClient

# Initialize LLM Client
llm_client = InferenceClient()

def record_event(type: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{"type": type, "data": data}]

async def recall_node(state: MemoryState) -> Dict[str, Any]:
    """Retrieve relevant knowledge using Hybrid Search AND Note Search."""
    kernel = get_kernel()
    if not kernel.is_ready: await kernel.initialize()
    
    query = state["query"]
    trace = record_event("memory_op", {"action": "recall_start", "query": query})
    
    all_docs = []
    
    # 1. Knowledge Base (Hybrid Search)
    try:
        kb_result = await kernel.execute_tool("knowledge.recall", {"query": query, "limit": 3})
        if isinstance(kb_result, list):
            for d in kb_result: d["source_type"] = "knowledge_base"
            all_docs.extend(kb_result)
        elif isinstance(kb_result, dict) and "results" in kb_result:
            items = kb_result["results"]
            for d in items: d["source_type"] = "knowledge_base"
            all_docs.extend(items)
        trace.extend(record_event("memory_op", {"action": "kb_search", "count": len(all_docs)}))
    except Exception as e:
        trace.extend(record_event("error", {"msg": f"KB recall failed: {e}"}))

    # 2. Notes & Session History (Keyword Search)
    try:
        note_result = await kernel.execute_tool("note_taker.search_notes", {"query": query, "limit": 3})
        if isinstance(note_result, dict) and "results" in note_result:
            notes = note_result["results"]
            for n in notes: n["source_type"] = "notes"
            all_docs.extend(notes)
            trace.extend(record_event("memory_op", {"action": "note_search", "count": len(notes)}))
    except Exception as e:
        trace.extend(record_event("error", {"msg": f"Note search failed: {e}"}))
            
    return {"retrieved_docs": all_docs, "trace": trace}

async def synthesize_node(state: MemoryState) -> Dict[str, Any]:
    """Synthesize retrieved docs into a concise context block using LLM."""
    docs = state.get("retrieved_docs", [])
    query = state["query"]
    
    if not docs:
        trace = record_event("memory_op", {"action": "synthesis", "result": "empty"})
        return {"final_context": "No relevant memories found.", "trace": trace}
        
    # Prepare prompt for synthesis
    docs_text = ""
    for i, d in enumerate(docs):
        source = d.get("source", "unknown")
        content = d.get("content", "")[:500] # Truncate for prompt
        docs_text += f"Document {i+1} ({source}):\n{content}\n\n"
        
    prompt = f"""
    You are a Memory Synthesizer.
    Task: Summarize the following retrieved knowledge documents into a concise briefing relevant to the user's query.
    
    User Query: {query}
    
    Retrieved Documents:
    {docs_text}
    
    Output Format:
    - Bullet points of key facts/insights.
    - Ignore irrelevant documents.
    - If documents contradict, note the conflict.
    - Keep it under 200 words.
    """
    
    try:
        response = await llm_client.complete(
            system_prompt="You are a helpful assistant.",
            user_query=prompt,
            max_tokens=512
        )
        summary = response.get("content", "Synthesis failed.")
        trace = record_event("memory_op", {"action": "synthesis", "input_docs": len(docs)})
        return {"final_context": summary, "trace": trace}
        
    except Exception as e:
        return {"final_context": f"Error synthesizing memory: {e}", "trace": record_event("error", {"msg": str(e)})}

async def store_node(state: MemoryState) -> Dict[str, Any]:
    """Store insights into Long-term Memory."""
    kernel = get_kernel()
    if not kernel.is_ready: await kernel.initialize()
    
    content = state.get("content")
    if not content:
        return {"storage_result": "No content to store."}
        
    try:
        # Use memory.save_memory for facts/insights
        result = await kernel.execute_tool("memory.save_memory", {"fact": content})
        trace = record_event("memory_op", {"action": "store", "content_preview": content[:50]})
        return {"storage_result": str(result), "trace": trace}
    except Exception as e:
        return {"storage_result": f"Storage failed: {e}", "trace": record_event("error", {"msg": str(e)})}

