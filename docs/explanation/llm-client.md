# LLM Client

> Unified LLM inference client for Omni-Dev-Fusion

## Overview

The `InferenceClient` provides a unified interface for calling LLM APIs (Anthropic/MiniMax) with tool support. It handles authentication, request formatting, response parsing, and tool call extraction.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     InferenceClient                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐     ┌─────────────────┐               │
│  │  Configuration  │────▶│  API Client     │               │
│  │  (settings)│     │  (Anthropic)    │               │
│  └─────────────────┘     └────────┬────────┘               │
│                                   │                         │
│                                   ▼                         │
│  ┌─────────────────┐     ┌─────────────────┐               │
│  │  Tool Parser    │◀────│  Response       │               │
│  │  (Text + API)   │     │  Handler        │               │
│  └────────┬────────┘     └─────────────────┘               │
│           │                                                   │
│           ▼                                                   │
│  ┌─────────────────┐                                         │
│  │  Result         │                                         │
│  │  {content,      │                                         │
│  │   tool_calls,   │                                         │
│  │   usage}        │                                         │
│  └─────────────────┘                                         │
└─────────────────────────────────────────────────────────────┘
```

## Files

| File                                                                    | Description                |
| ----------------------------------------------------------------------- | -------------------------- |
| `packages/python/foundation/src/omni/foundation/services/llm/client.py` | Main client implementation |
| `packages/python/foundation/src/omni/foundation/api/api_key.py`         | API key management         |
| `packages/python/foundation/src/omni/foundation/config/settings.py`     | Settings configuration     |

## Key Components

### InferenceClient Class

```python
class InferenceClient:
    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        timeout: int = None,
        max_tokens: int = None,
    ):
        """Initialize InferenceClient."""
        self.api_key = api_key or get_anthropic_api_key()
        self.base_url = base_url or get_setting("inference.base_url")
        self.model = model or get_setting("inference.model")
        self.timeout = timeout or get_setting("inference.timeout")
        self.max_tokens = max_tokens or get_setting("inference.max_tokens")
        self.client = AsyncAnthropic(api_key=self.api_key, base_url=self.base_url)
```

### Complete Method

```python
async def complete(
    self,
    system_prompt: str,
    user_query: str,
    model: str = None,
    max_tokens: int = None,
    timeout: int = None,
    messages: list[dict] = None,
    tools: list[dict] = None,
) -> dict[str, Any]:
    """Make a non-streaming LLM call with optional tool support."""
    # Build API request
    api_kwargs = {
        "model": actual_model,
        "max_tokens": actual_max_tokens,
        "system": system_prompt,
        "messages": message_list,
    }

    if tools:
        api_kwargs["tools"] = tools

    # Call API
    response = await self.client.messages.create(**api_kwargs)

    # Parse response
    content = ""
    tool_calls = []

    for block in response.content:
        if block.type == "text":
            content += block.text
        elif block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
            content += f"[TOOL_CALL: {block.name}]\n"

    return {
        "success": True,
        "content": content,
        "tool_calls": tool_calls,
        "model": actual_model,
        "usage": {...},
        "error": "",
    }
```

## Tool Call Parsing

### Primary: API Tool Use Block

The client first extracts tool calls from the API's native `tool_use` blocks:

```python
for block in response.content:
    if block.type == "tool_use":
        tool_calls.append({
            "id": block.id,
            "name": block.name,
            "input": block.input,
        })
```

### Fallback: Text Pattern Parsing

If no native tool calls are found, the client parses `[TOOL_CALL:...]` patterns from text:

```python
# Pattern: [TOOL_CALL: filesystem.read_files]
pattern = r"\[TOOL_CALL:\s*([^\]]+)\]"
matches = re.findall(pattern, content_for_parsing)

for tool_call_match in matches:
    tool_name = tool_call_match.strip()
    tool_input = {}

    # Method 1: Full JSON format
    # [TOOL_CALL: name]({"paths": ["a", "b"], ...})
    json_parens_pattern = rf"\[TOOL_CALL:\s*{re.escape(tool_name)}\]\s*\(\s*(\{{[^}}]*\}})\s*\)"
    json_match = re.search(json_parens_pattern, content_for_parsing)
    if json_match:
        args_json = json_match.group(1)
        tool_input = json.loads(args_json)

    # Method 2: Shorthand array format
    # [TOOL_CALL: name](paths=["a", "b"])
    if not tool_input:
        shorthand_match = re.search(
            rf'\[TOOL_CALL:\s*{re.escape(tool_name)}\]\s*\(([^)]+)\)',
            content_for_parsing,
        )
        if shorthand_match:
            # Parse array format...

    # Method 3: Simple key=value format
    # [TOOL_CALL: name](path="file.md")
    if not tool_input:
        simple_match = re.search(
            rf"\[TOOL_CALL:\s*{re.escape(tool_name)}\]\s*\(([^)]+)\)",
            content_for_parsing,
        )
        # Parse key=value pairs...

    # Method 4: XML-like parameter tags
    # <parameter name="path">file.md</parameter>
    if not tool_input:
        param_pattern = r"<parameter\s+name=\"(\w+)\">([^<]+)</parameter>"
        params = re.findall(param_pattern, content_for_parsing)
        for k, v in params:
            tool_input[k] = v.strip()
```

## Configuration

### Settings (system: packages/conf/settings.yaml, user: $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml)

```yaml
inference:
  base_url: "https://api.anthropic.com"
  model: "claude-sonnet-4-20250514"
  timeout: 120
  max_tokens: 4096
  api_key_env: "ANTHROPIC_API_KEY"
```

### Environment Variables

| Variable            | Description                                 |
| ------------------- | ------------------------------------------- |
| `ANTHROPIC_API_KEY` | Anthropic API key                           |
| `MINIMAX_API_KEY`   | MiniMax API key (for alternative endpoints) |

## Issues & Improvements

### Current Issues

| Issue                   | Severity | Description                    | Impact                      |
| ----------------------- | -------- | ------------------------------ | --------------------------- |
| Incomplete JSON parsing | High     | Some LLM outputs fail to parse | Tool calls silently dropped |
| Path extraction limited | Medium   | Only `.md` and basic patterns  | Missing file targets        |
| No streaming support    | Medium   | `complete()` is blocking       | Poor UX for long responses  |
| No retry logic          | Low      | Single attempt only            | Fragile to transient errors |
| MiniMax compatibility   | Low      | Basic auth handling            | Potential edge cases        |

### Detailed Issue Analysis

#### 1. Incomplete JSON Parsing

```python
# LLM output that fails:
[TOOL_CALL: filesystem.read_files]({"paths": ["file1.md", "file2.md"])

# Current regex might not handle nested structures
# Solution: Use proper JSON parser with error recovery
```

#### 2. Path Extraction Limited

```python
# Current fallback only handles:
- `"file.md"` in backticks
- Quoted `.md` files
- Specific file extensions

# Missing:
- Relative paths: `../src/main.py`
- Glob patterns: `src/**/*.py`
- Directory paths
```

### Potential Improvements

1. **Robust JSON Parsing**
   - Use `json.JSONDecoder` with error recovery
   - Handle partial/invalid JSON gracefully
   - Log parsing failures for debugging

2. **Enhanced Path Detection**
   - Support glob patterns
   - Use `pathlib` for path validation
   - Integrate with `skill.discover` for path discovery

3. **Streaming Support**
   - Add `stream_complete()` method
   - Yield partial results
   - Support real-time tool call streaming

4. **Retry Logic**
   - Exponential backoff
   - Circuit breaker pattern
   - Dead letter queue for failed calls

5. **Multi-Provider Support**
   - Abstract provider interface
   - OpenAI, Anthropic, MiniMax, local LLMs
   - Unified response format

### Research Directions

- **Function Calling** (OpenAI 2023) - Structured function calling APIs
- **Tool Use** (Anthropic 2024) - Native tool use in Claude
- **vLLM** - High-throughput LLM serving
- **TGI** (Text Generation Inference) - HuggingFace's LLM server
- **LiteLLM** - Unified interface for multiple LLM providers

## Related Documentation

- [ReAct Workflow](react-workflow.md) - Tool-augmented reasoning pattern
- [Inference Settings Reference](../reference/inference-settings.md) - Configuration options
- [Intent Protocol](../../assets/prompts/routing/intent_protocol.md) - System prompt for LLM
