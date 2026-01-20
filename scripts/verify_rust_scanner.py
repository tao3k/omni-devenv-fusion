#!/usr/bin/env python3
"""
Phase 62: Verify Rust Scanner via omni-core-rs Bindings

This script verifies that the Rust skills-scanner can correctly scan Python scripts
and return PyToolRecord objects with proper metadata using the new modular scanner:
- SkillScanner: Parses SKILL.md for metadata and routing keywords
- ScriptScanner: Scans scripts/ for @skill_command decorated functions
"""

import sys
from pathlib import Path
from collections import defaultdict

# Add agent source to path for imports
agent_src = Path(__file__).parent.parent / "packages/python/agent/src"
sys.path.insert(0, str(agent_src))

try:
    from omni_core_rs import scan_skill_tools
except ImportError as e:
    print(f"[!] Error: Could not import omni_core_rs. Did you run 'maturin develop'?")
    print(f"    Detail: {e}")
    sys.exit(1)


def get_directory_from_path(file_path: str, skill_name: str) -> str:
    """Extract directory name from file path relative to skill."""
    try:
        parts = file_path.split(f"{skill_name}/")
        if len(parts) > 1:
            return parts[1].split("/")[0]
        return "root"
    except:
        return "unknown"


def main():
    skills_dir = Path("assets/skills")
    if not skills_dir.exists():
        print(f"[!] Error: Skills directory not found at {skills_dir}")
        print("    Make sure you're running from the project root.")
        return

    print(f"[=] Scanning skills in {skills_dir} using Rust skills-scanner...")
    print("=" * 70)

    # 1. Show which directories will be scanned
    print("\n[>] Directories configured in settings.yaml skills.architecture:")
    scan_dirs = ["scripts/", "templates/", "references/", "assets/", "data/", "tests/"]
    for d in scan_dirs:
        print(f"      - {d}")
    print()

    # 2. Call Rust scanner (uses SkillScanner + ScriptScanner internally)
    try:
        tools = scan_skill_tools(str(skills_dir))
    except Exception as e:
        print(f"[!] Rust panic or error: {e}")
        import traceback

        traceback.print_exc()
        return

    print(f"[+] Total tools found: {len(tools)}")
    print()

    # 3. Check if skills directory has the expected structure
    print("[>] Skills directory structure check:")
    skills_checked = 0
    skills_with_dirs = defaultdict(list)
    for item in skills_dir.iterdir():
        if item.is_dir():
            skills_checked += 1
            for scan_dir in scan_dirs:
                check_path = item / scan_dir.rstrip("/")
                if check_path.exists():
                    # Count files
                    file_count = sum(1 for _ in check_path.rglob("*") if _.is_file())
                    skills_with_dirs[item.name].append((scan_dir.rstrip("/"), file_count))

    if skills_with_dirs:
        for skill, dirs in sorted(skills_with_dirs.items()):
            print(f"      {skill}/")
            for d, count in sorted(dirs):
                print(f"        └── {d}/ ({count} files)")
    else:
        print("      No skill subdirectories with scan targets found.")
    print(f"      (Checked {skills_checked} skill directories)")
    print()

    # 4. Group tools by skill and by directory
    tools_by_skill_dir = defaultdict(lambda: defaultdict(list))
    for tool in tools:
        dir_name = get_directory_from_path(tool.file_path, tool.skill_name)
        tools_by_skill_dir[tool.skill_name][dir_name].append(tool)

    # 5. Display results grouped by skill -> directory
    print("[>] Scan Results (by Skill -> Directory):")
    print("-" * 70)

    total_script_mode = 0
    total_with_docstring = 0

    for skill_name in sorted(tools_by_skill_dir.keys()):
        skill_data = tools_by_skill_dir[skill_name]
        print(f"\n  Skill: {skill_name}")
        print(f"  {'─' * 50}")

        # Show routing keywords from SKILL.md
        first_tool = list(skill_data.values())[0][0] if skill_data else None
        if first_tool and first_tool.keywords:
            # Extract unique keywords excluding tool name and skill name
            unique_keywords = set(first_tool.keywords) - {skill_name}
            kw_list = sorted(unique_keywords)[:5]
            if kw_list:
                print(f"  Routing Keywords: {', '.join(kw_list)}")
            print()

        for dir_name in sorted(skill_data.keys()):
            tools_in_dir = skill_data[dir_name]
            dir_display = f"{dir_name}/" if dir_name != "root" else "(root)"
            print(f"  [{dir_display}] {len(tools_in_dir)} tool(s)")

            for tool in tools_in_dir:
                if tool.execution_mode == "script":
                    total_script_mode += 1
                if tool.docstring:
                    total_with_docstring += 1

                # Format tool info
                name = tool.tool_name
                func = tool.function_name

                # Truncate description
                desc = tool.description
                if len(desc) > 40:
                    desc = desc[:40] + "..."

                # Get keywords for this tool (exclude skill name and tool name)
                tool_kw = set(tool.keywords) - {skill_name, tool.tool_name.split(".")[-1]}
                kw_str = f" [{', '.join(sorted(tool_kw))[:25]}...]" if tool_kw else ""

                print(f"    ├── {name}")
                print(f"    │   function: {func}")
                print(f"    │   file: {tool.file_path.split('/')[-1]}")
                print(f"    │   desc: {desc}{kw_str}")
                if tool.docstring:
                    doc_preview = tool.docstring[:50].replace("\n", " ")
                    print(f'    │   doc: "{doc_preview}..."')
                print()

    # 6. Summary statistics
    print("=" * 70)
    print("\n[i] Summary Statistics:")
    print(f"    - Total tools discovered:   {len(tools)}")
    print(f"    - Script mode tools:        {total_script_mode}")
    print(f"    - Tools with docstring:     {total_with_docstring}")
    print(f"    - Skills with tools:        {len(tools_by_skill_dir)}")

    # Directory breakdown
    all_dirs = defaultdict(int)
    for skill_data in tools_by_skill_dir.values():
        for dir_name in skill_data.keys():
            all_dirs[dir_name] += len(skill_data[dir_name])

    if all_dirs:
        print(f"\n[i] Tools by Directory:")
        for dir_name in sorted(all_dirs.keys()):
            count = all_dirs[dir_name]
            dir_display = f"{dir_name}/" if dir_name != "root" else "root"
            print(f"    - {dir_display:15} : {count} tools")

    # 7. Verification tests
    print("\n[=] Verification Tests")
    print("-" * 40)

    git_tools = [t for t in tools if t.skill_name == "git"]
    if git_tools:
        print(f"[PASS] Found {len(git_tools)} tool(s) in 'git' skill")
        for t in git_tools:
            dir_name = get_directory_from_path(t.file_path, "git")
            print(f"       - {t.tool_name} ({dir_name})")
    else:
        print("[INFO] No tools found in 'git' skill.")

    # 8. Attribute access test
    print("\n[=] PyToolRecord Attribute Test")
    print("-" * 40)
    if tools:
        first_tool = tools[0]
        attrs = [
            ("tool_name", str),
            ("description", str),
            ("skill_name", str),
            ("file_path", str),
            ("function_name", str),
            ("execution_mode", str),
            ("keywords", list),
            ("input_schema", str),
            ("docstring", str),
        ]

        all_passed = True
        for attr_name, expected_type in attrs:
            try:
                val = getattr(first_tool, attr_name)
                if isinstance(val, expected_type):
                    val_str = str(val)[:30]
                    print(f'  [PASS] {attr_name}: {expected_type.__name__} = "{val_str}..."')
                else:
                    print(f"  [FAIL] {attr_name}: expected {expected_type.__name__}")
                    all_passed = False
            except Exception as e:
                print(f"  [FAIL] {attr_name}: {e}")
                all_passed = False

        if all_passed:
            print("\n[+] All attributes accessible!")
    else:
        print("  [SKIP] No tools found.")

    print("\n" + "=" * 70)
    print("[*] Rust skills-scanner verification complete!")


if __name__ == "__main__":
    main()
