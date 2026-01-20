"""
agent/core/note_taker.py
 The Note-Taker (CCA F2 - Meta Agent).

Distills execution trajectories into structured wisdom notes.
Stores them in the Librarian (LanceDB) for future retrieval.

Philosophy:
- Meta-perspective: Analyzes history from above, not in the loop
- Hindsight focus: Extracts lessons from errors and corrections
- Dense knowledge: Each note teaches something non-trivial
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import structlog

from common.skills_path import SKILLS_DIR, load_skill_module

logger = structlog.get_logger(__name__)

# Lazy imports for heavy dependencies
_cached_llm_client: Optional[Any] = None


def _get_llm_client() -> Any:
    """Get LLM client using InferenceClient (supports MiniMax via settings.yaml)."""
    global _cached_llm_client
    if _cached_llm_client is None:
        try:
            from common.mcp_core.inference import InferenceClient

            _cached_llm_client = InferenceClient()
            logger.info("Note-Taker LLM client initialized (InferenceClient with MiniMax)")
        except ImportError as e:
            logger.debug(f"mcp_core not available: {e}")
            return None
    return _cached_llm_client


def _load_system_prompt() -> str:
    """Load the note-taker system prompt from assets using SKILLS_DIR."""
    prompt_path = SKILLS_DIR().parent / "prompts" / "system" / "note_taker.md"

    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    else:
        logger.error(f"Note-Taker prompt not found: {prompt_path}")
        return "You are a helpful Note-Taking Agent. Analyze the history and output notes."


class NoteTaker:
    """
    Meta-Agent that analyzes session history and generates wisdom notes.

    Usage:
        from agent.core.note_taker import get_note_taker

        taker = get_note_taker()
        result = await taker.distill_and_save(conversation_history)
    """

    _instance: Optional["NoteTaker"] = None

    def __new__(cls) -> "NoteTaker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self.system_prompt = _load_system_prompt()
        self.llm_client = _get_llm_client()
        self._initialized = True

        logger.info("Note-Taker initialized")

    def _clean_json_content(self, content: str) -> str:
        """Extract clean JSON from markdown code blocks or text.

        LLM often wraps JSON in ```json code blocks. This extracts the actual JSON.
        Also handles cases where LLM adds extra text before/after the JSON.
        """
        # Try to extract from ```json code block
        if "```json" in content:
            # Find content between ```json and ```
            start = content.find("```json") + len("```json")
            end = content.find("```", start)
            if end != -1:
                return content[start:end].strip()

        # Try to extract from ``` code block (no language specified)
        if "```" in content:
            start = content.find("```") + len("```")
            # Skip potential language specifier
            first_newline = content.find("\n", start)
            if first_newline != -1 and first_newline < start + 10:
                start = first_newline + 1
            end = content.find("```", start)
            if end != -1:
                return content[start:end].strip()

        # Try to find JSON object in text
        first_brace = content.find("{")
        last_brace = content.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return content[first_brace : last_brace + 1].strip()

        # Return empty string if no valid JSON found (let caller handle fallback)
        return ""

    def _format_history(self, history: List[Dict[str, str]]) -> str:
        """Convert history list to transcript string."""
        lines = []
        for msg in history:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            # Truncate long content for efficiency
            if len(content) > 1000:
                content = content[:1000] + "... [truncated]"
            lines.append(f"[{role}]\n{content}")
        return "\n\n".join(lines)

    async def _call_llm(self, transcript: str) -> List[Dict[str, Any]]:
        """Call LLM to generate notes from transcript.

        Optimized: reduced max_tokens, simplified prompt, fast-fail JSON parsing.
        """
        client = self.llm_client
        if client is None:
            logger.warning("No LLM client available, using dummy notes")
            return self._generate_dummy_notes(transcript)

        try:
            # Optimized prompt: simplified, forces JSON format
            user_query = f"""Analyze this session and extract insights.

Session:
{transcript}

Output ONLY a JSON object with this structure:
{{
  "has_insights": boolean,
  "insights": ["string", "string"]
}}

If nothing new learned, set has_insights: false."""

            result = await client.complete(
                system_prompt="You are a Knowledge Harvester. Extract technical insights. Output ONLY valid JSON.",
                user_query=user_query,
                max_tokens=500,  # Reduced from 4000 - prevent verbose output
            )

            if not result["success"]:
                logger.error(f"LLM call failed: {result['error']}")
                return self._generate_dummy_notes(transcript)

            content = result["content"]
            logger.debug(f"LLM response length: {len(content)} chars")

            # Handle empty response - fast fail
            if not content or not content.strip():
                logger.warning("Note-Taker: LLM returned empty response")
                return []

            # Clean JSON content (remove markdown code blocks if present)
            cleaned_content = self._clean_json_content(content)

            # Handle empty cleaned content - fast fail
            if not cleaned_content or not cleaned_content.strip():
                logger.warning("Note-Taker: Failed to extract JSON from response")
                return []

            # Parse JSON response - robust parsing
            parsed = json.loads(cleaned_content)

            # Validate structure
            if isinstance(parsed, dict):
                if "has_insights" in parsed and parsed["has_insights"] is True:
                    return parsed.get("notes", [])
                return []

            # Handle direct list format
            if isinstance(parsed, list):
                return parsed

            logger.warning(f"Note-Taker: Unexpected response format")
            return []

        except json.JSONDecodeError as e:
            logger.error(f"Note-Taker: JSON parse failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Note-Taker: LLM call failed: {e}")
            return []

    def _generate_dummy_notes(self, transcript: str) -> List[Dict[str, Any]]:
        """Generate basic notes when LLM is unavailable."""
        notes = []

        # Simple heuristic: detect errors and look for "fixed" patterns
        if "Error:" in transcript or "error:" in transcript.lower():
            notes.append(
                {
                    "title": "Session contained errors (see transcript)",
                    "category": "hindsight",
                    "content": f"Analysis was performed on a session with errors.\n\nTranscript preview:\n{transcript[:500]}...",
                    "tags": ["needs-review", "error"],
                    "related_files": [],
                }
            )

        if "PASSED" in transcript or "success" in transcript.lower():
            notes.append(
                {
                    "title": "Session completed successfully",
                    "category": "insight",
                    "content": "This session completed without errors.",
                    "tags": ["success"],
                    "related_files": [],
                }
            )

        return notes

    async def _save_notes(self, notes: List[Dict[str, Any]]) -> int:
        """Save notes to the Librarian via Memory Skill (fully async)."""
        try:
            # Use load_skill_module to load memory tools
            memory_tools = load_skill_module("memory")

            saved_count = 0
            for note in notes:
                title = note.get("title", "Untitled Note")
                content = note.get("content", "")
                category = note.get("category", "general")
                tags = note.get("tags", [])
                related_files = note.get("related_files", [])

                # Build full content with metadata
                full_content = f"# {title}\n\n{content}"

                # Build metadata
                metadata = {
                    "type": "note",
                    "category": category,
                    "tags": tags,
                    "related_files": related_files,
                    "source": "note_taker",
                }

                await memory_tools.save_memory(full_content, metadata)
                saved_count += 1
                logger.debug(f"Saved note: {title[:50]}...")

            return saved_count

        except Exception as e:
            logger.error(f"Failed to save notes to Librarian: {e}")
            return 0

    async def distill_and_save(self, history: List[Dict[str, str]]) -> str:
        """
        Analyze session history and save generated notes to the Librarian.

        Args:
            history: List of message dicts with 'role' and 'content' keys

        Returns:
            Summary message about what was saved
        """
        if not history:
            return "Note-Taker: No history to distill."

        logger.info(f"Note-Taker: Analyzing {len(history)} messages...")

        # Step 1: Format history
        transcript = self._format_history(history)

        # Step 2: Generate notes via LLM
        logger.info("Note-Taker: Calling LLM to generate wisdom notes...")
        notes = await self._call_llm(transcript)

        if not notes:
            logger.info("Note-Taker: No significant insights found.")
            return "Note-Taker: No noteworthy insights extracted from this session."

        # Step 3: Save to Librarian
        logger.info(f"Note-Taker: Saving {len(notes)} notes to Librarian...")
        saved_count = await self._save_notes(notes)

        # Categorize for reporting
        categories = {}
        for note in notes:
            cat = note.get("category", "general")
            categories[cat] = categories.get(cat, 0) + 1

        category_str = ", ".join(f"{k}({v})" for k, v in categories.items())

        return f"Note-Taker: Distilled {saved_count} notes [{category_str}] and saved to memory."

    async def distill_single(self, content: str, category: str = "insight") -> str:
        """
        Convenience method to distill a single piece of content.

        Args:
            content: Text to analyze
            category: Category hint (insight, hindsight, bug_fix, etc.)

        Returns:
            Summary message about what was saved
        """
        # Wrap in minimal history format
        history = [{"role": "user", "content": content}]

        return await self.distill_and_save(history)


# Singleton accessor
def get_note_taker() -> NoteTaker:
    """Get the Note-Taker singleton instance."""
    return NoteTaker()


# Convenience function for simple usage
def take_note(
    content: str,
    title: str,
    category: str = "insight",
    tags: Optional[List[str]] = None,
) -> str:
    """
    Directly save a note without LLM analysis.

    Use this for explicit knowledge that doesn't need meta-analysis.

    Args:
        content: The note content
        title: Note title
        category: insight|hindsight|bug_fix|architecture|snippet
        tags: List of tags

    Returns:
        Confirmation message
    """
    full_content = f"# {title}\n\n{content}"
    metadata = {
        "type": "note",
        "category": category,
        "tags": tags or [],
        "source": "manual",
    }

    # Use load_skill_module to load memory tools
    memory_tools = load_skill_module("memory")
    memory_tools.save_memory(full_content, metadata)

    return f"Saved note: {title}"


__all__ = [
    "NoteTaker",
    "get_note_taker",
    "take_note",
]
