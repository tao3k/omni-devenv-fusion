# Scripts Directory

This directory contains utility scripts for the Omni-Dev Fusion project.

## Available Scripts

| Script                         | Purpose                              |
| ------------------------------ | ------------------------------------ |
| `generate_llm_index.py`        | Generate skill index for LLM context |
| `verify_skill_descriptions.py` | Verify skill command descriptions    |
| `verify_system.py`             | End-to-end smoke test for kernel     |

## Running Scripts

All scripts should be run from the project root:

```bash
# Using uv (recommended)
uv run python scripts/script_name.py

# Or directly with python
python scripts/script_name.py
```

## Database Commands

Database operations are now available via the `omni db` CLI command:

```bash
# List all databases
omni db list

# Query knowledge base
omni db query "error handling"

# Show database statistics
omni db stats

# Count records in table
omni db count <table_name>
```
