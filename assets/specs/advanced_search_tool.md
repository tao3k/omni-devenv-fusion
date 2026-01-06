# Spec: advanced_search_tool

> **Status**: Approved
> **Complexity**: L3
> **Owner**: @omni-orchestrator

## 1. Context & Goal (Why)

_Creating a high-performance code search capability for the MCP Orchestrator that leverages ripgrep for fast, parallel code searching across the project codebase._

- **Goal**: Enable developers to quickly search through codebase files using regex patterns with rich context output, integrated directly into the MCP tool ecosystem.
- **User Story**: As a developer using the MCP tools, I want to search for code patterns across the project with line numbers and match context, so I can quickly understand code usage, find bugs, and navigate the codebase without leaving my IDE.
- **Why ripgrep**: ripgrep is a line-oriented search tool that recursively searches the current directory for a regex pattern. It's 10-100x faster than grep and supports PCRE2 regex, making it ideal for code search scenarios.

## 2. Architecture & Interface (What)

_Defines the advanced_search_tool module contract that integrates with the MCP Orchestrator using ripgrep as the search engine._

### 2.1 File Changes

| File                                           | Action   | Purpose                                                              |
| ---------------------------------------------- | -------- | -------------------------------------------------------------------- |
| `mcp-server/advanced_search.py`                | Created  | Main module containing the `search_project_code` tool implementation |
| `mcp-server/orchestrator.py`                   | Modified | Register `search_project_code` tool with the MCP server              |
| `mcp-server/tests/test_advanced_search.py`     | Created  | Unit tests for the search tool                                       |
| `tests/integration/test_search_integration.py` | Created  | Integration tests verifying end-to-end functionality                 |

### 2.2 Data Structures / Schema

```python
from typing import TypedDict
from dataclasses import dataclass


class SearchResult(TypedDict):
    """Represents a single search match result."""
    file: str          # Path to the file containing the match
    line_number: int   # 1-indexed line number of the match
    line_content: str  # The actual line content
    match: str         # The matching portion of the line


class SearchStats(TypedDict):
    """Statistics about the search operation."""
    files_searched: int
    total_matches: int
    elapsed_ms: float


class SearchResponse(TypedDict):
    """Complete response from the search tool."""
    results: list[SearchResult]
    stats: SearchStats
    error: str | None  # None if successful, error message if failed


@dataclass
class SearchConfig:
    """Configuration for search parameters."""
    pattern: str               # Required: regex pattern to search
    path: str = "."            # Optional: search directory (default: current)
    file_type: str | None = None   # Optional: filter by file extension (e.g., "py", "nix")
    include_hidden: bool = False   # Optional: include hidden files/directories
    context_lines: int = 2     # Optional: lines of context around matches
    max_results: int = 1000    # Optional: maximum number of results to return
```

### 2.3 API Signatures (Pseudo-code)

```python
from typing import TypedDict
from pathlib import Path
from mcp.server.fastmcp import FastMCP


class SearchConfig(TypedDict, total=False):
    """Configuration for the search_project_code tool."""
    pattern: str              # Required regex pattern
    path: str                 # Search directory (default: ".")
    file_type: str | None     # File extension filter (e.g., "py")
    include_hidden: bool      # Include hidden files (default: False)


async def search_project_code(
    pattern: str,
    path: str = ".",
    file_type: str | None = None,
    include_hidden: bool = False
) -> SearchResponse:
    """Search for a regex pattern in files using ripgrep.

    Args:
        pattern: Required regex pattern to search for.
        path: Search directory (defaults to current directory).
        file_type: Optional file extension filter (e.g., "py" for Python files).
        include_hidden: Whether to search in hidden files/directories.

    Returns:
        SearchResponse containing results list, stats, and any error message.

    Raises:
        ValueError: If pattern is empty or invalid regex.
        RuntimeError: If ripgrep is not installed or search fails.
    """
    # Validate pattern is not empty
    if not pattern or not pattern.strip():
        raise ValueError("Pattern cannot be empty")

    # Build ripgrep command with proper escaping
    cmd = _build_ripgrep_command(pattern, path, file_type, include_hidden)

    # Execute command asynchronously
    stdout, stderr = await _execute_search(cmd, cwd=path)

    # Parse output into structured results
    results = _parse_ripgrep_output(stdout, context_lines=2)

    # Calculate stats
    stats = SearchStats(
        files_searched=_count_files_searched(results),
        total_matches=len(results),
        elapsed_ms=_measure_elapsed_ms()
    )

    return SearchResponse(results=results, stats=stats, error=None)


def register_tool(mcp: FastMCP) -> None:
    """Register the search_project_code tool with an MCP server instance."""
    @mcp.tool()
    async def search_project_code(
        pattern: str,
        path: str = ".",
        file_type: str | None = None,
        include_hidden: bool = False
    ) -> str:
        """Search for a regex pattern in code files.

        Uses ripgrep for high-performance parallel searching. Returns
        matches with line numbers and surrounding context.

        Args:
            pattern: The regex pattern to search for (required).
            path: Directory to search in (default: current directory).
            file_type: Filter by file extension, e.g., "py" or "nix".
            include_hidden: Include hidden files and directories.

        Returns:
            JSON string of SearchResponse with results and statistics.
        """
        response = await search_project_code(
            pattern=pattern,
            path=path,
            file_type=file_type,
            include_hidden=include_hidden
        )
        return _format_json_response(response)
```

## 3. Implementation Plan (How)

1. **[L3] Create `mcp-server/advanced_search.py`**:
   - Define `SearchResult`, `SearchStats`, `SearchResponse` TypedDict classes
   - Implement `SearchConfig` dataclass for parameter validation
   - Create `_build_ripgrep_command()` helper to construct ripgrep CLI arguments
   - Create `_execute_search()` helper using `asyncio.create_subprocess_exec()`
   - Create `_parse_ripgrep_output()` to convert ripgrep output to structured data
   - Implement main `search_project_code()` async function with full error handling
   - Add Google-style docstrings with type hints per `lang-python.md`

2. **[L3] Register tool in `mcp-server/orchestrator.py`**:
   - Import `search_project_code` from `advanced_search`
   - Add `@mcp.tool()` decorator function wrapper for registration
   - Ensure tool is discoverable in MCP tool list

3. **[L2] Create unit tests in `mcp-server/tests/test_advanced_search.py`**:
   - Test `_build_ripgrep_command()` command construction
   - Test `_parse_ripgrep_output()` parsing logic with sample ripgrep output
   - Test `SearchConfig` validation and defaults
   - Test error handling for invalid patterns and paths

4. **[L3] Create integration tests in `tests/integration/test_search_integration.py`**:
   - Test tool registration with MCP server
   - Test actual search against real project files
   - Test with various file types (`.py`, `.nix`, `.md`)
   - Test with hidden files and directories

## 4. Verification Plan

### 4.1 Unit Tests (L2)

| Test Case                       | Description                                       | Expected Result                 |
| ------------------------------- | ------------------------------------------------- | ------------------------------- |
| `test_build_ripgrep_command`    | Test command construction with various parameters | Correct CLI arguments generated |
| `test_parse_ripgrep_output`     | Test parsing of ripgrep output format             | Structured SearchResult list    |
| `test_search_config_defaults`   | Test SearchConfig default values                  | All defaults applied correctly  |
| `test_invalid_pattern_handling` | Test error handling for invalid regex             | ValueError raised with message  |
| `test_empty_path_handling`      | Test handling of non-existent paths               | RuntimeError with clear message |

### 4.2 Integration Tests (L3)

| Test Case                  | Description                        | Expected Result                   |
| -------------------------- | ---------------------------------- | --------------------------------- |
| `test_tool_registration`   | Verify tool is registered with MCP | Tool appears in tool list         |
| `test_search_python_files` | Search in .py files only           | Results filtered by extension     |
| `test_search_nix_files`    | Search in .nix files only          | Results filtered by extension     |
| `test_search_with_context` | Search with context lines          | Results include surrounding lines |
| `test_hidden_file_search`  | Search including hidden files      | Hidden files included in results  |

### 4.3 Acceptance Criteria

- [ ] `mcp-server/advanced_search.py` created with all TypedDict classes
- [ ] `search_project_code` tool registered in `orchestrator.py`
- [ ] All L2 unit tests pass (`pytest mcp-server/tests/test_advanced_search.py`)
- [ ] All L3 integration tests pass (`pytest tests/integration/test_search_integration.py`)
- [ ] Code follows `lang-python.md` standards (type hints, docstrings)
- [ ] Tool returns JSON-formatted response with results and stats
