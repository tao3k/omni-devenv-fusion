"""Router configuration schema and loader.

This module defines the runtime configuration contract for router search behavior.
It centralizes settings access and validation to keep OmniRouter initialization clean.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omni.foundation.config.settings import get_setting, get_settings


class RouterConfidenceProfile(BaseModel):
    """Validated confidence profile values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    high_threshold: float = Field(0.75, ge=0.0, le=1.0)
    medium_threshold: float = Field(0.5, ge=0.0, le=1.0)
    high_base: float = Field(0.90, ge=0.0, le=1.0)
    high_scale: float = Field(0.05, ge=0.0, le=1.0)
    high_cap: float = Field(0.99, ge=0.0, le=1.0)
    medium_base: float = Field(0.60, ge=0.0, le=1.0)
    medium_scale: float = Field(0.30, ge=0.0, le=1.0)
    medium_cap: float = Field(0.89, ge=0.0, le=1.0)
    low_floor: float = Field(0.10, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_profile(self) -> "RouterConfidenceProfile":
        if self.high_threshold < self.medium_threshold:
            raise ValueError("profile.high_threshold must be >= profile.medium_threshold")
        if self.high_cap < self.high_base:
            raise ValueError("profile.high_cap must be >= profile.high_base")
        if self.medium_cap < self.medium_base:
            raise ValueError("profile.medium_cap must be >= profile.medium_base")
        return self


def _default_profiles() -> dict[str, dict[str, float]]:
    return {
        "balanced": {
            "high_threshold": 0.75,
            "medium_threshold": 0.50,
            "high_base": 0.90,
            "high_scale": 0.05,
            "high_cap": 0.99,
            "medium_base": 0.60,
            "medium_scale": 0.30,
            "medium_cap": 0.89,
            "low_floor": 0.10,
        },
        "precision": {
            "high_threshold": 0.82,
            "medium_threshold": 0.58,
            "high_base": 0.92,
            "high_scale": 0.04,
            "high_cap": 0.99,
            "medium_base": 0.62,
            "medium_scale": 0.24,
            "medium_cap": 0.88,
            "low_floor": 0.10,
        },
        "recall": {
            "high_threshold": 0.68,
            "medium_threshold": 0.42,
            "high_base": 0.88,
            "high_scale": 0.06,
            "high_cap": 0.99,
            "medium_base": 0.56,
            "medium_scale": 0.35,
            "medium_cap": 0.90,
            "low_floor": 0.08,
        },
    }


class RouterSearchConfig(BaseModel):
    """Validated router search configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    active_profile: str = "balanced"
    auto_profile_select: bool = True
    profiles: dict[str, RouterConfidenceProfile] = Field(default_factory=_default_profiles)
    default_limit: int = Field(10, ge=1)
    default_threshold: float = Field(0.2, ge=0.0, le=1.0)
    rerank: bool = True
    semantic_weight: float = Field(0.7, ge=0.0, le=1.0)
    keyword_weight: float = Field(0.3, ge=0.0, le=1.0)
    adaptive_threshold_step: float = Field(0.15, ge=0.0, le=1.0)
    adaptive_max_attempts: int = Field(3, ge=1)

    @model_validator(mode="after")
    def _validate_threshold_order(self) -> "RouterSearchConfig":
        if not self.profiles:
            raise ValueError("router.search.profiles must not be empty")
        if self.active_profile not in self.profiles:
            raise ValueError(
                "router.search.active_profile must reference an existing entry "
                "in router.search.profiles"
            )
        return self

    @property
    def active_confidence_profile(self) -> RouterConfidenceProfile:
        """Return the selected confidence profile."""
        return self.profiles[self.active_profile]


def load_router_search_config(
    *,
    semantic_weight: float | None = None,
    keyword_weight: float | None = None,
    adaptive_threshold_step: float | None = None,
    adaptive_max_attempts: int | None = None,
) -> RouterSearchConfig:
    """Load and validate router search settings.

    Explicit arguments override settings values.
    """

    return RouterSearchConfig(
        active_profile=str(get_setting("router.search.active_profile", "balanced")),
        auto_profile_select=bool(get_setting("router.search.auto_profile_select", True)),
        profiles=get_setting("router.search.profiles", _default_profiles()),
        default_limit=int(get_setting("router.search.default_limit", 10)),
        default_threshold=float(get_setting("router.search.default_threshold", 0.2)),
        rerank=bool(get_setting("router.search.rerank", True)),
        semantic_weight=(
            float(get_setting("router.search.semantic_weight", 0.7))
            if semantic_weight is None
            else semantic_weight
        ),
        keyword_weight=(
            float(get_setting("router.search.keyword_weight", 0.3))
            if keyword_weight is None
            else keyword_weight
        ),
        adaptive_threshold_step=(
            float(get_setting("router.search.adaptive_threshold_step", 0.15))
            if adaptive_threshold_step is None
            else adaptive_threshold_step
        ),
        adaptive_max_attempts=(
            int(get_setting("router.search.adaptive_max_attempts", 3))
            if adaptive_max_attempts is None
            else adaptive_max_attempts
        ),
    )


def router_search_json_schema() -> dict:
    """Export JSON schema for router search settings."""
    return RouterSearchConfig.model_json_schema()


# Default schema file in packages/shared (SSOT for router search config schema).
_SHARED_ROUTER_SEARCH_CONFIG_SCHEMA = (
    "packages/shared/schemas/omni.router.search_config.v1.schema.json"
)


def resolve_router_schema_path(schema_path: str | Path | None = None) -> Path:
    """Resolve path to router search config schema file.

    Priority:
    1. Explicit `schema_path` argument
    2. `router.search.schema_file` from merged settings
    3. Default: project root's packages/shared/schemas/omni.router.search_config.v1.schema.json

    Paths starting with "packages/shared/" are resolved relative to project root;
    other relative paths are resolved relative to conf_dir (--conf).
    """
    if schema_path is not None:
        return Path(schema_path)

    configured = get_setting(
        "router.search.schema_file",
        _SHARED_ROUTER_SEARCH_CONFIG_SCHEMA,
    )
    configured_path = Path(str(configured))
    if configured_path.is_absolute():
        return configured_path
    # SSOT: resolve packages/shared/... relative to project root
    if str(configured_path).replace("\\", "/").startswith("packages/shared/"):
        from omni.foundation.runtime.gitops import get_project_root

        return get_project_root() / configured_path
    conf_dir = Path(get_settings().conf_dir)
    return conf_dir / configured_path


def write_router_search_json_schema(schema_path: str | Path | None = None) -> Path:
    """Write router search JSON schema to config home (or explicit path)."""
    output = resolve_router_schema_path(schema_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(router_search_json_schema(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
