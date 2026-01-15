#!/usr/bin/env python3
"""
scripts/generate_llm_index.py
Omni-Dev 1.0: Skill Index Generator for LLM Context.

Scans assets/skills/ and generates docs/llm/skill_index.json.
This allows the Agent to "know what it knows" without reading every file.

OSS 1.0 Standard Structure:
- SKILL.md: Core definition + YAML Frontmatter (metadata)
- README.md: User guide
- prompts.md: Persona definitions
- scripts/*.py: Command implementations
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional


SKILLS_DIR = Path("assets/skills")
OUTPUT_FILE = SKILLS_DIR / "skill_index.json"


def parse_skill_md_frontmatter(skill_path: Path) -> Dict[str, Any]:
    """Parse YAML frontmatter from SKILL.md."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        # Fallback for legacy skills without SKILL.md
        return {
            "name": skill_path.name,
            "description": "Legacy skill (no SKILL.md)",
            "version": "0.0.0",
            "routing_keywords": [],
            "intents": [],
        }

    try:
        with open(skill_md, "r") as f:
            content = f.read()

        # Parse YAML frontmatter between --- markers
        frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if frontmatter_match:
            frontmatter = frontmatter_match.group(1)
            data = {}

            # Parse simple YAML key: value pairs
            for line in frontmatter.split("\n"):
                line = line.strip()
                if ":" in line and not line.startswith("#"):
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    # Handle arrays
                    if value.startswith("[") and value.endswith("]"):
                        # Parse array
                        items = re.findall(r'"([^"]*)"', value)
                        data[key] = items
                    elif value.startswith("["):
                        # Multi-line array
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


def scan_tools_in_scripts(skill_path: Path) -> List[Dict[str, Any]]:
    """Scan scripts/*.py for tool definitions."""
    tools = []
    scripts_dir = skill_path / "scripts"

    if not scripts_dir.exists():
        return tools

    for script_file in scripts_dir.glob("*.py"):
        if script_file.name.startswith("_"):
            continue
        try:
            with open(script_file, "r") as f:
                content = f.read()
                # Look for function definitions with docstrings
                # Simple pattern: def command_xxx
                lines = content.split("\n")
                current_func = None
                docstring = []

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

                # Don't forget the last function
                if current_func and docstring:
                    tools.append(
                        {"name": current_func, "description": " ".join(docstring).strip()[:200]}
                    )
        except Exception as e:
            print(f"  ⚠️ Error reading script {script_file}: {e}")

    return tools


def scan_skills() -> List[Dict[str, Any]]:
    """Scan all skills and build index."""
    skill_index = []

    if not SKILLS_DIR.exists():
        print(f"❌ Skills directory not found: {SKILLS_DIR}")
        return []

    print(f"🔍 Scanning skills in {SKILLS_DIR}...")

    for item in SKILLS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith("_"):
            metadata = parse_skill_md_frontmatter(item)

            # Extract high-level metadata for LLM context
            entry = {
                "name": metadata.get("name", item.name),
                "description": metadata.get("description", ""),
                "version": metadata.get("version", "1.0.0"),
                "path": str(item),
                "tools": scan_tools_in_scripts(item),
                "routing_keywords": metadata.get("routing_keywords", []),
                "intents": metadata.get("intents", []),
                "authors": metadata.get("authors", []),
            }

            # Check for standard OSS 1.0 files
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

            # Check OSS 1.0 compliance
            # Required: SKILL.md + (README.md or guide.md) + scripts/
            compliance = []
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

            # OSS 1.0 compliant: SKILL.md + at least one guide + scripts/
            entry["oss_compliant"] = has_skill_md and entry["tools"] and (has_readme or has_guide)
            entry["compliance_details"] = compliance

            skill_index.append(entry)
            status = "✅" if entry["oss_compliant"] else "⚠️"
            print(
                f"  {status} Found: {entry['name']} (v{entry['version']}) - {', '.join(compliance) if compliance else 'incomplete'}"
            )

    return skill_index


def generate_system_prompt_snippet(index: List[Dict[str, Any]]) -> str:
    """Generates a compact XML snippet for insertion into system_context.xml"""
    lines = ["<available_skills>"]
    for skill in sorted(index, key=lambda x: x["name"]):
        lines.append(f'  <skill name="{skill["name"]}" version="{skill["version"]}">')
        lines.append(f"    {skill['description']}")
        if skill["tools"]:
            tool_names = [t["name"] for t in skill["tools"][:5]]
            lines.append(
                f"    Commands: {', '.join(tool_names)}{'...' if len(skill['tools']) > 5 else ''}"
            )
        lines.append(f"  </skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)


def main():
    index = scan_skills()

    if not index:
        print("No skills found.")
        return

    # 1. Write JSON Index (Machine Readable)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(index, f, indent=2)
    print(f"\n💾 Generated index at {OUTPUT_FILE}")

    # 2. Output XML Snippet (for System Prompt)
    print("\n" + "=" * 60)
    print("📋 XML Snippet for system_context.xml:")
    print("=" * 60)
    snippet = generate_system_prompt_snippet(index)
    print(snippet)
    print("=" * 60)

    # Summary
    compliant = sum(1 for s in index if s["oss_compliant"])
    print(f"\n📊 Summary: {len(index)} skills scanned, {compliant} OSS 1.0 compliant")


if __name__ == "__main__":
    main()
