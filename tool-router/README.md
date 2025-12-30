# Tool Router Practice

This folder holds a Claude tool-router practice set plus a small driver script. It mirrors the cookbook pattern where the router is asked to choose a tool ID, justify the pick, and emit a structured JSON decision.

## JSONL schema (`data/examples/nix.edit.jsonl`)

Each line is a JSON object with the following fields:

| Field | Description | Maps to cookbook router examples |
| --- | --- | --- |
| `id` | Unique tool identifier to select. | Tool name/ID exposed to the router. |
| `intent` | One-line task summary the router should solve. | Equivalent to the user's task description the router reads. |
| `syntax_focus` | Key syntax or APIs that must be present. | Guidance for the router's tool definitions, similar to cookbook tool capabilities. |
| `do_not` | Explicit anti-patterns the tool must avoid. | Negative constraints in router tool cards. |
| `allowed_edits` | Positive permissions/examples of valid edits. | What the tool is allowed to do, mirroring cookbook “capabilities” lists. |
| `checks` | Required commands/tests to run after edits. | Maps to cookbook “post-call checks” bullets. |
| `notes` | Additional clarifications or edge cases. | Extra nuance in the tool card description. |

Some entries add `before`/`after`/`example` snippets to showcase the intended change; these act like the cookbook “usage examples” that help the router disambiguate similar tools.

## Running the router example

The `run_router_example.py` script loads `data/examples/nix.edit.jsonl`, builds tool cards from the schema above, and asks the model to pick the best tool for each task—just like the Claude cookbooks router chapter.

```bash
python tool-router/run_router_example.py \
  --model claude-3-5-sonnet-20240620 \
  --dataset tool-router/data/examples/nix.edit.jsonl
```

The script logs structured routing decisions (JSON with `chosen_tool`, `confidence`, and `reasoning`) and prints an accuracy summary over the sample set so you can practice routing locally.

### Environment

- `ANTHROPIC_API_KEY` must be set.
- Optional: `ANTHROPIC_BASE_URL` to point at an Anthropic-compatible endpoint.

### What the script does

1. Reads the JSONL dataset and turns each row into a tool card mirroring the cookbook router definitions (capabilities, “avoid” clauses, and example snippets).
2. Builds a routing prompt that lists all tool cards and instructs the model to reply with JSON: `{\"tool_id\": \"...\", \"confidence\": 0-1, \"reasoning\": \"...\"}`.
3. Calls the model for each example, logs the response, and compares `tool_id` to the row’s `id` to compute simple accuracy.
4. Prints per-item routing logs plus an aggregate score.

Use this to rehearse the orchestrator/router pattern before wiring it into the MCP stack.
