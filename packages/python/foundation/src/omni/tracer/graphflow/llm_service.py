"""Graphflow LLM service with fallback and meta-commentary guard."""

from __future__ import annotations

import asyncio

from omni.tracer.xml import extract_tag


class RealLLMService:
    """Real LLM service using omni.foundation.services.llm."""

    # Patterns that indicate meta-commentary (should use fallback)
    META_PATTERNS = [
        "the user wants",
        "the user is asking",
        "you are asking me",
        "i need to",
        "i should",
        "i will",
        "my task is",
        "here is my",
        "let me think",
        "okay, i",
        "sure, i",
    ]

    def __init__(self):
        from omni.foundation.services.llm import get_llm_provider

        self._provider = get_llm_provider()
        self._provider_disabled = False
        self._provider_failure_reason = ""
        self._consecutive_failures = 0

    def reset_runtime_state(self) -> None:
        """Reset per-run circuit breaker state."""
        self._provider_disabled = False
        self._provider_failure_reason = ""
        self._consecutive_failures = 0

    def _is_meta_commentary(self, text: str) -> bool:
        """Check if text is meta-commentary rather than actual content."""
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in self.META_PATTERNS)

    async def complete(self, topic: str, step: str, iteration: int = 1, context: str = "") -> str:
        """Call LLM with appropriate prompt for each step type."""
        reflect_fallbacks = [
            "The analysis lacks concrete language-level examples (TypeScript, Rust, Python typing).",
            "The analysis does not quantify impact on bug reduction or developer productivity.",
            "The analysis omits trade-offs such as stricter refactoring cost and type annotation overhead.",
        ]
        analyze_fallback = (
            f"{topic} improves reliability through compile-time error detection and self-documenting code. "
            f"For example, TypeScript catches interface mismatches before runtime and Rust ownership checks "
            f"prevent use-after-free at compile time."
        )
        if context:
            analyze_fallback += " It also addresses prior critiques by adding concrete examples and explicit trade-off discussion."

        fallbacks = {
            "analyze": analyze_fallback,
            "reflect": reflect_fallbacks[(max(iteration, 1) - 1) % len(reflect_fallbacks)],
            "draft": f"{topic} offers superior reliability, better tooling, and improved code maintainability.",
            "final": f"{topic} is valuable for catching errors early and enhancing code quality.",
            "evaluate": "0.30",
        }

        if self._provider_disabled:
            return fallbacks.get(step, f"{topic} is important.")

        # Context-aware prompts for structured reflection
        if step == "analyze" and context:
            prompt = f"""## Analysis Task: {topic}

## Previous Critiques to Address:
{context}

## Requirements:
1. For each critique above, explain HOW your analysis addresses it
2. Add ONE NEW insight NOT covered by previous critiques
3. Use specific examples (Python types, Rust ownership, TypeScript interfaces, etc.)
4. Return analysis in this structure:
   <analysis_contract>
     <thesis>...</thesis>
     <evidence>...</evidence>
     <examples>...</examples>
     <tradeoffs>...</tradeoffs>
     <changes_from_prev>...</changes_from_prev>
   </analysis_contract>

## Your Analysis:
"""
        elif step == "analyze":
            prompt = f"""## Analysis Task: {topic}

Provide key insights with specific examples.
Return analysis in this structure:
<analysis_contract>
  <thesis>...</thesis>
  <evidence>...</evidence>
  <examples>...</examples>
  <tradeoffs>...</tradeoffs>
  <changes_from_prev>Initial analysis iteration.</changes_from_prev>
</analysis_contract>"""
        elif step == "reflect" and context:
            prompt = f"""## Critique Task

## Previous Critiques (do NOT repeat these):
{context}

## Requirements:
1. If previous critiques were addressed, state "Issue #N: RESOLVED"
2. Identify ONE NEW issue not yet raised
3. New issues must be DIFFERENT from previous ones
4. Format: <issue type="evidence|specificity|tradeoff|completeness" severity="low|medium|high">New critique here</issue>

## Your Critique:
"""
        elif step == "reflect":
            prompt = f"""## Critique Task

Identify issues or gaps in the analysis. Be specific."""
        elif step == "draft":
            prompt = f"Write a concise summary about {topic}."
        elif step == "final":
            prompt = f"Final answer: {topic}"
        elif step == "evaluate":
            prompt = f"""Evaluate the current analysis quality for: {topic}

Return a strict score from 0.0 to 1.0 based on specificity, evidence, and completeness."""
        else:
            prompt = f"{topic}"

        if step in {"analyze", "reflect", "draft", "final"}:
            prompt += """

Return XML only:
<thought>short reasoning summary</thought>
<content>final answer text for this step</content>
"""

        try:
            result = await asyncio.wait_for(
                self._provider.complete_async(
                    system_prompt="You are an expert writer. Give direct answers only. No meta-commentary. No explanations about what you're doing. Just provide the content.",
                    user_query=prompt,
                ),
                timeout=20.0,
            )
            content = result.strip() if result else ""
            # Empty result is treated as provider failure in this demo loop.
            if not content:
                self._consecutive_failures += 1
                self._provider_failure_reason = "empty_result"
                return fallbacks.get(step, f"{topic} is important.")
            parsed_content = extract_tag(content, "content") or content
            # Reject meta-commentary
            if (
                parsed_content
                and not self._is_meta_commentary(parsed_content)
                and len(parsed_content) > 10
            ):
                self._consecutive_failures = 0
                return content
        except Exception:
            self._consecutive_failures += 1
            self._provider_failure_reason = "exception"
        return fallbacks.get(step, f"{topic} is important.")


# Lazy LLM service - only initialized when needed
_llm_service: "RealLLMService | None" = None


def get_llm_service() -> RealLLMService:
    """Get or create the LLM service (lazy loading)."""
    global _llm_service
    if _llm_service is None:
        _llm_service = RealLLMService()
    return _llm_service


__all__ = ["RealLLMService", "get_llm_service"]
