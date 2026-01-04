#!/usr/bin/env python3
"""
test_router.py - Test script for Semantic Router (Phase 14)

Tests:
1. Basic routing with skills selection
2. Mission Brief generation
3. Hive Mind Cache (cache hits)
4. Context injection format

Usage:
    python scripts/test_router.py                                    # Run all tests
    python scripts/test_router.py --skills git,filesystem            # Test multiple skills
    python scripts/test_router.py --list-skills                      # List available skill groups
    python scripts/test_router.py --query "commit my changes"        # Single query test
    python scripts/test_router.py --cache                            # Test cache behavior
"""
import asyncio
import argparse
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "python" / "agent" / "src"))

from agent.core.router import get_router, clear_routing_cache, RoutingResult


async def test_router(query: str):
    """Test the semantic router with a single query."""
    router = get_router()

    print(f"\n{'='*60}")
    print(f"QUERY: {query}")
    print(f"{'='*60}")

    result = await router.route(query)

    print(f"\n🎯 ROUTING RESULT:")
    print(f"   Skills: {result.selected_skills}")
    print(f"   Confidence: {result.confidence:.2f}")
    print(f"   From Cache: {'Yes ⚡' if result.from_cache else 'No'}")
    print(f"\n📋 MISSION BRIEF:")
    print(f"   {result.mission_brief}")
    print(f"\n💭 REASONING:")
    print(f"   {result.reasoning}")
    print(f"{'='*60}\n")

    return result


async def test_cache_behavior():
    """Test Hive Mind Cache behavior."""
    router = get_router()
    clear_routing_cache()

    query = "run the tests"

    print("\n🧪 CACHE BEHAVIOR TEST")
    print("=" * 60)

    # First call - should be cache miss
    print(f"\n1️⃣ First call (expect MISS):")
    result1 = await router.route(query, use_cache=False)
    print(f"   From Cache: {result1.from_cache}")

    # Second call - should be cache hit
    print(f"\n2️⃣ Second call (expect HIT):")
    result2 = await router.route(query)
    print(f"   From Cache: {result2.from_cache}")

    # Verify same result
    print(f"\n3️⃣ Verify consistency:")
    print(f"   Same skills: {result1.selected_skills == result2.selected_skills}")
    print(f"   Same brief: {result1.mission_brief == result2.mission_brief}")

    # Timing comparison
    print(f"\n4️⃣ Performance:")
    start = time.time()
    for _ in range(5):
        await router.route(query)
    elapsed = time.time() - start
    print(f"   5 cached calls: {elapsed*1000:.1f}ms (should be near-instant)")

    print("=" * 60)


async def test_mission_brief():
    """Test that mission briefs are specific and actionable."""
    router = get_router()
    clear_routing_cache()

    test_cases = [
        ("fix the IndexError in src/main.py line 42", ["filesystem", "file_ops", "code_insight"]),
        ("commit my changes with message 'feat: add new feature'", ["git"]),
        ("write a README for this project", ["writer", "documentation"]),
        ("search for all occurrences of 'TODO' in the codebase", ["advanced_search"]),
    ]

    print("\n📋 MISSION BRIEF QUALITY TEST")
    print("=" * 60)

    all_passed = True
    for query, expected_skills in test_cases:
        result = await router.route(query, use_cache=False)

        # Check skills
        skills_ok = any(s in result.selected_skills for s in expected_skills)

        # Check brief quality
        brief = result.mission_brief
        brief_has_action = any(word in brief.lower() for word in ['use', 'fix', 'commit', 'write', 'search', 'create', 'read'])
        brief_not_generic = len(brief) > 20  # Should be more than generic text

        passed = skills_ok and brief_has_action and brief_not_generic

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n{status}: {query[:40]}")
        print(f"   Skills: {result.selected_skills}")
        print(f"   Brief: {brief[:80]}...")
        print(f"   Brief has action: {brief_has_action}, Not generic: {brief_not_generic}")

        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    return all_passed


# =============================================================================
# Test Cases Organized by Skill
# =============================================================================

TEST_CASES_BY_SKILL = {
    "git": [
        ("commit my changes", ["git"]),
        ("push to remote", ["git"]),
        ("check git status", ["git"]),
        ("view commit history", ["git"]),
        ("create a new branch", ["git"]),
        ("merge feature branch", ["git"]),
        ("show me the diff", ["git"]),
    ],
    "filesystem": [
        ("read the README file", ["filesystem"]),
        ("list files in current directory", ["filesystem"]),
        ("create a new Python file called utils.py", ["filesystem", "file_ops"]),
        ("edit config.yaml", ["file_ops"]),
        ("show me the directory structure", ["filesystem"]),
        ("find all JSON files", ["filesystem"]),
    ],
    "testing": [
        ("run the tests", ["testing"]),
        ("what tests should I run?", ["testing_protocol"]),
        ("run unit tests", ["testing"]),
        ("check test coverage", ["testing"]),
    ],
    "writer": [
        ("polish this text", ["writer"]),
        ("check my writing style", ["writer"]),
        ("improve the documentation", ["documentation"]),
        ("check grammar", ["writer"]),
    ],
    "knowledge": [
        ("what are the project rules?", ["knowledge"]),
        ("explain how to commit", ["git"]),
        ("how do I use the git skill?", ["knowledge"]),
        ("show me the coding standards", ["knowledge"]),
    ],
    "code_insight": [
        ("analyze the code structure", ["code_insight"]),
        ("what functions are defined in main.py?", ["code_insight"]),
        ("find all classes in this file", ["code_insight"]),
        ("show me the imports", ["code_insight"]),
    ],
    "terminal": [
        ("run a shell command", ["terminal"]),
        ("execute npm install", ["terminal"]),
        ("run a build command", ["terminal"]),
        ("check disk usage", ["terminal"]),
    ],
    "software_engineering": [
        ("design the system architecture", ["software_engineering"]),
        ("refactor this module", ["software_engineering"]),
        ("what is the tech stack?", ["software_engineering"]),
    ],
    "advanced_search": [
        ("search for all occurrences of 'TODO'", ["advanced_search"]),
        ("find where login is defined", ["advanced_search"]),
        ("grep for error handling patterns", ["advanced_search"]),
        ("find all API endpoints", ["advanced_search"]),
    ],
}

# Flatten all test cases
ALL_TEST_CASES = []
for skill_cases in TEST_CASES_BY_SKILL.values():
    ALL_TEST_CASES.extend(skill_cases)


def list_skills():
    """List available skill groups."""
    print("\n📋 AVAILABLE SKILL GROUPS")
    print("=" * 40)
    for skill, cases in sorted(TEST_CASES_BY_SKILL.items()):
        print(f"  {skill:<20} ({len(cases)} tests)")
    print("=" * 40)
    print(f"  {'all':<20} ({len(ALL_TEST_CASES)} tests total)")
    print()


async def run_tests_for_skills(skill_names: list):
    """Run tests for one or more skills."""
    router = get_router()
    clear_routing_cache()

    if not skill_names:
        # Default to all
        test_cases = ALL_TEST_CASES
        print("🧪 SEMANTIC ROUTER PHASE 14 - FULL TEST SUITE")
    elif "all" in skill_names:
        test_cases = ALL_TEST_CASES
        print("🧪 SEMANTIC ROUTER PHASE 14 - FULL TEST SUITE")
    else:
        test_cases = []
        skill_labels = []
        for name in skill_names:
            if name in TEST_CASES_BY_SKILL:
                test_cases.extend(TEST_CASES_BY_SKILL[name])
                skill_labels.append(name)
            else:
                print(f"❌ Unknown skill: {name}")
                print("Use --list-skills to see available skills.")
                return False
        print(f"🧪 SEMANTIC ROUTER PHASE 14 - {', '.join(skill_labels).upper()} SKILL TESTS")

    print("=" * 60)

    passed = 0
    failed = 0

    for query, expected_skills in test_cases:
        result = await test_router(query)
        selected = set(result.selected_skills)
        expected = set(expected_skills)

        # Check if expected skills are in the result (fuzzy match)
        if expected.issubset(selected) or selected.issubset(expected):
            print(f"✅ PASS: '{query[:40]:<40}' → {result.selected_skills}")
            passed += 1
        elif len(expected & selected) > 0:
            print(f"✅ PASS: '{query[:40]:<40}' → {result.selected_skills}")
            passed += 1
        else:
            print(f"❌ FAIL: '{query[:40]:<40}'")
            print(f"   Expected: {expected_skills}, Got: {result.selected_skills}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"📊 ROUTING RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    return failed == 0


async def run_all_tests():
    """Run a comprehensive test suite (all skills)."""
    return await run_tests_for_skills([])


async def interactive_test():
    """Interactive mode - type queries and see routing results."""
    router = get_router()

    print("\n🎮 INTERACTIVE ROUTING TEST (Phase 14)")
    print("Type 'cache' to test cache, 'quit' to exit\n")

    while True:
        query = input("You: ").strip()
        if query.lower() in ('quit', 'exit', 'q'):
            break
        if query.lower() == 'cache':
            await test_cache_behavior()
            continue

        result = await router.route(query)
        print(f"\n🎯 Skills: {result.selected_skills}")
        print(f"📋 Brief: {result.mission_brief}")
        print(f"⚡ Cached: {result.from_cache}\n")


async def main():
    parser = argparse.ArgumentParser(description="Test the Semantic Router (Phase 14)")
    parser.add_argument("--query", "-q", type=str, help="Single query to test")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--all", "-a", action="store_true", help="Run all test cases")
    parser.add_argument("--cache", "-c", action="store_true", help="Test cache behavior")
    parser.add_argument("--brief", "-b", action="store_true", help="Test mission brief quality")
    parser.add_argument("--skills", "-s", type=str, help="Run tests for specific skills (comma-separated, e.g., git,filesystem)")
    parser.add_argument("--list-skills", "-l", action="store_true", help="List available skill groups")

    args = parser.parse_args()

    if args.list_skills:
        list_skills()
        return

    if args.interactive:
        await interactive_test()
    elif args.cache:
        await test_cache_behavior()
    elif args.brief:
        success = await test_mission_brief()
        sys.exit(0 if success else 1)
    elif args.skills:
        skill_list = [s.strip() for s in args.skills.split(",")]
        success = await run_tests_for_skills(skill_list)
        sys.exit(0 if success else 1)
    elif args.query:
        await test_router(args.query)
    else:
        # Default: run all tests
        success = await run_all_tests()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
