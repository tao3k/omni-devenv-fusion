# Scripts Directory

This directory contains utility scripts for the Omni-Dev Fusion v2.0 project.

## Available Scripts

| Script                         | Purpose                                      |
| ------------------------------ | -------------------------------------------- |
| `verify_system.py`             | End-to-end smoke test for v2.0 kernel        |
| `verify_fixtures.py`           | Verify extension fixture system              |
| `verify_universal_skill.py`    | Verify zero-code skill architecture          |
| `verify_rust_scanner.py`       | Verify Rust skills-scanner bindings          |
| `benchmark_rust_core.py`       | Rust vs Python performance benchmarks        |
| `benchmark_sniffer.py`         | Neural Bridge benchmark (Rust vs Python git) |
| `generate_llm_index.py`        | Generate skill index for LLM context         |
| `verify_skill_descriptions.py` | Verify skill command descriptions            |

## Running Scripts

All scripts should be run from the project root:

```bash
# Using uv (recommended)
uv run python scripts/script_name.py

# Or directly with python
python scripts/script_name.py
```

## Script Development

When adding new scripts:

1. Use Python and follow project coding standards
2. Add `from __future__ import annotations` at the top
3. Use type hints and modern Python syntax
4. Import paths from `omni.foundation.config.skills` and `omni.foundation.config.dirs`
5. Add docstrings explaining purpose and usage
6. Make scripts executable if needed (`chmod +x`)
7. Document in this file if significant

## Path Conventions

Use SSOT utilities instead of hardcoded paths:

```python
from omni.foundation.config.skills import SKILLS_DIR
from omni.foundation.config.dirs import PRJ_DATA, PRJ_CACHE
```
