# Common package for omni-dev-fusion

# Defer expensive imports for faster module load
# importlib.metadata.version() takes ~70ms - defer until actually needed

_cached_version: str | None = None


def _get_version() -> str:
    """Lazy version lookup - called on first access."""
    global _cached_version
    if _cached_version is None:
        from importlib.metadata import version, PackageNotFoundError

        try:
            _cached_version = version("omni-dev-fusion-common")
        except PackageNotFoundError:
            _cached_version = "0.0.0-dev"
    return _cached_version


def __getattr__(name: str):
    """Lazy module attributes - defer expensive lookups."""
    if name == "__version__":
        return _get_version()

    # Lazy load skill_utils to avoid circular imports
    if name in (
        "current_skill_dir",
        "skill_path",
        "skill_asset",
        "skill_script",
        "skill_reference",
        "skill_data",
    ):
        from . import skill_utils

        return getattr(skill_utils, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
