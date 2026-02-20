# omni.langgraph.chunked

Reusable **chunked/sharded processing engine** for long content in LangGraph and MCP tool flows.

Use when skills need to:

- Process very long content (repos, papers, logs) without timeouts or context overflow
- Let the LLM drive **one step per MCP call** (start → process chunk → … → synthesize)
- Enforce **bounded chunk size** (max items per chunk, max total, merge tiny chunks)

## Quick use

### 1. Normalize chunks (split oversized, cap total, merge tiny)

```python
from omni.langgraph.chunked import normalize_chunks, ChunkConfig

items = [
    {"name": "Core", "targets": ["a.py", "b.py", "c.py", "d.py", "e.py", "f.py"], "description": "Core logic"},
    {"name": "Utils", "targets": ["x.py"], "description": "Helpers"},
]
config = ChunkConfig(max_per_chunk=5, max_total=30, min_to_merge=2)
normalized = normalize_chunks(items, config)
# Core split into 2 chunks; Utils can be merged with another small one
```

### 2. Common engine + step runner (start | shard | synthesize)

```python
from omni.langgraph.chunked import (
    ChunkedWorkflowEngine,
    build_chunked_session_store_adapters,
    build_child_work_items,
    build_chunk_plan_from_queue,
    build_summary_payload_from_chunked_result,
    build_summary_payload_from_chunked_step_result,
    build_summary_payload_from_state,
    collect_chunk_progress,
    extract_chunk_plan,
    extract_state_or_scalar_result,
    normalize_selected_ids,
    persist_chunked_lazy_start_state,
    run_chunked_action_dispatch,
    run_chunked_auto_complete,
    run_chunked_full_document_action,
    run_chunked_lazy_start_batch_dispatch,
    run_chunked_child_step,
    run_chunked_complete_from_session,
    run_chunked_fanout_shard,
    run_chunked_fanout_synthesize,
    run_chunked_parallel_selected,
    run_chunked_step,
)

engine = ChunkedWorkflowEngine(
    workflow_type="my_chunked",
    run_start=lambda: my_setup_and_plan(),
    run_step=my_process_one_chunk,
    run_synthesize=my_synthesize,
    queue_key="shards_queue",
    # Optional hooks for custom start behavior:
    # prepare_start_state=lambda state, sid: {...},
    # after_start_save=lambda sid, state: persist_child_states(...),
    # build_start_response=lambda sid, state: {"shard_count": ...},
)

start = await engine.run_step(session_id="", action="start", auto_complete=False)
next_step = await engine.run_step(session_id=start["session_id"], action="shard")
done = await engine.run_step(session_id=start["session_id"], action="synthesize")

# Resume from existing session and complete all remaining chunks in one call.
resumed = await engine.run_complete_from_session(start["session_id"])
# Or via runner wrapper:
resumed2 = await run_chunked_complete_from_session(
    workflow_type="my_chunked",
    session_id=start["session_id"],
    run_start=lambda: {},
    run_step=my_process_one_chunk,
    run_synthesize=my_synthesize,
    queue_key="shards_queue",
)

# When action=start and auto_complete=True (default): runs full workflow in one call.
# Avoids N+2 agent rounds (each step would otherwise count as one round).
result = await run_chunked_step(
    workflow_type="my_chunked",
    session_id=session_id,
    action="start",  # or "shard", "synthesize"
    run_start=lambda: my_setup_and_plan(),
    run_step=my_process_one_chunk,
    run_synthesize=my_synthesize,
    queue_key="shards_queue",  # if your state uses "shards_queue" not "queue"
    auto_complete=True,  # default: action=start runs full workflow in one call
)
# Or call run_chunked_auto_complete directly for one-shot full run.

# Optional dispatcher for custom action routing with shared guards:
dispatch_result = await run_chunked_action_dispatch(
    action=action,
    session_id=session_id,
    workflow_type="my_chunked",
    load_state=load_state,
    on_start=lambda: start_handler(),
    on_shard=lambda sid, state: shard_handler(sid, state),
    on_synthesize=lambda sid, state: synth_handler(sid, state),
)

# For "start + lazy cached batch" workflows (e.g. knowledge recall):
lazy_result = await run_chunked_lazy_start_batch_dispatch(
    action=action,  # start | batch (fetch alias optional)
    session_id=session_id,
    batch_index=batch_index,
    workflow_type="my_chunked",
    load_state=load_state,
    on_start=lambda: start_handler(),
    load_session_state=load_session_state,
    save_session_state=save_session_state,
    fetch_rows=fetch_rows,
)

# Optional adapter helpers when using ChunkedSessionStore directly:
load_state, load_session_state, save_session_state = build_chunked_session_store_adapters(store)
persist_chunked_lazy_start_state(
    store=store,
    session_id="sid-1",
    state={"query": "x", "cached_results_ready": False, "cached_results": []},
)

# Optional common helper for action=full_document style list_all flows:
payload = await run_chunked_full_document_action(
    source="2601.03192.pdf",
    list_all_entries=lambda source_suffix: store_impl.list_all(
        "knowledge_chunks",
        source_filter=source_suffix,
    ),
    batch_size=15,
    batch_index=0,
)
```

### 3b. Fan-out plan helpers (master + child sessions)

```python
chunk_plan = build_chunk_plan_from_queue(state["shards_queue"])
selected_ids = normalize_selected_ids(chunk_id, chunk_ids)
progress = collect_chunk_progress(
    session_id=session_id,
    chunk_plan=chunk_plan,
    load_state=load_state,
    build_child_id=lambda sid, cid: f"{sid}:{cid}",
)
child_items = build_child_work_items(
    session_id=session_id,
    chunk_plan=chunk_plan,
    base_state=state,
    build_child_id=lambda sid, cid: f"{sid}:{cid}",
)
state_obj, scalar = extract_state_or_scalar_result(chunked_result)
summary_payload = build_summary_payload_from_state(
    state_obj or {},
    workflow_type="my_chunked",
)
# Or one-shot normalization:
summary_payload2 = build_summary_payload_from_chunked_result(
    chunked_result,
    workflow_type="my_chunked",
)
step_summary_payload = build_summary_payload_from_chunked_step_result(
    step_result,
    workflow_type="my_chunked",
    session_id=session_id,
    state_error_key="error",
)

fanout_payload = await run_chunked_fanout_shard(
    workflow_type="my_chunked",
    session_id=session_id,
    chunk_plan=chunk_plan,
    requested_chunk_ids=selected_ids,
    process_selected=lambda cid: run_one_selected_chunk(session_id, cid),
    load_state=load_state,
    build_child_id=lambda sid, cid: f"{sid}:{cid}",
)

single_chunk_result = await run_chunked_child_step(
    session_id=session_id,
    chunk_id="c1",
    load_state=load_state,
    save_state=save_state,
    run_step=run_one_shard,
    build_child_id=lambda sid, cid: f"{sid}:{cid}",
)

synthesize_payload = await run_chunked_fanout_synthesize(
    workflow_type="my_chunked",
    session_id=session_id,
    loaded_state=state,
    chunk_plan=chunk_plan,
    run_synthesize=run_synthesize_only,
    load_state=load_state,
    build_child_id=lambda sid, cid: f"{sid}:{cid}",
)
```

### 3. Parallel selected chunk ids

```python
from omni.langgraph.chunked import run_chunked_parallel_selected

results = await run_chunked_parallel_selected(
    ["c1", "c2", "c3"],
    process_selected=lambda chunk_id: run_one_selected_chunk(session_id, chunk_id),
    max_concurrent=3,
)
```

### 4. LangGraph node factory

```python
from langgraph.graph import StateGraph, END
from omni.langgraph.chunked import make_process_chunk_node, make_synthesize_node

async def process_one(state):
    # state["current_chunk"] is the chunk to process
    ...
    return {"summary": "..."}

workflow = StateGraph(MyState)
workflow.add_node("process_chunk", make_process_chunk_node(process_one, queue_key="shards_queue"))
workflow.add_node("synthesize", make_synthesize_node(my_synthesize_fn))
# Add edges: ... -> process_chunk -> (process_chunk | synthesize) -> END
```

## State shape

- **queue** (or custom `queue_key`): list of chunk dicts, e.g. `{"name", "targets", "description"}`.
- **accumulated** (or custom key): list of results from each chunk.
- **current_chunk** / **current_shard**: the chunk being processed (set by runner/node).
- Persistence uses shared `WorkflowStateStore` (checkpoint-backed) by `workflow_type` and `session_id`.

## Who uses it

- **Researcher**: can use `normalize_chunks` for shard normalization and `run_chunked_step` for action=start|shard|synthesize (with `queue_key="shards_queue"`).
- **Knowledge recall**: can use the same step pattern for batch-by-batch long doc read.
- Any new skill that needs stable, bounded chunking for LLM or tool loops can import from `omni.langgraph.chunked`.
