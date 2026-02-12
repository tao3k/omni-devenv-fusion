"""Pytest configuration for knowledge skill tests.

Imports fixtures from omni.test_kit.fixtures.rag to make them available
for pytest test discovery.
"""

import sys
from pathlib import Path

# Add skill scripts to path for imports
skill_scripts = Path(__file__).parents[1] / "scripts"
if str(skill_scripts) not in sys.path:
    sys.path.insert(0, str(skill_scripts))

# Import fixtures from omni.test_kit.fixtures.rag
# These will be automatically discovered by pytest
from omni.test_kit.fixtures.rag import (
    mock_knowledge_graph_store,
    mock_llm_for_extraction,
    mock_llm_empty_response,
    mock_llm_invalid_json,
)
