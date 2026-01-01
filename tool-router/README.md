# Tool Router Practice

Claude tool-router practice with a driver script. Follows the cookbook pattern: router picks a tool ID, justifies the choice, and emits structured JSON.

## JSONL Schema (`data/examples/nix.edit.jsonl`)

Each line is a JSON object:

| Field           | Description               | Cookbook Mapping             |
| --------------- | ------------------------- | ---------------------------- |
| `id`            | Unique tool identifier.   | Tool name exposed to router. |
| `intent`        | One-line task summary.    | User's task description.     |
| `syntax_focus`  | Required syntax/APIs.     | Router tool capabilities.    |
| `do_not`        | Anti-patterns to avoid.   | Negative constraints.        |
| `allowed_edits` | Valid edit examples.      | "Capabilities" lists.        |
| `checks`        | Post-edit tests to run.   | "Post-call checks".          |
| `notes`         | Edge case clarifications. | Tool card nuances.           |

Entries may include `before`/`after`/`example` snippets—usage examples that help disambiguate similar tools.

## Run the Router

```bash
python tool-router/run_router_example.py \
  --model claude-3-5-sonnet-20240620 \
  --dataset tool-router/data/examples/nix.edit.jsonl
```

Logs structured decisions (`chosen_tool`, `confidence`, `reasoning`) and prints an accuracy summary.

### Environment

- `ANTHROPIC_API_KEY`: Required.
- `ANTHROPIC_BASE_URL`: Optional. Points to Anthropic-compatible endpoint.

### Script Actions

1. Read JSONL, build tool cards from schema (capabilities, avoid clauses, examples).
2. Build routing prompt, ask model for JSON: `{"tool_id": "...", "confidence": 0-1, "reasoning": "..."}`.
3. Call model for each example, compare `tool_id` to expected `id`, compute accuracy.
4. Print per-item logs and aggregate score.

Use this to rehearse the orchestrator/router pattern before integrating into MCP.
