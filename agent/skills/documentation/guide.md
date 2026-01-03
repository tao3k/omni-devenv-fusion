# Skill: Documentation Management

## Overview

This skill handles the lifecycle of project documentation. It enforces the "Knowledge Harvest" workflow and ensures all docs follow the standard format.

## Capabilities

- **Create Doc**: `create_knowledge_entry` (Create standard .md files)
- **Update Index**: `rebuild_knowledge_index` (Update README tables)
- **Search**: `search_knowledge_base` (Find existing wisdom)

## Standards

1.  **Location**: All knowledge goes into `agent/knowledge/` or `agent/knowledge/harvested/`.
2.  **Naming**: `YYYYMMDD-category-title.md` (e.g., `20260102-debugging-nested-locks.md`).
3.  **Frontmatter**:

    ```markdown
    # Title

    > **Category**: ... | **Date**: ...
    ```

4.  **Categories**: `architecture`, `debugging`, `pattern`, `workflow`, `domain`.
