"""
sniffer.py - The Agnostic Sniffer (Hybrid Mode)

Asset-driven context detection with triple-mode support:
1. Static Rules: Fast file-based matching from SKILL.md
2. Dynamic Logic: Python functions from extensions/sniffer/*
3. Declarative Rules: TOML-based rules from rules.toml

Design Philosophy:
- Kernel provides the mechanism (rule evaluation + function execution)
- Assets provide the knowledge (file triggers + detection logic)
- Zero hardcoded file-to-skill mappings in src/

Migrated from: src/agent/core/router/sniffer.py
"""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.router.sniffer")

# Threshold for activating a skill based on dynamic sniffer score
SNIFTER_SCORE_THRESHOLD = 0.5


class ActivationRule:
    """Represents a skill activation rule (static file-based)."""

    def __init__(
        self,
        skill_name: str,
        files: list[str] | None = None,
        pattern: str | None = None,
    ):
        self.skill_name = skill_name
        self.files = set(files) if files else set()
        self.pattern = pattern  # Regex pattern for advanced matching

    def matches(self, cwd: str, root_files: set[str] | None = None) -> bool:
        """Check if this rule matches the given directory.

        Args:
            cwd: Current working directory
            root_files: Optional pre-computed set of files in cwd (for efficiency)
        """
        # File-based activation
        if self.files:
            if root_files is not None:
                return bool(self.files & root_files)
            try:
                root_files = set(os.listdir(cwd))
                return bool(self.files & root_files)
            except (OSError, PermissionError):
                return False

        # Pattern-based activation (e.g., ".*\\.py$")
        if self.pattern:
            import re

            try:
                regex = re.compile(self.pattern)
                for f in Path(cwd).rglob("*"):
                    if f.is_file() and regex.match(f.name):
                        return True
            except re.error:
                pass

        return False


class DynamicSniffer:
    """Represents a dynamic sniffer function from extensions/sniffer/*."""

    def __init__(
        self,
        func: Callable[[str], float],
        skill_name: str,
        name: str = "unknown",
        priority: int = 100,
    ):
        self.func = func
        self.skill_name = skill_name
        self.name = name
        self.priority = priority

    def check(self, cwd: str) -> float:
        """Execute the sniffer and return a score."""
        try:
            return self.func(cwd)
        except Exception as e:
            logger.warning(f"Sniffer '{self.name}' failed: {e}")
            return 0.0


class DeclarativeRule:
    """Represents a declarative rule from rules.toml."""

    def __init__(self, skill_name: str, rule_type: str, pattern: str):
        self.skill_name = skill_name
        self.rule_type = rule_type  # "file_exists" or "file_pattern"
        self.pattern = pattern

    def matches(self, cwd: str, root_files: set[str]) -> bool:
        """Check if rule matches in given directory."""
        if self.rule_type == "file_exists":
            # O(1) exact match
            return self.pattern in root_files
        elif self.rule_type == "file_pattern":
            # O(N) glob match
            for filename in root_files:
                if fnmatch.fnmatch(filename, self.pattern):
                    return True
            return False
        return False

    def __repr__(self) -> str:
        return f"DeclarativeRule({self.skill_name}, {self.rule_type}, {self.pattern})"


class IntentSniffer:
    """
    [The Hybrid Sniffer]

    Environment-agnostic skill activation detector with triple-mode support.

    Mode 1: Static Rules (from SKILL.md)
        - Fast file existence checks
        - Defined in activation.files field

    Mode 2: Dynamic Logic (from extensions/sniffer/*)
        - Custom Python detection functions
        - Returns score 0.0-1.0
        - Threshold: 0.5

    Mode 3: Declarative Rules (from rules.toml)
        - file_exists: Exact file match (O(1), fast)
        - file_pattern: Glob pattern matching (O(N), slower)

    Usage:
        sniffer = IntentSniffer()
        # Register static rule
        sniffer.register_rule(ActivationRule("python", files=["pyproject.toml"]))
        # Register dynamic sniffer
        sniffer.register_dynamic(DynamicSniffer(func, "python", name="venv_check"))
        # Register declarative rules from rules.toml
        sniffer.register_rules("python", [
            {"type": "file_exists", "pattern": "pyproject.toml"},
            {"type": "file_pattern", "pattern": "*.py"},
        ])
        suggestions = sniffer.sniff("/path/to/project")
    """

    def __init__(self):
        self._rules: list[ActivationRule] = []
        self._dynamic_sniffers: list[DynamicSniffer] = []
        self._declarative_rules: list[DeclarativeRule] = []
        self._cached_suggestions: dict[str, list[str]] = {}
        self._score_threshold: float = SNIFTER_SCORE_THRESHOLD

    @property
    def score_threshold(self) -> float:
        """Get the score threshold for activation."""
        return self._score_threshold

    @score_threshold.setter
    def score_threshold(self, value: float) -> None:
        """Set the score threshold for activation."""
        self._score_threshold = max(0.0, min(1.0, value))

    # === Static Rule Registration ===

    def register_rule(self, rule: ActivationRule) -> None:
        """Register a static activation rule."""
        self._rules.append(rule)
        logger.debug(f"Registered static rule for skill: {rule.skill_name}")

    def register_skill_activation(
        self, skill_name: str, files: list[str] | None = None, pattern: str | None = None
    ) -> None:
        """Convenience method to register a skill with file triggers."""
        rule = ActivationRule(skill_name=skill_name, files=files, pattern=pattern)
        self.register_rule(rule)

    # === Declarative Rule Registration ===

    def register_rules(self, skill_name: str, rules: list[dict[str, str]]) -> None:
        """Register declarative rules from rules.toml format.

        Args:
            skill_name: Name of the skill
            rules: List of rule dicts with 'type' and 'pattern' keys

        Example:
            sniffer.register_rules("python", [
                {"type": "file_exists", "pattern": "pyproject.toml"},
                {"type": "file_pattern", "pattern": "*.py"},
            ])
        """
        count = 0
        for rule in rules:
            rule_type = rule.get("type", "").strip()
            pattern = rule.get("pattern", "").strip()

            # Validate rule
            if rule_type not in ("file_exists", "file_pattern"):
                logger.warning(f"Unknown rule type '{rule_type}' for skill '{skill_name}'")
                continue

            if not pattern:
                logger.warning(f"Empty pattern in rule for skill '{skill_name}'")
                continue

            declarative_rule = DeclarativeRule(
                skill_name=skill_name,
                rule_type=rule_type,
                pattern=pattern,
            )
            self._declarative_rules.append(declarative_rule)
            count += 1

        if count > 0:
            logger.debug(f"Registered {count} declarative rules for skill '{skill_name}'")

    # === Index Reader Integration (Step 3) ===

    def clear_declarative_rules(self) -> None:
        """Clear all declarative rules (used for hot reload).

        This removes all registered declarative rules so they can be
        reloaded from the index without duplication.
        """
        count = len(self._declarative_rules)
        self._declarative_rules.clear()
        if count > 0:
            logger.debug(f"Cleared {count} declarative rules")

    def load_from_index(self, index_path: str | None = None) -> int:
        """Load rules from skill_index.json (Single Source of Truth).

        This method clears existing declarative rules before loading
        to support hot reload scenarios.

        Args:
            index_path: Optional path to skills-index.json

        Returns:
            Number of rules loaded
        """
        try:
            from omni.foundation.bridge.scanner import PythonSkillScanner

            # Clear existing rules to prevent duplication on reload
            self.clear_declarative_rules()

            scanner = PythonSkillScanner(index_path)
            skills = scanner.scan_directory()

            rules_loaded = 0
            for skill in skills:
                if skill.rules:
                    rule_dicts = [r.to_dict() for r in skill.rules]
                    self.register_rules(skill.skill_name, rule_dicts)
                    rules_loaded += len(rule_dicts)

            if rules_loaded > 0:
                logger.info(f"Loaded {rules_loaded} sniffer rules from index")
            else:
                logger.debug("No sniffing rules found in index")

            return rules_loaded

        except ImportError as e:
            logger.warning(f"Foundation scanner not available: {e}")
            return 0

    # === Dynamic Sniffer Registration ===

    def register_dynamic(
        self,
        func: Callable[[str], float],
        skill_name: str,
        name: str | None = None,
        priority: int = 100,
    ) -> None:
        """Register a dynamic sniffer function."""
        sniffer = DynamicSniffer(
            func=func,
            skill_name=skill_name,
            name=name or getattr(func, "__name__", "unknown"),
            priority=getattr(func, "_sniffer_priority", priority),
        )
        self._dynamic_sniffers.append(sniffer)
        logger.debug(f"Registered dynamic sniffer '{sniffer.name}' for skill: {skill_name}")

    def register_sniffer_func(self, func: Callable[[str], float], skill_name: str) -> None:
        """Register a sniffer function with metadata from @sniffer decorator."""
        name = getattr(func, "_sniffer_name", None) or getattr(func, "__name__", "unknown")
        priority = getattr(func, "_sniffer_priority", 100)
        self.register_dynamic(func, skill_name, name, priority)

    def register_sniffer_loaders(self, loaders: list[tuple[Callable[[str], float], str]]) -> None:
        """Register multiple sniffer functions from (func, skill_name) tuples."""
        for func, skill_name in loaders:
            self.register_sniffer_func(func, skill_name)

    # === Sniffing Operations ===

    def clear_cache(self) -> None:
        """Clear the suggestion cache."""
        self._cached_suggestions.clear()

    def sniff(self, cwd: str) -> list[str]:
        """Scan directory and return matching skill names.

        Args:
            cwd: Current working directory to analyze

        Returns:
            List of skill names that should be activated
        """
        # Check cache
        if cwd in self._cached_suggestions:
            return self._cached_suggestions[cwd].copy()

        active_skills: set[str] = set()

        # Get directory contents once (for efficiency)
        try:
            root_files = set(os.listdir(cwd))
        except (OSError, PermissionError) as e:
            logger.warning(f"Sniffer cannot read directory {cwd}: {e}")
            return []

        # Mode 1: Static file-based rules
        for rule in self._rules:
            try:
                if rule.matches(cwd, root_files):
                    active_skills.add(rule.skill_name)
                    logger.debug(f"👃 Static match: {rule.skill_name} in {cwd}")
            except Exception as e:
                logger.warning(f"Rule matching failed for {rule.skill_name}: {e}")

        # Mode 3: Declarative rules (from rules.toml)
        for rule in self._declarative_rules:
            try:
                if rule.matches(cwd, root_files):
                    active_skills.add(rule.skill_name)
                    logger.debug(
                        f"👃 Declarative match: {rule.skill_name} "
                        f"({rule.rule_type}: {rule.pattern})"
                    )
            except Exception as e:
                logger.warning(f"Declarative rule matching failed for {rule.skill_name}: {e}")

        # Mode 2: Dynamic sniffer functions
        for sniffer in self._dynamic_sniffers:
            try:
                score = sniffer.check(cwd)
                if score >= self._score_threshold:
                    active_skills.add(sniffer.skill_name)
                    logger.info(
                        f"👃 Dynamic Sniffer Triggered: {sniffer.skill_name} "
                        f"(score: {score:.2f}, sniffer: {sniffer.name})"
                    )
            except Exception as e:
                logger.warning(f"Sniffer '{sniffer.name}' execution failed: {e}")

        # Cache result
        result = list(active_skills)
        self._cached_suggestions[cwd] = result
        return result

    def sniff_with_scores(self, cwd: str) -> list[tuple[str, float]]:
        """Scan directory and return skill names with their activation scores.

        Args:
            cwd: Current working directory to analyze

        Returns:
            List of (skill_name, score) tuples, sorted by score descending
        """
        scores: dict[str, float] = {}

        # Get directory contents once (for efficiency)
        try:
            root_files = set(os.listdir(cwd))
        except (OSError, PermissionError):
            root_files = set()

        # Static rules contribute score 1.0
        for rule in self._rules:
            try:
                if rule.matches(cwd, root_files):
                    if rule.skill_name not in scores or scores[rule.skill_name] < 1.0:
                        scores[rule.skill_name] = 1.0
            except Exception:
                pass

        # Declarative rules contribute score 1.0
        for rule in self._declarative_rules:
            try:
                if rule.matches(cwd, root_files):
                    if rule.skill_name not in scores or scores[rule.skill_name] < 1.0:
                        scores[rule.skill_name] = 1.0
            except Exception:
                pass

        # Dynamic sniffers contribute their score
        for sniffer in self._dynamic_sniffers:
            try:
                score = sniffer.check(cwd)
                if score > scores.get(sniffer.skill_name, 0.0):
                    scores[sniffer.skill_name] = score
            except Exception:
                pass

        # Sort by score descending
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def sniff_file(self, file_path: str) -> list[str]:
        """Sniff a specific file path (static rules only).

        Args:
            file_path: Path to the file

        Returns:
            List of skill names that might handle this file
        """
        file_name = Path(file_path).name
        active_skills: set[str] = set()

        for rule in self._rules:
            if file_name in rule.files:
                active_skills.add(rule.skill_name)

        return list(active_skills)


class ContextualSniffer:
    """
    [Enhanced Sniffer with Session Memory]

    Extends IntentSniffer to remember context across a session.
    Useful for maintaining state between commands.
    """

    def __init__(self):
        self._sniffer = IntentSniffer()
        self._session_context: dict[str, Any] = {}
        self._last_suggestions: list[str] = []

    # Delegate static rule registration
    def register_rule(self, rule: ActivationRule) -> None:
        self._sniffer.register_rule(rule)

    def register_skill_activation(
        self, skill_name: str, files: list[str] | None = None, pattern: str | None = None
    ) -> None:
        self._sniffer.register_skill_activation(skill_name, files, pattern)

    # Delegate dynamic sniffer registration
    def register_dynamic(
        self,
        func: Callable[[str], float],
        skill_name: str,
        name: str | None = None,
        priority: int = 100,
    ) -> None:
        self._sniffer.register_dynamic(func, skill_name, name, priority)

    def register_sniffer_func(self, func: Callable[[str], float], skill_name: str) -> None:
        self._sniffer.register_sniffer_func(func, skill_name)

    def update_session(self, key: str, value: Any) -> None:
        """Update session context."""
        self._session_context[key] = value

    def get_session(self, key: str, default: Any = None) -> Any:
        """Get from session context."""
        return self._session_context.get(key, default)

    def sniff(self, cwd: str) -> list[str]:
        """Sniff with session memory."""
        suggestions = self._sniffer.sniff(cwd)

        # Boost previously used skills
        last_used = self.get_session("last_used_skill")
        if last_used and last_used not in suggestions:
            suggestions.insert(0, last_used)

        self._last_suggestions = suggestions
        return suggestions

    def mark_used(self, skill: str) -> None:
        """Mark a skill as used in this session."""
        self.update_session("last_used_skill", skill)


__all__ = [
    "SNIFTER_SCORE_THRESHOLD",
    "ActivationRule",
    "ContextualSniffer",
    "DeclarativeRule",
    "DynamicSniffer",
    "IntentSniffer",
]
