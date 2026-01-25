#!/usr/bin/env python3
"""Generate skill_index.json for tests.

Usage:
    python scripts/generate_skill_index.py
"""

from pathlib import Path
import json


def main():
    try:
        from omni_core_rs import export_skill_index
    except ImportError:
        print("Warning: omni_core_rs not available")
        return

    skills_path = str(Path("assets/skills").resolve())
    output_path = str(Path(".cache/skill_index.json").resolve())

    # Ensure .cache directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        result = export_skill_index(skills_path, output_path)
        skills = json.loads(result)
        print(f"Generated skill_index.json with {len(skills)} skills")
    except Exception as e:
        print(f"Warning: Could not generate skill_index.json: {e}")


if __name__ == "__main__":
    main()
