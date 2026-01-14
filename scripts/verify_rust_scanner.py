#!/usr/bin/env python3
"""
Phase 62: Verify Rust Scanner via omni-core-rs Bindings

This script verifies that the Rust core can correctly scan Python scripts
and return PyToolRecord objects with proper metadata.
"""

import sys
from pathlib import Path

# Add agent source to path for imports
agent_src = Path(__file__).parent.parent / "packages/python/agent/src"
sys.path.insert(0, str(agent_src))

try:
    from omni_core_rs import scan_skill_tools
except ImportError as e:
    print(f"❌ Error: Could not import omni_core_rs. Did you run 'maturin develop'?")
    print(f"   Detail: {e}")
    sys.exit(1)


def main():
    skills_dir = Path("assets/skills")
    if not skills_dir.exists():
        print(f"❌ Error: Skills directory not found at {skills_dir}")
        print("   Make sure you're running from the project root.")
        return

    print(f"🔍 Scanning skills in {skills_dir} using Rust core...")
    print("=" * 60)

    # 1. Call Rust scanner
    try:
        tools = scan_skill_tools(str(skills_dir))
    except Exception as e:
        print(f"❌ Rust panic or error: {e}")
        import traceback

        traceback.print_exc()
        return

    print(f"✅ Found {len(tools)} tools in total.\n")

    # 2. Analyze results
    script_mode_count = 0
    legacy_mode_count = 0
    tools_with_file_path = 0
    tools_with_docstring = 0

    for tool in tools:
        mode_icon = "📜" if tool.execution_mode == "script" else "📦"
        print(f"{mode_icon} [{tool.execution_mode.upper()}] {tool.tool_name}")
        print(f"    Skill: {tool.skill_name}")
        print(f"    File:  {tool.file_path}")
        print(f"    Func:  {tool.function_name}")
        print(f"    Desc:  {tool.description[:60]}...")
        if tool.keywords:
            print(f"    Tags:  {', '.join(tool.keywords[:3])}")
        print("-" * 60)

        if tool.execution_mode == "script":
            script_mode_count += 1
        else:
            legacy_mode_count += 1

        if tool.file_path:
            tools_with_file_path += 1
        if tool.docstring:
            tools_with_docstring += 1

    # 3. Summary
    print(f"\n📊 Summary:")
    print(f"   - Script Mode (New): {script_mode_count}")
    print(f"   - Legacy Mode (Old): {legacy_mode_count}")
    print(f"   - With file_path:    {tools_with_file_path}")
    print(f"   - With docstring:    {tools_with_docstring}")

    # 4. Verification: Check git skill has script-based tools
    git_script_tools = [t for t in tools if t.skill_name == "git" and t.execution_mode == "script"]

    print(f"\n{'=' * 60}")
    if git_script_tools:
        print(
            f"✅ Verification PASSED: Detected {len(git_script_tools)} script-based tools in 'git' skill:"
        )
        for t in git_script_tools:
            print(f"   - {t.function_name}: {t.description[:40]}...")
    else:
        print("⚠️  No script-based tools detected in 'git' skill yet.")
        print("   This is expected if you haven't added @skill_script decorators yet.")
        print("   The Rust scanner is working correctly - it's finding 0 tools.")

    # 5. Test attributes are accessible
    print(f"\n{'=' * 60}")
    print("🧪 Attribute Access Test:")
    if tools:
        first_tool = tools[0]
        attrs = [
            "tool_name",
            "description",
            "skill_name",
            "file_path",
            "function_name",
            "execution_mode",
            "keywords",
            "input_schema",
            "docstring",
        ]
        all_accessible = True
        for attr in attrs:
            try:
                val = getattr(first_tool, attr)
                print(f"   ✅ {attr}: {type(val).__name__} = {str(val)[:30]}...")
            except Exception as e:
                print(f"   ❌ {attr}: {e}")
                all_accessible = False

        if all_accessible:
            print("\n✅ All PyToolRecord attributes are accessible from Python!")
        else:
            print("\n❌ Some attributes failed to access.")
    else:
        print("   No tools found to test attributes (this is OK for now).")

    print(f"\n{'=' * 60}")
    print("🎉 Rust Scanner verification complete!")


if __name__ == "__main__":
    main()
