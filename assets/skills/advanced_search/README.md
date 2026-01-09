# Advanced Search Skill

High-performance code search using ripgrep with structured results.

## Core Philosophy

**"Find anything, fast"** - Uses ripgrep for parallel, high-performance searching with structured output.

## Tools

### search_project_code

Search for regex patterns in code files using ripgrep.

Features:

- Parallel searching across multiple files
- Context lines around matches
- File type filtering
- Hidden file inclusion toggle
- Structured JSON output with statistics

## Usage

```python
# Basic search
await search_project_code(pattern="def test_")

# With filters
await search_project_code(
    pattern="async def.*",
    path="src/",
    file_type="py",
    include_hidden=False,
    context_lines=3
)

# Get structured results
response = await search_project_code(
    pattern="class.*MCP",
    file_type="py"
)
# response.stats.files_searched
# response.results[0].line_content
```

## Performance

- Uses ripgrep (rg) - native speed
- Parallel file scanning
- Statistics returned for optimization
- Typical search < 100ms for 10k files

## Output Format

Results include:

- `file`: Relative path to match
- `line_number`: 1-indexed line number
- `line_content`: Full line content
- `match`: The matching portion

Statistics include:

- `files_searched`: Number of unique files
- `total_matches`: Total match count
- `elapsed_ms`: Search time in milliseconds
