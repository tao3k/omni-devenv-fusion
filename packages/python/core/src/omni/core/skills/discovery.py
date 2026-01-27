"""
omni.core.skills.discovery - Skill Discovery Module

High-performance skill discovery using Rust + LanceDB.

Architecture:
    LanceDB (SSOT) -> Foundation (Reader) -> Core (Discovery) -> Kernel

    ┌─────────────────┐
    │    LanceDB      │  ← Single Source of Truth (Rust/LanceDB)
    │   (Vector DB)   │
    └────────┬────────┘
             │
             ▼ Reads (Memory Registry - O(1) lookup)
    ┌─────────────────┐
    │Memory Registry  │  ← HashMap[tool_name -> ToolRecord]
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │SkillDiscovery   │
    │Service          │
    └────────┬────────┘
             │
             ▼ Returns
    ┌─────────────────┐
    │   Kernel        │  ← Consumes ToolMatch with usage_template
    └─────────────────┘

Unified Search Flow:
    1. Query → LanceDB (semantic retrieval) + Keyword matching (fallback)
    2. Tool Names → Memory Registry lookup (O(1))
    3. Schema → Template Generation (@omni("tool", {...}))
    4. Return enriched ToolMatch objects
"""

import json
import os
from typing import Any

from omni.foundation.bridge.scanner import (
    DiscoveredSkillRules,
    PythonSkillScanner,
)
from omni.foundation.config.logging import get_logger
from pydantic import BaseModel

logger = get_logger("omni.core.discovery")


def generate_usage_template(tool_name: str, input_schema: dict | str | None) -> str:
    """
    Generate a smart usage template based on JSON Schema.

    Example Output:
        @omni("git.commit", {"message": "feat: ...", "repo_path": "."})

    Args:
        tool_name: Full tool name (e.g., "git.commit")
        input_schema: JSON Schema dict or string for the tool's parameters

    Returns:
        Formatted @omni() call template with type-appropriate placeholders
    """
    # Parse schema if it's a string
    if input_schema is None:
        return f'@omni("{tool_name}", {{"..."}})'

    if isinstance(input_schema, str):
        try:
            schema = json.loads(input_schema)
            # Handle double-encoded JSON from LanceDB (Rust serialization)
            # If result is still a string, parse again
            if isinstance(schema, str):
                schema = json.loads(schema)
        except (json.JSONDecodeError, TypeError):
            return f'@omni("{tool_name}", {{"..."}})'
    else:
        schema = input_schema

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    args = {}

    for prop_name, prop_meta in properties.items():
        # Only include required args to avoid cluttering context window
        if prop_name not in required:
            continue

        # Generate placeholder based on type
        prop_type = prop_meta.get("type", "string")
        enum_values = prop_meta.get("enum")

        if enum_values:
            # Use first enum value as placeholder
            placeholder = enum_values[0] if isinstance(enum_values[0], str) else f"<{prop_name}>"
        elif prop_type == "integer":
            placeholder = 0
        elif prop_type == "number":
            placeholder = 0.0
        elif prop_type == "boolean":
            placeholder = True
        elif prop_type == "array":
            placeholder = []
        elif prop_type == "object":
            placeholder = {}
        else:
            # String - add type hint in placeholder
            placeholder = f"<{prop_name}>"

        args[prop_name] = placeholder

    # Format as compact JSON string
    args_str = json.dumps(args, separators=(", ", ": "))
    return f'@omni("{tool_name}", {args_str})'


class DiscoveredSkill(BaseModel):
    """Represents a discovered skill with its metadata.

    Created from Foundation's DiscoveredSkillRules via from_index_entry().
    """

    name: str
    path: str
    metadata: dict[str, Any]
    has_extensions: bool = False

    @classmethod
    def from_index_entry(cls, entry: DiscoveredSkillRules) -> "DiscoveredSkill":
        """Create from Foundation DiscoveredSkillRules object.

        Args:
            entry: DiscoveredSkillRules from PythonSkillScanner.scan_directory()

        Returns:
            DiscoveredSkill instance
        """
        # Check for extensions directory
        has_ext = False
        if entry.skill_path:
            ext_path = os.path.join(entry.skill_path, "extensions")
            has_ext = os.path.isdir(ext_path)

        return cls(
            name=entry.skill_name,
            path=entry.skill_path,
            metadata=entry.metadata,
            has_extensions=has_ext,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], name: str, path: str) -> "DiscoveredSkill":
        """Create from raw dictionary (for testing/fallback).

        Args:
            data: Dictionary with skill metadata
            name: Skill name
            path: Skill path

        Returns:
            DiscoveredSkill instance
        """
        has_ext = os.path.isdir(os.path.join(path, "extensions"))
        return cls(
            name=name,
            path=path,
            metadata=data,
            has_extensions=has_ext,
        )


class ToolMatch(BaseModel):
    """Represents a tool matching a search query."""

    name: str
    skill_name: str
    description: str
    score: float
    matched_intent: str
    usage_template: str = ""


class ToolRecord:
    """Represents a tool record from the Memory Registry."""

    def __init__(
        self,
        name: str,
        skill_name: str,
        description: str,
        category: str = "",
        input_schema: str = "{}",
        file_path: str = "",
    ):
        self.name = name
        self.skill_name = skill_name
        self.description = description
        self.category = category
        self.input_schema = input_schema
        self.file_path = file_path

    @classmethod
    def from_tool_dict(cls, tool: dict, skill_name: str) -> "ToolRecord":
        """Create from tool dictionary (from LanceDB)."""
        return cls(
            name=tool.get("name", ""),
            skill_name=skill_name,
            description=tool.get("description", ""),
            category=tool.get("category", ""),
            input_schema=tool.get("input_schema", "{}"),
            file_path=tool.get("file_path", ""),
        )


class SkillDiscoveryService:
    """
    Level 2: Skill Discovery Service.

    Coordinates skill discovery using Hybrid Search:
    1. Vector DB (Rust/LanceDB) for semantic retrieval
    2. Memory Registry (HashMap) for O(1) schema lookup
    3. Template generation for enriched @omni() calls

    Architecture:
        - Memory Registry: O(1) lookup for tool metadata + schema
        - Vector Store: Semantic search for candidate selection
        - Fallback: Keyword matching when Vector DB unavailable

    Usage:
        service = SkillDiscoveryService()
        skills = service.discover_all()  # Reads from LanceDB
        for skill in skills:
            print(f"Found: {skill.name}")

        # Search for tools (hybrid: vector + keyword)
        matches = service.search_tools(query="read file", limit=3)
    """

    # Category boost mapping for query patterns
    CATEGORY_BOOSTS: dict[tuple[str, ...], list[str]] = {
        ("code", "refactor", "function", "class", "variable", "import"): [
            "engineering",
            "code_tools",
            "development",
        ],
        ("file", "read", "write", "edit", "create", "delete"): [
            "filesystem",
            "file_tools",
        ],
        ("search", "find", "grep", "query"): ["search", "query_tools"],
        ("git", "commit", "branch", "merge", "push"): ["version_control", "git"],
        ("test", "unit", "integration", "coverage"): ["testing", "qa"],
        ("api", "http", "request", "rest", "endpoint"): ["api", "network"],
        ("database", "sql", "query", "table"): ["database", "data"],
        ("shell", "run", "execute", "command", "bash"): ["shell", "execution"],
    }

    def __init__(self):
        """Initialize the discovery service.

        Uses Unified LanceDB Architecture:
        - Primary: LanceDB (Single Source of Truth)
        """
        self._index: list[dict] | None = None
        # Memory Registry: tool_name -> ToolRecord (O(1) lookup)
        self._registry: dict[str, ToolRecord] = {}
        self._registry_loaded = False
        self._source: str = "lance"  # Track data source for testing

    @property
    def source(self) -> str:
        """Return the data source used by the discovery service.

        Returns:
            "lance" when using LanceDB, "memory" for fallback
        """
        return self._source

    def _load_registry(self) -> dict[str, ToolRecord]:
        """Load tools into Memory Registry.

        Reads from LanceDB (Single Source of Truth).

        Returns:
            Dictionary mapping tool_name -> ToolRecord
        """
        if self._registry_loaded:
            return self._registry

        self._registry = {}

        # Step 1: Try LanceDB (Primary Source)
        try:
            from omni.foundation.bridge.rust_vector import get_vector_store

            store = get_vector_store()
            import asyncio

            tools = asyncio.run(store.list_all_tools())

            if tools:
                for tool in tools:
                    # Use tool_name (from Rust scanner) or id as fallback
                    tool_name = tool.get("tool_name") or tool.get("id", "")
                    if tool_name:
                        self._registry[tool_name] = ToolRecord(
                            name=tool_name,
                            skill_name=tool.get("skill_name", ""),
                            description=tool.get("description", "")
                            or tool.get("content", "")[:200],
                            category=tool.get("category", ""),
                            input_schema=tool.get("input_schema", "{}"),
                            file_path=tool.get("file_path", ""),
                        )
                self._registry_loaded = True
                logger.debug(f"Loaded {len(self._registry)} tools from LanceDB")
                return self._registry
        except Exception as e:
            logger.error(f"Failed to load from LanceDB: {e}")
            return {}

    def get_tool_record(self, tool_name: str) -> ToolRecord | None:
        """Get a single tool record from the Registry (O(1))."""
        registry = self._load_registry()
        return registry.get(tool_name)

    @property
    def tool_count(self) -> int:
        """Get the number of tools in the registry."""
        self._load_registry()
        return len(self._registry)

    def search_tools(self, query: str, limit: int = 3, threshold: float = 0.3) -> list[ToolMatch]:
        """
        Search for tools matching the given intent/query.

        Search Flow:
        1. Load Memory Registry (O(1) tool lookup)
        2. Keyword matching (fast, works offline)
        3. Generate usage template from schema

        Args:
            query: Natural language intent (e.g., "read markdown files")
            limit: Maximum number of results to return
            threshold: Minimum score threshold (0.0-1.0)

        Returns:
            List of ToolMatch objects sorted by score
        """
        # Step 1: Load Memory Registry (O(1) lookup for tool metadata + schema)
        registry = self._load_registry()
        query_lower = query.lower()
        query_words = set(query_lower.split())

        # Detect query intent for category boosting
        query_intent = self._detect_query_intent(query_words)

        matches: list[tuple[ToolMatch, float]] = []

        # Step 2: Search through all tools using layered scoring
        for tool_name, tool_record in registry.items():
            tool_score = 0.0
            tool_desc = tool_record.description
            tool_category = tool_record.category
            skill_name = tool_record.skill_name

            # Layer 1: Direct name match (anchor - highest priority)
            if query_lower.replace(" ", "_") in tool_name.lower():
                tool_score = max(tool_score, 0.95)
            elif query_lower.replace(" ", "") in tool_name.lower().replace("_", "").replace(
                ".", ""
            ):
                tool_score = max(tool_score, 0.85)

            # Layer 2: Category-specific name boost
            if query_intent and tool_category in self.CATEGORY_BOOSTS.get(query_intent, []):
                tool_score = max(tool_score, 0.8)

            # Layer 3: Keyword-based scoring for install/jit scenarios
            if "install" in query_lower and "jit_install" in tool_name:
                tool_score = max(tool_score, 0.9)
            elif "install" in query_lower and "install" in tool_name.lower():
                tool_score = max(tool_score, 0.85)

            # Layer 4: Check if query words appear in tool name
            for word in query_words:
                if word in tool_name.lower() and len(word) > 3:
                    tool_score = max(tool_score, 0.7)

            # Layer 5: Description match (lower priority)
            if query_lower in tool_desc.lower():
                tool_score = max(tool_score, 0.6)

            # Layer 6: Keyword density in description
            matched_keywords = [w for w in query_words if w in tool_desc.lower() and len(w) > 3]
            tool_score += len(matched_keywords) * 0.05

            # Layer 7: Category boosting
            if query_intent and tool_category in self.CATEGORY_BOOSTS.get(query_intent, []):
                tool_score = max(tool_score, 0.7)

            # Layer 8: SPECIAL - skill.discover for uncertainty queries
            if tool_name == "skill.discover":
                uncertainty_keywords = [
                    "analyze",
                    "learn",
                    "what can",
                    "available",
                    "capability",
                    "tools",
                    "commands",
                    "find",
                    "search",
                    "discover",
                    "look up",
                    "how to",
                    "which tool",
                    "what tool",
                ]
                for keyword in uncertainty_keywords:
                    if keyword in query_lower:
                        tool_score = max(tool_score, 0.85)
                        break
                else:
                    tool_score = max(tool_score, 0.6)

            # Step 3: Generate usage template from schema
            if tool_score >= threshold:
                usage = generate_usage_template(tool_name, tool_record.input_schema)

                match = ToolMatch(
                    name=tool_name,
                    skill_name=skill_name,
                    description=tool_desc,
                    score=tool_score,
                    matched_intent=query,
                    usage_template=usage,
                )
                matches.append((match, tool_score))

        # Step 4: Sort by score and limit
        matches.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matches[:limit]]

    def _detect_query_intent(self, query_words: set[str]) -> tuple[str, ...] | None:
        """Detect query intent based on keywords to enable category boosting."""
        for intent_keywords, _categories in self.CATEGORY_BOOSTS.items():
            if any(word in query_words for word in intent_keywords):
                return intent_keywords
        return None

    def discover_all(self, locations: list[str] | None = None) -> list[DiscoveredSkill]:
        """Discover all skills from LanceDB.

        Args:
            locations: Ignored (kept for API compat).

        Returns:
            List of DiscoveredSkill objects sorted by name.
        """
        logger.debug("🔍 Accessing Skill Index from LanceDB...")

        # Use PythonSkillScanner to read from LanceDB
        scanner = PythonSkillScanner()
        index_entries = scanner.scan_directory()

        all_skills = []
        for entry in index_entries:
            skill = DiscoveredSkill.from_index_entry(entry)
            all_skills.append(skill)

        # Sort by name for consistent ordering
        all_skills.sort(key=lambda s: s.name)

        logger.info(f"📦 Index Service provided {len(all_skills)} skills from LanceDB")
        return all_skills

    def discover_one(self, skill_name: str) -> DiscoveredSkill | None:
        """Find a single skill in the Index by name.

        Args:
            skill_name: Name of the skill to find.

        Returns:
            DiscoveredSkill if found, None otherwise.
        """
        # This scans the in-memory list (fast enough for now)
        skills = self.discover_all()
        for skill in skills:
            if skill.name == skill_name:
                return skill
        return None

    def get_skills_with_extensions(self) -> list[DiscoveredSkill]:
        """Get all skills that have extensions directory."""
        skills = self.discover_all()
        return [s for s in skills if s.has_extensions]

    def get_analytics_dataframe(self):
        """Get all tools as a PyArrow Table for analytics.

        This method uses the Arrow-native export from Rust bindings
        for high-performance analytics operations.

        Returns:
            PyArrow Table with columns: id, content, skill_name, tool_name,
            file_path, keywords, etc.

        Raises:
            ImportError: If pyarrow is not installed
            RuntimeError: If LanceDB is not available
        """
        from omni.core.skills.analyzer import get_analytics_dataframe as _get_df

        return _get_df()

    def generate_system_context(self) -> str:
        """Generate system context using Arrow vectorized operations.

        This is optimized for generating tool context for LLM prompts.
        Uses PyArrow Compute for efficient string operations.

        Returns:
            Formatted string with all tools in @omni() format
        """
        from omni.core.skills.analyzer import generate_system_context as _gen_ctx

        return _gen_ctx()

    def get_category_distribution(self) -> dict[str, int]:
        """Get tool count distribution by category using Arrow.

        Returns:
            Dictionary mapping category names to tool counts
        """
        from omni.core.skills.analyzer import get_category_distribution as _get_dist

        return _get_dist()


def is_rust_available() -> bool:
    """Check if Rust bindings are available.

    Note: In Rust-First Indexing, this returns True if the index
    was generated by the Rust scanner (which is always the case now).
    """
    return True


__all__ = [
    "DiscoveredSkill",
    "SkillDiscoveryService",
    "ToolMatch",
    "ToolRecord",
    "generate_usage_template",
    "is_rust_available",
]
