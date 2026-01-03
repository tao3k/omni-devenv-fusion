# Implementing the Harvester Module for Learning from Experience

**Category**: architecture
**Date**: 2026-01-02
**Harvested**: Automatically from development session

## Context

Phase 12 required building a learning capability for the Agentic OS that can automatically distill development experience into permanent knowledge cards. The system needed to harvest insights from development sessions and make them accessible for future work.

## Solution

Created the Harvester module with three key components: 1) Unified API key management in api_key.py supporting both ANTHROPIC_API_KEY and ANTHROPIC_AUTH_TOKEN from settings.json and environment variables, 2) Harvester capabilities with harvest_session_insight, list_harvested_knowledge, and get_scratchpad_summary tools, 3) Direct Anthropic API integration with MiniMax base_url support for compatibility. The system now automatically converts development experience into persistent knowledge cards.

## Key Takeaways

- Unified API key management provides flexibility by supporting multiple authentication methods (settings.json, environment variables) and key formats
- Using direct API calls with configurable base_url enables compatibility across different Anthropic-compatible services
- Learning systems require clear, dedicated tools for harvesting, listing, and summarizing knowledge to make the captured insights accessible
- Implementing a dedicated schema module helps organize the data structures for the new learning capabilities

## Pattern / Snippet

```architecture
from src.common.mcp_core.api_key import get_api_key

# Unified API key retrieval supporting multiple formats and sources
api_key = get_api_key(
    preferred_keys=['ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN'],
    sources=['settings', 'env']
)
```

## Related Files

- `src/agent/capabilities/harvester.py`
- `src/common/mcp_core/api_key.py`
- `src/agent/core/schema.py`
