import time
from assets.skills.decorators import skill_command

# Version: 0
# Timestamp: 1767773060.988461


@skill_command(category="stress", description="Ping Pong Test - verifies hot-reload works")
def ping(delay: float = 0.0) -> str:
    """
    Returns the version number. Used to verify the skill was reloaded.
    """
    if delay > 0:
        time.sleep(delay)
    return "pong_v0"
