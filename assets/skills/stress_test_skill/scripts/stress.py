"""
stress_test_skill/scripts/stress.py - Stress Test Commands

Phase 63: Migrated from tools.py to scripts pattern.
"""

import time

from agent.skills.decorators import skill_script


@skill_script(
    name="ping",
    category="stress",
    description="Ping Pong Test - verifies hot-reload works",
)
def ping(delay: float = 0.0) -> str:
    """
    Returns the version number. Used to verify the skill was reloaded.
    """
    if delay > 0:
        time.sleep(delay)
    return "pong_v0"
