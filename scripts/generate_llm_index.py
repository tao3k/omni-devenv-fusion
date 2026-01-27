#!/usr/bin/env python3
"""
scripts/generate_llm_index.py
Skill Index Generator for LLM Context.

Scans assets/skills/ and generates .cache/omni-skills-index.json.
This allows the Agent to "know what it knows" without reading every file.

Note: The runtime system now uses LanceDB (.cache/omni-vector/).
This index is for LLM context purposes only.

Standard Structure:
- SKILL.md: Core definition + YAML Frontmatter (metadata)
- README.md: User guide
- scripts/*.py: Command implementations
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# Add packages to path for imports
_PRJ_ROOT = Path(__file__).parent.parent
_foundation_src = _PRJ_ROOT / "packages/python/foundation/src"
if str(_foundation_src) not in sys.path:
    sys.path.insert(0, str(_foundation_src))

from omni.foundation.config.skills import SKILLS_DIR


def parse_skill_md_frontmatter(skill_path: Path) -> dict[str, Any]:
    """Parse YAML frontmatter from SKILL.md."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return {
            "name": skill_path.name,
            "description": "Legacy skill (no SKILL.md)",
            "version": "0.0.0",
            "routing_keywords": [],
            "intents": [],
        }

    try:
        content = skill_md.read_text(encoding="utf-8")
        frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if frontmatter_match:
            frontmatter = frontmatter_match.group(1)
            data: dict[str, Any] = {}
            for line in frontmatter.split("\n"):
                line = line.strip()
                if ":" in line and not line.startswith("#"):
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    if value.startswith("[") and value.endswith("]"):
                        items = re.findall(r'"([^"]*)"', value)
                        data[key] = items
                    elif value.startswith("["):
                        data[key] = []
                    else:
                        data[key] = value
            return {
                "name": data.get("name", skill_path.name),
                "description": data.get("description", ""),
                "version": data.get("version", "1.0.0"),
                "routing_keywords": data.get("routing_keywords", []),
                "intents": data.get("intents", []),
                "authors": data.get("authors", []),
            }
    except Exception as e:
        print(f"  ⚠️ Error reading {skill_md}: {e}")

    return {
        "name": skill_path.name,
        "description": "Error parsing SKILL.md",
        "version": "0.0.0",
        "routing_keywords": [],
        "intents": [],
    }


def scan_tools_in_scripts(skill_path: Path) -> list[dict[str, Any]]:
    """Scan scripts/*.py for tool definitions."""
    tools: list[dict[str, Any]] = []
    scripts_dir = skill_path / "scripts"

    if not scripts_dir.exists():
        return tools

    for script_file in scripts_dir.glob("*.py"):
        if script_file.name.startswith("_"):
            continue
        try:
            content = script_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            current_func: str | None = None
            docstring: list[str] = []

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("def "):
                    if current_func and docstring:
                        tools.append(
                            {
                                "name": current_func,
                                "description": " ".join(docstring).strip()[:200],
                            }
                        )
                    current_func = stripped.split("(")[0].replace("def ", "")
                    docstring = []
                elif current_func and stripped.startswith('"""'):
                    docstring.append(stripped.replace('"""', ""))
                elif current_func and docstring:
                    if stripped and not stripped.startswith("#"):
                        docstring.append(stripped)

            if current_func and docstring:
                tools.append(
                    {"name": current_func, "description": " ".join(docstring).strip()[:200]}
                )
        except Exception as e:
            print(f"  ⚠️ Error reading script {script_file}: {e}")

    return tools


def scan_skills() -> list[dict[str, Any]]:
    """Scan all skills and build index."""
    skill_index: list[dict[str, Any]] = []

    if not SKILLS_DIR.exists():
        print(f"❌ Skills directory not found: {SKILLS_DIR}")
        return []

    print(f"🔍 Scanning skills in {SKILLS_DIR}...")

    for item in SKILLS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith("_"):
            metadata = parse_skill_md_frontmatter(item)
            entry: dict[str, Any] = {
                "name": metadata.get("name", item.name),
                "description": metadata.get("description", ""),
                "version": metadata.get("version", "1.0.0"),
                "path": str(item),
                "tools": scan_tools_in_scripts(item),
                "routing_keywords": metadata.get("routing_keywords", []),
                "intents": metadata.get("intents", []),
                "authors": metadata.get("authors", []),
            }

            has_skill_md = (item / "SKILL.md").exists()
            has_readme = (item / "README.md").exists()
            has_guide = (item / "guide.md").exists()
            has_prompts = (item / "prompts.md").exists()
            has_tests = (item / "tests").exists()

            entry["docs_available"] = {
                "skill_md": has_skill_md,
                "readme": has_readme,
                "guide": has_guide,
                "prompts": has_prompts,
                "tests": has_tests,
            }

            compliance: list[str] = []
            if has_skill_md:
                compliance.append("SKILL.md")
            if has_readme:
                compliance.append("README.md")
            if has_guide:
                compliance.append("guide.md")
            if has_prompts:
                compliance.append("prompts.md")
            if entry["tools"]:
                compliance.append("scripts")
            if has_tests:
                compliance.append("tests")

            entry["oss_compliant"] = has_skill_md and entry["tools"] and (has_readme or has_guide)
            entry["compliance_details"] = compliance

            skill_index.append(entry)
            status = "✅" if entry["oss_compliant"] else "⚠️"
            print(
                f"  {status} Found: {entry['name']} (v{entry['version']}) - {', '.join(compliance) if compliance else 'incomplete'}"
            )

    return skill_index


def generate_system_prompt_snippet(index: list[dict[str, Any]]) -> str:
    """Generate a compact XML snippet for insertion into system_context.xml."""
    lines = ["<available_skills>"]
    for skill in sorted(index, key=lambda x: x["name"]):
        lines.append(f'  <skill name="{skill["name"]}" version="{skill["version"]}">')
        lines.append(f"    {skill['description']}")
        if skill["tools"]:
            tool_names = [t["name"] for t in skill["tools"][:5]]
            lines.append(
                f"    Commands: {', '.join(tool_names)}{'...' if len(skill['tools']) > 5 else ''}"
            )
        lines.append("  </skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)


def main():
    """Main entry point."""
    index = scan_skills()

    if not index:
        print("No skills found.")
        return

    output_file = _PRJ_ROOT / ".cache" / "omni-skills-index.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"\n💾 Generated index at {output_file}")

    print("\n" + "=" * 60)
    print("📋 XML Snippet for system_context.xml:")
    print("=" * 60)
    snippet = generate_system_prompt_snippet(index)
    print(snippet)
    print("=" * 60)

    compliant = sum(1 for s in index if s["oss_compliant"])
    print(f"\n📊 Summary: {len(index)} skills scanned, {compliant} compliant")


if __name__ == "__main__":
    main()
