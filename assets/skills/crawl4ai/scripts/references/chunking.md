# Chunk Extraction

## Overview

Extract specific sections from markdown documents by line numbers. Enables lazy loading and token-efficient processing.

## API Reference

### `extract_chunk(markdown_text, line_start, line_end=None)`

Extract content between line numbers (inclusive).

**Parameters:**

- `markdown_text` (str): Full markdown content
- `line_start` (int): Starting line index (0-based)
- `line_end` (int, optional): Ending line index. Defaults to last line.

**Returns:** `str` - Extracted content

**Example:**

```python
from engine import extract_chunk

content = "# Heading\n\nSome content\n\n## Section 2"
chunk = extract_chunk(content, line_start=0, line_end=2)
# Returns: "# Heading\n\nSome content"
```

### `extract_skeleton(markdown_text, content_handle=None)`

Extract document structure without full content.

**Parameters:**

- `markdown_text` (str): Markdown to analyze
- `content_handle` (str, optional): Reference for lazy loading

**Returns:** `dict` with keys:

- `skeleton`: List of section metadata
- `stats`: Document statistics
- `content_handle`: Reference identifier

**Example:**

```python
from engine import extract_skeleton

result = extract_skeleton(long_markdown)
sections = result["skeleton"]
stats = result["stats"]
# sections[0] = {
#   "index": 0,
#   "level": 1,
#   "title": "Introduction",
#   "line_start": 0,
#   "line_end": 45,
#   "approx_chars": 1500,
#   "approx_tokens": 375
# }
```

## Line Number Mapping

Sections are mapped by line numbers, not characters:

```markdown
Line 0: # Document Title
Line 1:
Line 2: Introduction text...
Line 3:
Line 4: ## Section One ◄── Header detected
Line 5: Content here...
Line 6:
Line 7: ## Section Two
```

## Token Estimation

Rough approximation: 4 characters per token

```python
section["approx_tokens"] = section["approx_chars"] // 4
```

## Lazy Loading Pattern

For very large documents, combine skeleton with lazy extraction:

```python
# Step 1: Get skeleton (fast, lightweight)
skeleton = extract_skeleton(markdown)["skeleton"]

# Step 2: LLM decides relevant sections
relevant_indices = [3, 4, 5, 6]

# Step 3: Extract only needed sections
for idx in relevant_indices:
    section = skeleton[idx]
    content = extract_chunk(
        markdown,
        section["line_start"],
        section["line_end"]
    )
    process(content)
```

## Chunk Plan Format

Used by smart action to define extraction:

```json
{
  "chunks": [
    {
      "chunk_id": 0,
      "section_indices": [0, 1, 2],
      "reason": "Introduction and setup"
    },
    {
      "chunk_id": 1,
      "section_indices": [5, 6],
      "reason": "API reference"
    }
  ]
}
```

## Multi-Section Chunks

Combine multiple sections into one chunk:

```python
# Extract sections 2-5 as single chunk
line_start = skeleton[2]["line_start"]
line_end = skeleton[5]["line_end"]
combined = extract_chunk(content, line_start, line_end)
```
