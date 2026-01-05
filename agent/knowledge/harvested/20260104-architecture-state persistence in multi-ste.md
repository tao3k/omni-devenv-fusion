# State Persistence in Multi-Step ReAct Loops

**Category**: architecture
**Date**: 2026-01-04
**Harvested**: Automatically from development session

## Context

During Phase 19 testing of delegate_mission, discovered critical state loss issue where each delegate_mission call creates a new Orchestrator instance, preventing agents from resuming multi-step tasks across calls. Additionally found XML tool format parsing issues requiring DOTALL regex flag.

## Solution

Enhanced tool call parsing in base.py to support XML/MCP format with proper regex parsing using DOTALL flag. Fixed daemon thread shutdown handling in bootstrap.py. Recommended providing complete context in single delegate_mission calls and considering stateful Orchestrator singleton for session persistence.

## Key Takeaways

- Multi-step ReAct tasks require complete context in single delegate_mission call to avoid state loss
- Stateful Orchestrator singleton pattern needed for session persistence across multiple calls
- XML/MCP tool format parsing requires regex DOTALL flag to handle multi-line content properly
- Proper daemon thread shutdown handling essential for graceful application termination

## Pattern / Snippet

```architecture
def _parse_tool_call(self, response_text: str) -> Optional[Dict]:
    """Enhanced parser supporting XML/MCP format with DOTALL regex"""
    # Support multiple tool call formats
    patterns = [
        r'<invoke>\s*<(\w+)>\s*<([^>]+)>([^`]*?)</\2>\s*</\1>\s*</invoke>',
        r'TOOL:\s*(\w+)\s*\(([^)]+)\)',
        r'\[(\w+)\s*([^\]]+)\]'
    ]

    for pattern in patterns:
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            return self._extract_tool_params(match)
```

## Related Files

- `packages/python/agent/src/agent/core/agents/base.py`
- `packages/python/agent/src/agent/core/bootstrap.py`
