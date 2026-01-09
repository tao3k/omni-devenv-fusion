"""
agent/core/security/structure_validator.py
Skill Structure Validator (ODF-EP v7.0)

Enforces skill structure defined in assets/settings.yaml.
Ensures all skills conform to the canonical structure.

Usage:
    from agent.core.security.structure_validator import SkillStructureValidator

    validator = SkillStructureValidator()
    validator.validate_all_skills()  # Validate all skills
    validator.validate_skill("git")  # Validate specific skill
"""

from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum
import yaml
import json

from structlog import get_logger

logger = get_logger()


class FileType(Enum):
    """Type of file specification."""

    FILE = "file"
    DIR = "dir"


@dataclass
class FileSpec:
    """Specification for a file or directory in skill structure."""

    path: str
    description: str
    type: FileType


@dataclass
class ValidationResult:
    """Result of structure validation."""

    skill_name: str
    valid: bool
    missing_required: List[str]
    ghost_files: List[str]
    disallowed_files: List[str]  # New: forbidden files that must not exist
    warnings: List[str]
    score: float  # 0-100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill": self.skill_name,
            "valid": self.valid,
            "missing_required": self.missing_required,
            "ghost_files": self.ghost_files,
            "disallowed_files": self.disallowed_files,
            "warnings": self.warnings,
            "score": self.score,
        }


class SkillStructureValidator:
    """
    Enforces the skill structure defined in settings.yaml.

    Validates:
    1. Required files exist
    2. No unauthorized "ghost files"
    3. Directory structure matches spec
    """

    def __init__(
        self,
        settings_path: Optional[Path] = None,
        skills_dir: Optional[Path] = None,
    ):
        """
        Initialize validator with configuration.

        Args:
            settings_path: Path to settings.yaml (default: assets/settings.yaml)
            skills_dir: Path to skills directory (default: assets/skills)
        """
        # Default paths
        project_root = self._find_project_root()
        self.settings_path = settings_path or project_root / "assets" / "settings.yaml"
        self.skills_dir = skills_dir or project_root / "assets" / "skills"

        # Load configuration
        self.config = self._load_config()

        # Build allowed paths set
        self._allowed_paths = self._build_allowed_paths()

        logger.info(
            "structure_validator_initialized",
            settings=self.settings_path,
            skills_dir=self.skills_dir,
            required_count=len(self.config["structure"].get("required", [])),
            default_count=len(self.config["structure"].get("default", [])),
        )

    def _find_project_root(self) -> Path:
        """Find project root by looking for .git (project root marker) or pyproject.toml."""
        import os

        # Start from current file's package location
        package_dir = (
            Path(__file__).resolve().parent.parent.parent
        )  # agent/core/security -> agent -> packages/python/agent

        # Priority 1: Look for .git (more reliable for project root)
        for parent in list(package_dir.parents) + [package_dir]:
            if (parent / ".git").exists():
                return parent

        # Priority 2: Look for pyproject.toml (might be sub-package)
        for parent in list(package_dir.parents) + [package_dir]:
            if (parent / "pyproject.toml").exists():
                return parent

        # Fallback to cwd
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".git").exists():
                return parent

        return package_dir  # Return package dir as last resort

    def _load_config(self) -> Dict[str, Any]:
        """Load skill_architecture configuration from settings.yaml."""
        with open(self.settings_path) as f:
            data = yaml.safe_load(f)

        # Try new path first (skills.architecture), fall back to old (skill_architecture)
        config = data.get("skills", {}).get("architecture", {})
        if not config:
            config = data.get("skill_architecture", {})

        if not config:
            logger.warning("no_skill_architecture_config", path=self.settings_path)
            # Return minimal default config
            return {
                "version": "v2.0",
                "definition_file": "SKILL.md",
                "structure": {
                    "required": [
                        {"path": "SKILL.md", "description": "Skill metadata", "type": "file"}
                    ],
                    "optional": [],
                },
                "validation": {"block_on_invalid": False, "allow_ghost_files": True},
            }

        return config

    def _build_allowed_paths(self) -> set:
        """Build set of allowed paths from config (required + default = allowed)."""
        paths = set()

        # Required files/dirs
        for spec in self.config["structure"].get("required", []):
            paths.add(spec["path"].rstrip("/"))

        # Default files/dirs (optional but allowed)
        for spec in self.config["structure"].get("default", []):
            path = spec["path"].rstrip("/")
            paths.add(path)
            if spec.get("type") == "dir":
                paths.add(f"{path}/.gitkeep")

        return paths

    def _parse_file_spec(self, spec: Dict) -> FileSpec:
        """Parse a file specification from config."""
        return FileSpec(
            path=spec["path"],
            description=spec.get("description", ""),
            type=FileType(spec.get("type", "file")),
        )

    def validate_skill(self, skill_name: str) -> ValidationResult:
        """
        Validate a single skill directory against the spec.

        Args:
            skill_name: Name of the skill to validate

        Returns:
            ValidationResult with validation details
        """
        skill_dir = self.skills_dir / skill_name

        if not skill_dir.exists():
            return ValidationResult(
                skill_name=skill_name,
                valid=False,
                missing_required=[],
                ghost_files=[],
                disallowed_files=[],
                warnings=[f"Skill directory does not exist: {skill_dir}"],
                score=0,
            )

        missing_required = []
        ghost_files = []
        disallowed_files = []
        warnings = []

        # Check required files
        for spec in self.config["structure"].get("required", []):
            file_spec = self._parse_file_spec(spec)
            target = skill_dir / file_spec.path
            if not target.exists():
                missing_required.append(file_spec.path)

        # Check for disallowed files (must not exist - causes LLM confusion)
        disallowed = self.config.get("validation", {}).get("disallowed_files", [])
        for filename in disallowed:
            if (skill_dir / filename).exists():
                disallowed_files.append(filename)

        # Check for ghost files (non-standard files)
        allow_ghost = self.config.get("validation", {}).get("allow_ghost_files", True)

        for item in skill_dir.iterdir():
            if item.name.startswith("."):
                continue  # Skip hidden files
            if item.name == "__pycache__":
                continue
            if item.name == ".gitkeep":
                continue
            if item.name in disallowed:
                continue  # Already reported as disallowed

            # Normalize path for comparison
            item_path = item.name if item.is_file() else f"{item.name}/"
            normalized = item.name if item.is_dir() else item.name

            if normalized not in self._allowed_paths:
                if not allow_ghost:
                    ghost_files.append(item.name)
                else:
                    warnings.append(f"Non-standard file detected: {item.name}")

        # Calculate score
        total_required = len(self.config["structure"].get("required", []))
        missing_count = len(missing_required)
        score = (
            max(0, ((total_required - missing_count) / total_required) * 100)
            if total_required > 0
            else 100
        )

        # Disallowed files make skill invalid
        if disallowed_files:
            score = max(0, score - 20)  # Penalty for disallowed files

        # Determine validity
        block_on_invalid = self.config.get("validation", {}).get("block_on_invalid", False)
        valid = (
            len(missing_required) == 0
            and (allow_ghost or len(ghost_files) == 0)
            and len(disallowed_files) == 0
        )

        if not valid:
            logger.warning(
                "skill_structure_invalid",
                skill=skill_name,
                missing=missing_required,
                ghosts=ghost_files if not allow_ghost else [],
                disallowed=disallowed_files,
            )
        else:
            logger.debug(
                "skill_structure_valid",
                skill=skill_name,
                score=score,
            )

        return ValidationResult(
            skill_name=skill_name,
            valid=valid,
            missing_required=missing_required,
            ghost_files=ghost_files,
            disallowed_files=disallowed_files,
            warnings=warnings,
            score=score,
        )

    def validate_all_skills(self) -> List[ValidationResult]:
        """
        Validate all skills in the skills directory.

        Returns:
            List of ValidationResult for each skill
        """
        results = []

        if not self.skills_dir.exists():
            logger.error("skills_dir_not_found", path=self.skills_dir)
            return results

        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            result = self.validate_skill(skill_dir.name)
            results.append(result)

        # Summary log
        valid_count = sum(1 for r in results if r.valid)
        total_count = len(results)

        logger.info(
            "all_skills_validated",
            total=total_count,
            valid=valid_count,
            invalid=total_count - valid_count,
        )

        return results

    def get_validation_report(self) -> Dict[str, Any]:
        """
        Get a detailed validation report for all skills.

        Returns:
            Dict with summary and per-skill results
        """
        results = self.validate_all_skills()

        return {
            "summary": {
                "total_skills": len(results),
                "valid_skills": sum(1 for r in results if r.valid),
                "invalid_skills": sum(1 for r in results if not r.valid),
                "average_score": sum(r.score for r in results) / len(results) if results else 0,
                "config_version": self.config.get("version", "unknown"),
            },
            "skills": [r.to_dict() for r in results],
        }

    def validate_skill_sync(self, skill_name: str) -> bool:
        """
        Quick sync check if a skill is valid.

        Args:
            skill_name: Name of the skill

        Returns:
            True if skill structure is valid
        """
        result = self.validate_skill(skill_name)
        return result.valid


# Convenience function for skill check tool
def check_skills() -> Dict[str, Any]:
    """
    Quick check all skills and return summary.

    Usage:
        result = check_skills()
        print(f"Valid: {result['summary']['valid_skills']}/{result['summary']['total_skills']}")
    """
    validator = SkillStructureValidator()
    return validator.get_validation_report()


__all__ = [
    "SkillStructureValidator",
    "StructureValidator",
    "ValidationResult",
    "FileSpec",
    "FileType",
    "check_skills",
]
