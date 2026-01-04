# mcp-core/inference.py
"""
LLM Inference Module

Provides unified interface for LLM API calls with consistent error handling,
retry logic, and configuration management. Used by both orchestrator.py and coder.py.

Features:
- Async API client (supports Anthropic, OpenAI compatible APIs)
- Configurable model selection
- Retry logic
- Streaming support
- Error handling
- Config file support (.mcp.json, .claude/settings.json)

Usage:
    client = InferenceClient()
    result = await client.complete("You are a Python expert.", "Write a function to sort a list.")
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

import structlog
from anthropic import AsyncAnthropic

log = structlog.get_logger("mcp-core.inference")

# Default configuration
DEFAULT_MODEL = "MiniMax-M2.1"
DEFAULT_BASE_URL = "https://api.minimax.io/anthropic"
DEFAULT_TIMEOUT = 120
DEFAULT_MAX_TOKENS = 4096


def _get_git_toplevel() -> Optional[Path]:
    """
    Get git toplevel directory using GitOps approach.

    DEPRECATED: Use get_project_root() from common.mcp_core.gitops instead.
    This function is kept for backwards compatibility.

    Returns:
        Path to git repository root or None
    """
    from common.mcp_core.gitops import get_git_toplevel

    return get_git_toplevel()


def _load_api_key_from_config() -> Optional[str]:
    """
    Load API key from project config files.

    Checks in order:
    1. Environment variable ANTHROPIC_API_KEY
    2. .claude/settings.json (via agent/settings.yaml path)
    3. .mcp.json (Claude Desktop format)

    Delegates to common.mcp_core.api_key.get_anthropic_api_key() for unified loading.
    """
    from common.mcp_core.api_key import get_anthropic_api_key

    return get_anthropic_api_key()


# =============================================================================
# InferenceClient Class
# =============================================================================


class InferenceClient:
    """
    Unified LLM inference client for MCP servers.

    Provides consistent interface for both orchestrator and coder servers.
    Supports streaming, retries, and configurable API endpoints.

    Usage:
        client = InferenceClient()
        response = await client.complete(system_prompt, user_query)
        async for chunk in client.stream_complete(system_prompt, user_query):
            print(chunk)
    """

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        timeout: int = None,
        max_tokens: int = None,
    ):
        """
        Initialize InferenceClient.

        Args:
            api_key: API key (defaults to ANTHROPIC_API_KEY env var)
            base_url: API base URL
            model: Default model name
            timeout: Request timeout in seconds
            max_tokens: Max tokens per response
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or _load_api_key_from_config()
        self.base_url = base_url or DEFAULT_BASE_URL
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout or DEFAULT_TIMEOUT
        self.max_tokens = max_tokens or DEFAULT_MAX_TOKENS

        if not self.api_key:
            log.warning("inference.no_api_key")

        self.client = AsyncAnthropic(api_key=self.api_key, base_url=self.base_url)

    def _build_system_prompt(
        self, role: str, name: str = None, description: str = None, prompt: str = None
    ) -> str:
        """
        Build system prompt from persona configuration.

        Args:
            role: Persona role identifier
            name: Persona name override
            description: Persona description
            prompt: Custom system prompt

        Returns:
            Formatted system prompt string
        """
        if prompt:
            return prompt

        return f"You are {name or role}. {description or ''}"

    async def complete(
        self,
        system_prompt: str,
        user_query: str,
        model: str = None,
        max_tokens: int = None,
        timeout: int = None,
    ) -> Dict[str, Any]:
        """
        Make a non-streaming LLM call.

        Args:
            system_prompt: System prompt defining the persona/task
            user_query: User's actual query
            model: Override model name
            max_tokens: Override max tokens
            timeout: Override timeout

        Returns:
            Dict with keys: success (bool), content (str), error (str), usage (Dict)
        """
        actual_model = model or self.model
        actual_max_tokens = max_tokens or self.max_tokens
        actual_timeout = timeout or self.timeout

        messages = [{"role": "user", "content": user_query}]

        log.info(
            "inference.request",
            model=actual_model,
            prompt_length=len(system_prompt),
            query_length=len(user_query),
        )

        try:
            response = await asyncio.wait_for(
                self.client.messages.create(
                    model=actual_model,
                    max_tokens=actual_max_tokens,
                    system=system_prompt,
                    messages=messages,
                ),
                timeout=actual_timeout,
            )

            # Extract text from response
            content = ""
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    content += block.text
                elif hasattr(block, "text"):
                    content += block.text

            result = {
                "success": True,
                "content": content,
                "model": actual_model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                "error": "",
            }

            log.info(
                "inference.success",
                model=actual_model,
                input_tokens=result["usage"]["input_tokens"],
                output_tokens=result["usage"]["output_tokens"],
            )

            return result

        except asyncio.TimeoutError:
            log.warning("inference.timeout", model=actual_model)
            return {
                "success": False,
                "content": "",
                "error": f"Request timed out after {actual_timeout}s",
                "model": actual_model,
                "usage": {},
            }

        except Exception as e:
            log.warning("inference.error", model=actual_model, error=str(e))
            return {
                "success": False,
                "content": "",
                "error": str(e),
                "model": actual_model,
                "usage": {},
            }

    async def stream_complete(
        self,
        system_prompt: str,
        user_query: str,
        model: str = None,
        max_tokens: int = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Make a streaming LLM call.

        Args:
            system_prompt: System prompt defining the persona/task
            user_query: User's actual query
            model: Override model name
            max_tokens: Override max tokens

        Yields:
            Dict with keys: chunk (str), done (bool), usage (Dict)
        """
        actual_model = model or self.model
        actual_max_tokens = max_tokens or self.max_tokens

        messages = [{"role": "user", "content": user_query}]

        log.info(
            "inference.stream_request",
            model=actual_model,
            prompt_length=len(system_prompt),
        )

        try:
            async with self.client.messages.stream(
                model=actual_model,
                max_tokens=actual_max_tokens,
                system=system_prompt,
                messages=messages,
            ) as stream:
                chunks = []
                async for event in stream:
                    if hasattr(event, "type") and event.type == "message_stop":
                        break
                    if hasattr(event, "delta") and getattr(event.delta, "text", None):
                        chunk = event.delta.text
                        chunks.append(chunk)
                        yield {"chunk": chunk, "done": False, "content": "".join(chunks)}

                # Final chunk with usage info
                yield {"chunk": "", "done": True, "content": "".join(chunks)}

        except Exception as e:
            log.warning("inference.stream_error", model=actual_model, error=str(e))
            yield {"chunk": "", "done": True, "content": "", "error": str(e)}

    async def complete_with_retry(
        self,
        system_prompt: str,
        user_query: str,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make an LLM call with automatic retry on failure.

        Args:
            system_prompt: System prompt
            user_query: User query
            max_retries: Maximum retry attempts
            backoff_factor: Exponential backoff multiplier
            **kwargs: Additional arguments for complete()

        Returns:
            Result dict from complete()
        """
        last_error = ""

        for attempt in range(max_retries):
            result = await self.complete(system_prompt, user_query, **kwargs)

            if result["success"]:
                return result

            last_error = result["error"]
            log.warning(
                "inference.retry",
                attempt=attempt + 1,
                max_retries=max_retries,
                error=last_error,
            )

            if attempt < max_retries - 1:
                await asyncio.sleep(backoff_factor * (2**attempt))

        return {
            "success": False,
            "content": "",
            "error": f"Failed after {max_retries} attempts: {last_error}",
            "usage": {},
        }


# =============================================================================
# Persona Management
# =============================================================================

# Standard personas for project development
PERSONAS = {
    "architect": {
        "name": "System Architect",
        "description": "Expert in software design, patterns, and refactoring strategies.",
        "when_to_use": "Making architectural decisions, evaluating design patterns, planning refactoring.",
        "prompt": """You are a Principal Software Architect with 20 years of experience.
Focus on:
- Clean architecture principles (SOLID, hexagonal, microservices)
- Design patterns and when to use them
- Trade-offs between different approaches
- Long-term maintainability
- Security and performance considerations

Provide concise, actionable advice with clear reasoning.""",
    },
    "platform_expert": {
        "name": "Platform Engineer",
        "description": "Expert in Nix, DevOps, and infrastructure.",
        "when_to_use": "Configuring development environments, fixing Nix errors, setting up services.",
        "prompt": """You are a Nix and Platform Engineering expert.
Focus on:
- NixOS and nixpkgs best practices
- Declarative configuration
- Reproducible builds
- DevOps automation
- Container and VM management

Provide working code snippets and exact commands where possible.""",
    },
    "devops_mlops": {
        "name": "DevOps/MLOps Specialist",
        "description": "Expert in CI/CD, pipelines, and ML workflows.",
        "when_to_use": "Setting up CI/CD, designing ML pipelines, ensuring reproducibility.",
        "prompt": """You are a DevOps and MLOps specialist.
Focus on:
- CI/CD pipeline design (GitHub Actions, GitLab CI)
- ML workflow automation
- Reproducibility and version control
- Testing strategies
- Deployment patterns

Provide practical pipeline configurations and automation scripts.""",
    },
    "sre": {
        "name": "SRE Engineer",
        "description": "Expert in reliability, security, and performance.",
        "when_to_use": "Security reviews, performance optimization, reliability engineering.",
        "prompt": """You are a Site Reliability Engineering expert.
Focus on:
- Security best practices
- Performance optimization
- Error handling and resilience
- Monitoring and observability
- Incident response

Be thorough in security reviews and provide defensive recommendations.""",
    },
    "tech_writer": {
        "name": "Technical Writing Expert",
        "description": "Expert in engineering documentation and clear communication.",
        "when_to_use": "Writing or polishing READMEs, design docs, commit messages, or any project documentation.",
        "context_hints": [
            "Reference agent/writing-style/01_philosophy.md for rules",
            "Apply BLUF (Bottom Line Up Front)",
            "Use active voice, strip clutter",
            "Structure with What-Why-How pattern",
        ],
        "prompt": """You are a Technical Writing Expert following the project's Engineering Documentation Style Guide (docs/explanation/design-philosophy.md is derived from agent/writing-style/).

Core Principles (from On Writing Well & Spring Into Technical Writing):
1. BLUF: Lead with the most important information
2. Strip Clutter: Cut every unnecessary word
3. Active Voice: Use active verbs, avoid passive
4. Specificity: Be precise, avoid vague words

For Commit Messages:
- Subject: Imperative mood, max 50 chars
- Body: Explain what and why, not how

For Technical Explanations:
- Context (Problem) -> Solution (Fix) -> Verification (Proof)

Formatting Rules:
- Wrap commands/variables in backticks
- Use bullet points for lists, numbered for steps
- Descriptive link text, not "[here]"

When editing text, apply the 4-question checklist:
1. Can I remove words without losing meaning?
2. Is the most important point first?
3. Did I use active verbs?
4. Is the formatting scanning-friendly?

Refuse to accept unstructured or cluttered text. Restructure it into a clean, logical format.""",
    },
}


def load_personas_from_file(filepath: str = None) -> Dict[str, Any]:
    """
    Load additional personas from JSON file.

    Args:
        filepath: Path to personas JSON file

    Returns:
        Dict of persona configurations
    """
    import json

    if filepath is None:
        filepath = os.environ.get("ORCHESTRATOR_PERSONAS_FILE")

    if filepath is None or not os.path.exists(filepath):
        return {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        log.info("inference.personas_loaded", source=filepath, count=len(data))
        return data
    except Exception as e:
        log.warning("inference.personas_load_failed", error=str(e))
        return {}


# Merge static and dynamic personas
_DYNAMIC_PERSONAS = load_personas_from_file()
PERSONAS = {**PERSONAS, **_DYNAMIC_PERSONAS}


def get_persona(role: str) -> Optional[Dict[str, str]]:
    """
    Get persona configuration by role.

    Args:
        role: Persona role identifier

    Returns:
        Persona dict or None if not found
    """
    return PERSONAS.get(role)


def build_persona_prompt(role: str) -> str:
    """
    Build full system prompt for a persona.

    Args:
        role: Persona role identifier

    Returns:
        Formatted system prompt
    """
    persona = PERSONAS.get(role)
    if not persona:
        return ""

    hints = ""
    if persona.get("context_hints"):
        hints = "\nContext hints:\n" + "\n".join(f"- {hint}" for hint in persona["context_hints"])

    return (
        f"You are {persona.get('name', role)}.\n"
        f"{persona.get('description', '')}\n"
        f"When to use: {persona.get('when_to_use', '')}\n"
        f"{hints}\n"
        f"{persona.get('prompt', '')}"
    )
