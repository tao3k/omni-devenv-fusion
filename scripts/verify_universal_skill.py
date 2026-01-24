#!/usr/bin/env uv run python
"""verify_universal_skill.py - Verify Zero-Code Skill Architecture."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "packages/python/agent/src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "packages/python/core/src"))


# Test paths
SKILLS_PATH = Path(__file__).parent / "assets/skills"


def test_universal_skill_import():
    """Test that universal skill modules can be imported."""
    print("=" * 60)
    print("Test 1: Universal Skill Imports")
    print("=" * 60)

    from omni.core.skills.extensions import SkillExtensionLoader
    from omni.core.skills.script_loader import ScriptLoader
    from omni.core.skills.universal import UniversalScriptSkill, UniversalSkillFactory

    print("UniversalScriptSkill:", UniversalScriptSkill)
    print("UniversalSkillFactory:", UniversalSkillFactory)
    print("ScriptLoader:", ScriptLoader)
    print("SkillExtensionLoader:", SkillExtensionLoader)
    print("PASS: All imports successful")
    return True


def test_universal_skill_factory():
    """Test UniversalSkillFactory discovery."""
    print("\n" + "=" * 60)
    print("Test 2: Universal Skill Factory Discovery")
    print("=" * 60)

    from omni.core.skills.universal import UniversalSkillFactory

    factory = UniversalSkillFactory(SKILLS_PATH)
    skills = factory.discover_skills()

    print(f"Discovered {len(skills)} skills:")
    for name, path in skills:
        print(f"  - {name}: {path}")

    if len(skills) == 0:
        print("FAIL: No skills discovered")
        return False

    print("PASS: Factory discovery works")
    return True


def test_git_skill_universal_loading():
    """Test loading git skill via UniversalScriptSkill in a temp directory."""
    print("\n" + "=" * 60)
    print("Test 3: Git Skill Universal Loading (in temp directory)")
    print("=" * 60)

    import asyncio
    import subprocess

    from omni.core.skills.universal import UniversalScriptSkill

    # Create a temp directory with a git repo
    tmp_dir = tempfile.mkdtemp()
    try:
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_dir, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=tmp_dir, capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_dir, capture_output=True)

        # Create initial commit so we can test later operations
        test_file = Path(tmp_dir) / "README.md"
        test_file.write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=tmp_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_dir, capture_output=True)

        skill = UniversalScriptSkill(skill_name="git", skill_path=SKILLS_PATH / "git")

        asyncio.run(skill.load({"cwd": tmp_dir}))

        print(f"Loaded: {skill.is_loaded}")
        print(f"Commands: {skill.list_commands()}")

        if not skill.is_loaded:
            print("FAIL: Skill not loaded")
            return False

        print("PASS: Universal skill loaded")
        return True
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_git_commit_in_tmpdir():
    """Test executing git.commit in a temporary directory."""
    print("\n" + "=" * 60)
    print("Test 4: Git Commit Execution (in temp directory)")
    print("=" * 60)

    import asyncio
    import subprocess

    from omni.core.skills.universal import UniversalScriptSkill

    # Create a temp directory with a git repo
    tmp_dir = tempfile.mkdtemp()
    try:
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_dir, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=tmp_dir, capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_dir, capture_output=True)

        # Create a file and commit it
        test_file = Path(tmp_dir) / "test.txt"
        test_file.write_text("initial content")
        subprocess.run(["git", "add", "."], cwd=tmp_dir, capture_output=True)

        skill = UniversalScriptSkill(skill_name="git", skill_path=SKILLS_PATH / "git")

        asyncio.run(skill.load({"cwd": tmp_dir}))

        # Execute commit command
        result = asyncio.run(
            skill.execute("git.git_commit", message="test: verifying universal skill")
        )

        print(f"Result type: {type(result)}")
        print(f"Result: {result}")

        if isinstance(result, str) and "success" in result.lower():
            print("PASS: git.git_commit executed successfully")
            return True
        else:
            print(f"FAIL: Unexpected result: {result}")
            return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_filesystem_skill():
    """Test loading filesystem skill in a temp directory."""
    print("\n" + "=" * 60)
    print("Test 5: Filesystem Skill Universal Loading (in temp directory)")
    print("=" * 60)

    import asyncio

    from omni.core.skills.universal import UniversalScriptSkill

    # Use temp directory to avoid polluting project
    tmp_dir = tempfile.mkdtemp()
    try:
        skill = UniversalScriptSkill(skill_name="filesystem", skill_path=SKILLS_PATH / "filesystem")

        asyncio.run(skill.load({"cwd": tmp_dir}))

        print(f"Loaded: {skill.is_loaded}")
        print(f"Commands: {skill.list_commands()}")

        if not skill.is_loaded:
            print("FAIL: Filesystem skill not loaded")
            return False

        print("PASS: Filesystem skill loaded")
        return True
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_all_skills_loading():
    """Test loading all skills via factory (in temp directories)."""
    print("\n" + "=" * 60)
    print("Test 6: All Skills Universal Loading (in temp directories)")
    print("=" * 60)

    import asyncio
    import subprocess

    from omni.core.skills.universal import UniversalSkillFactory

    # Create a temp directory for git operations
    tmp_dir = tempfile.mkdtemp()
    try:
        # Initialize git repo for git-related skills
        subprocess.run(["git", "init"], cwd=tmp_dir, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=tmp_dir, capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_dir, capture_output=True)

        # Create initial commit
        test_file = Path(tmp_dir) / "README.md"
        test_file.write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=tmp_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_dir, capture_output=True)

        factory = UniversalSkillFactory(SKILLS_PATH)
        skills = []

        for name, path in factory.discover_skills():
            try:
                skill = factory.create_skill((name, path))
                asyncio.run(skill.load({"cwd": tmp_dir}))
                skills.append((name, skill))
                print(f"  Loaded: {name} ({len(skill.list_commands())} commands)")
            except Exception as e:
                print(f"  Failed: {name}: {e}")

        print(f"\nTotal: {len(skills)} skills loaded")

        if len(skills) == 0:
            print("FAIL: No skills loaded")
            return False

        print("PASS: All skills loaded")
        return True
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Zero-Code Skill Architecture Verification")
    print("=" * 60 + "\n")

    tests = [
        ("Imports", test_universal_skill_import),
        ("Factory Discovery", test_universal_skill_factory),
        ("Git Skill Loading", test_git_skill_universal_loading),
        ("Git Commit Execution", test_git_commit_in_tmpdir),
        ("Filesystem Skill", test_filesystem_skill),
        ("All Skills Loading", test_all_skills_loading),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback

            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    failed = len(results) - passed

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\nTotal: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
