# Writer Skill

Writing quality enforcement through systematic checks against project standards.

## Core Philosophy

**"Write once, write right"** - Writing tools catch issues before they enter the codebase, ensuring documentation quality is maintained at the same level as code quality.

## Tools

### lint_writing_style

Check text against Module 02 (Rosenberg Mechanics) style guide:

- Clutter words (utilize -> use, facilitate -> help)
- Passive voice detection
- Weak language (basically, essentially)

### check_markdown_structure

Validate markdown against Module 03 (Structure & AI):

- H1 uniqueness (only one # at top)
- Hierarchy jumping (H2 -> H4 not allowed)
- Code block labels (Input/Output style)
- Proper spacing

### polish_text

Polish text using all writing guidelines:

- Runs lint_writing_style + check_markdown_structure
- Auto-fixes style issues where possible
- Returns polished text with violation summary

### load_writing_memory

Load writing guidelines into LLM context:

- Reads all files from agent/writing-style/
- Injects into context for the session
- Call exactly once at start of writing task

### run_vale_check

Run Vale CLI on markdown files:

- External linter integration
- Returns JSON results with violations
- Requires Vale CLI installed

## Usage

```python
# Check writing style
await lint_writing_style(text="Your content here")

# Check markdown structure
await check_markdown_structure(text="# Heading\n\n## Subheading")

# Polish entire document
await polish_text(text="Raw content...")

# Load guidelines
await load_writing_memory()

# Lint markdown file
await run_vale_check(file_path="docs/guide.md")
```

## Integration

Writer skill is auto-loaded by the orchestrator when documentation changes are detected. All write operations through the coder MCP server automatically check writing quality.
