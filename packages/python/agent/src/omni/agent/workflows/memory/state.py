from typing import TypedDict, List, Dict, Any, Optional, Annotated
import operator


class MemoryState(TypedDict):
    # Input
    query: str
    content: Optional[str]
    mode: str  # "recall" | "store"

    # Internal
    retrieved_docs: List[Dict[str, Any]]
    trace: Annotated[List[Dict[str, Any]], operator.add]

    # Output
    final_context: str
    storage_result: str
