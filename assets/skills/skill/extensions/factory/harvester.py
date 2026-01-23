"""
harvester.py - Session Pattern Harvester
Feature: Self-Evolution (Lightweight Version)
Description: Detects skill creation requests in session history.
            For full auto-generation, use: omni skill generate "request"

Note: Full MetaAgent integration requires proper package setup.
This lightweight version detects patterns and logs them for review.
"""

import structlog
from typing import List, Dict, Any

logger = structlog.get_logger(__name__)


class SkillHarvester:
    """
    Analyzes session history for skill creation patterns.
    Lightweight version that logs candidates for manual review.

    For full self-evolution, use:
        omni skill generate "Create a X tool"
    """

    def __init__(self, meta_agent: Any = None):
        """
        Initialize harvester.

        Args:
            meta_agent: Optional MetaAgent for auto-generation (if available)
        """
        self._meta_agent = meta_agent

    async def process_session(self, session_id: str, history: List[Dict[str, Any]]):
        """
        Analyze session for skill creation patterns.
        """
        logger.info("harvester_analyzing", session=session_id, turns=len(history))

        # Detect skill creation requests
        candidates = self._detect_patterns(history)

        if not candidates:
            logger.info("harvester_no_patterns", session=session_id)
            return

        # Log found patterns
        for req in candidates:
            print(f"\n[🌾 Detected] Skill pattern in session {session_id[:8]}...")
            print(f"            Request: {req[:60]}...")

            # If MetaAgent is available, try to generate
            if self._meta_agent is not None:
                try:
                    result = await self._meta_agent.generate_skill(
                        requirement=req,
                        max_retries=1,
                    )
                    if result.success:
                        print(f"\n[🌱 Evolved] {result.skill_name}")
                        print(f"            Path: {result.path}")
                    else:
                        print(f"\n[⚠️ Skipped] {result.error[:60]}")
                except Exception as e:
                    print(f"\n[⚠️ Error] {type(e).__name__}: {str(e)[:60]}")
            else:
                # Suggest manual generation
                print(f'            → Run: omni skill generate "{req[:40]}..."')
                logger.info("harvester_candidate", requirement=req[:100])

    def _detect_patterns(self, history: List[Dict[str, Any]]) -> List[str]:
        """
        Detect skill creation requests from history.
        Flexible pattern matching for various phrasing.
        """
        candidates = []

        for msg in reversed(history):
            if msg.get("role") != "user":
                continue

            content = msg.get("content", "").lower()

            # Flexible detection patterns
            # Match: "create a X tool", "make a X tool", "build a X skill"
            create_patterns = [
                r"create\s+(?:a|an)\s+.+(?:tool|skill|function|calculator|converter|parser|formatter)",
                r"make\s+(?:a|an)\s+.+(?:tool|skill|function)",
                r"build\s+(?:a|an)\s+.+(?:tool|skill|function)",
                r"generate\s+(?:a|an)?\s*.+(?:tool|skill|function)",
                r"implement\s+(?:a|an)\s+.+(?:tool|function)",
                r"write\s+(?:a|an)\s+.+(?:function|tool)",
            ]

            for pattern in create_patterns:
                import re

                if re.search(pattern, content):
                    candidates.append(msg.get("content", ""))
                    break

        return candidates


__all__ = ["SkillHarvester"]
