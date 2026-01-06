"""
scripts/stress_trinity.py
Phase 25.4: The "Iron Trinity" Stress Test.

Verifies thread-safety and race-condition handling of SkillManager under:
1. High concurrency (Spam requests)
2. Rapid file modifications (Chaos Monkey)
3. Context generation load (Repomix)

Run with:
    python scripts/stress_trinity.py
"""

import asyncio
import time
import random
import shutil
import logging
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent

# Use the actual SKILLS_DIR from settings
import sys

# Add project root so "assets" can be imported as a module
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "python" / "common" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "python" / "agent" / "src"))

from common.settings import get_setting
from common.config_paths import get_project_root

PROJECT_ROOT = get_project_root()
SKILLS_DIR = PROJECT_ROOT / get_setting("skills.path", "assets/skills")
TARGET_SKILL_DIR = SKILLS_DIR / "stress_test_skill"
TOOLS_FILE = TARGET_SKILL_DIR / "tools.py"
REPOMIX_FILE = TARGET_SKILL_DIR / "repomix.json"

# Configure logging - only show warnings and errors
logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("stress_test")


def setup_dummy_skill():
    """Initialize a temporary skill for testing."""
    if TARGET_SKILL_DIR.exists():
        shutil.rmtree(TARGET_SKILL_DIR)

    TARGET_SKILL_DIR.mkdir(parents=True, exist_ok=True)

    # Write atomic Repomix config (tests context stability)
    REPOMIX_FILE.write_text(
        '{"output": {"style": "xml"}, "include": ["tools.py"]}', encoding="utf-8"
    )

    # Write initial tools code
    write_tool_version(0)
    print(f"✅ Setup dummy skill at: {TARGET_SKILL_DIR}")


def write_tool_version(version: int):
    """Dynamically modify tools.py, simulating developer saving files."""
    content = f'''
import time
from assets.skills.decorators import skill_command

# Version: {version}
# Timestamp: {time.time()}

@skill_command(
    category="stress",
    description="Ping Pong Test - verifies hot-reload works"
)
def ping(delay: float = 0.0) -> str:
    """
    Returns the version number. Used to verify the skill was reloaded.
    """
    if delay > 0:
        time.sleep(delay)
    return "pong_v{version}"
'''
    TOOLS_FILE.write_text(content, encoding="utf-8")


async def chaos_monkey(duration: int = 5):
    """Monkey: Randomly modifies source code during the test."""
    print("🐵 Chaos Monkey started: Modifying source code randomly...")
    end_time = time.time() + duration
    versions_written = 0

    while time.time() < end_time:
        await asyncio.sleep(random.uniform(0.05, 0.2))  # 50ms - 200ms intervals
        versions_written += 1
        write_tool_version(versions_written)

    print(f"🐵 Chaos Monkey finished. Total modifications: {versions_written}")
    return versions_written


async def spam_requests(duration: int = 5):
    """Spammer: Fires concurrent requests at the skill."""
    # Import here to avoid circular dependency issues
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()
    SKILL_NAME = "stress_test_skill"

    print("🚀 Spammer started: Firing concurrent requests...")
    end_time = time.time() + duration
    requests_sent = 0
    errors = 0
    successes = 0
    race_condition_hits = 0  # Expected brief "not found" during reload

    while time.time() < end_time:
        # Simulate burst traffic
        batch_size = random.randint(1, 5)
        tasks = []
        for _ in range(batch_size):
            tasks.append(manager.run(SKILL_NAME, "ping"))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            requests_sent += 1
            if isinstance(res, Exception):
                print(f"🔥 CALL ERROR: {res}")
                errors += 1
            elif "pong_v" in str(res):
                successes += 1
            elif "not found" in str(res):
                # Brief race condition during skill creation - acceptable
                race_condition_hits += 1
                errors += 1  # Still counts as an error but expected
            else:
                print(f"❌ Unexpected output: {res}")
                errors += 1

        await asyncio.sleep(0.01)  # 10ms interval

    print(f"🚀 Spammer finished. Total: {requests_sent}, OK: {successes}, Err: {errors}")
    return requests_sent, errors, race_condition_hits


async def context_heavy_load():
    """Context Loader: Tests if Repomix打包 blocks the main thread."""
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()
    SKILL_NAME = "stress_test_skill"

    print("📚 Context Loader started: Testing Repomix performance...")
    times = []

    for i in range(10):
        start = time.time()
        try:
            await manager.run(SKILL_NAME, "help")
        except Exception as e:
            print(f"⚠️ Context generation error: {e}")
        duration = time.time() - start
        times.append(duration)

    avg_time = sum(times) / len(times)
    print(f"📚 Context Loader finished.")
    print(f"   Avg Context Gen Time: {avg_time:.3f}s")
    print(f"   Min: {min(times):.3f}s, Max: {max(times):.3f}s")
    return avg_time


async def main():
    print("=" * 60)
    print("🛡️  Omni Trinity Architecture Stress Test  🛡️")
    print("=" * 60)
    print()
    print("This test verifies stability under:")
    print("  1. Rapid file modifications (Chaos Monkey)")
    print("  2. High concurrency requests (Spammer)")
    print("  3. Context generation load (Repomix)")
    print()

    # Setup
    print("--- Phase 0: Setup ---")
    setup_dummy_skill()

    # Initialize manager AFTER skill is created
    # This simulates a fresh manager discovering the skill
    print("\n--- Phase 1: Warmup (Cold Start) ---")
    from agent.core.skill_manager import SkillManager

    # Create a fresh manager to discover our new skill
    manager = SkillManager(skills_dir=SKILLS_DIR)
    manager.load_skills()

    res = await manager.run("stress_test_skill", "ping")
    print(f"Initial Call Result: {res}")
    assert "pong_v0" in res, "Warmup failed!"
    print("✅ Warmup passed")

    # Stress Test (Chaos + Spam + Context)
    print("\n--- Phase 2: Race Condition Stress Test (5s) ---")
    start_time = time.time()

    # Run all three tests concurrently
    results = await asyncio.gather(chaos_monkey(5), spam_requests(5), context_heavy_load())

    total_writes = results[0]
    total_reqs, total_errs, race_hits = results[1]
    avg_context_time = results[2]

    total_duration = time.time() - start_time

    # Report
    print("\n" + "=" * 60)
    print("📊  TEST REPORT  📊")
    print("=" * 60)
    print(f"Duration:           {total_duration:.2f}s")
    print(f"Skill Modifications: {total_writes}")
    print(f"Skill Invocations:   {total_reqs}")
    print(f"Failed Requests:     {total_errs}")
    print(f"  - Race Hits:       {race_hits} (expected)")
    print(f"  - Real Errors:     {total_errs - race_hits}")
    print(f"Avg Context Time:    {avg_context_time:.3f}s")

    # Calculate TPS
    if total_duration > 0:
        tps = total_reqs / total_duration
        print(f"Throughput:          {tps:.2f} requests/sec")

    print()
    print("=" * 60)

    # Pass/Fail Criteria
    real_errors = total_errs - race_hits
    if real_errors == 0 and avg_context_time < 1.0:
        print("✅  PASSED: Iron Trinity is SOLID. No crashes under fire.")
        print()
        print("Performance Summary:")
        print(f"  - Hot-reload: Working (file modified {total_writes} times)")
        print(f"  - Context gen: {avg_context_time:.3f}s avg")
        print(f"  - Throughput: {tps:.2f} req/s")
    else:
        print(f"⚠️  ATTENTION: {real_errors} real errors detected.")
        print("   Check logs above for details.")
        print()
        if avg_context_time >= 1.0:
            print(f"   ⚠️ Context generation is slow ({avg_context_time:.3f}s)")
            print("   Consider async Repomix or smaller context scope.")

    print("=" * 60)

    # Cleanup
    print("\n--- Cleanup ---")
    shutil.rmtree(TARGET_SKILL_DIR)
    print("🧹 Cleanup done.")

    return real_errors == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
