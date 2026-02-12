# harvested.py
"""
Harvested Knowledge Utilities.

Manages harvested knowledge entries from references.yaml.

Usage:
    >>> from omni.foundation.config.harvested import get_harvest_dir
    >>> get_harvest_dir()
    >>> # Returns: /project/assets/knowledge/harvested
    >>> get_harvest_dir("patterns")
    >>> # Returns: /project/assets/knowledge/harvested/patterns
"""

from pathlib import Path


def get_harvest_dir(category: str = "") -> Path:
    """Get the harvested knowledge directory path.

    Reads from merged reference config
    (`$PRJ_CONFIG_HOME/omni-dev-fusion/references.yaml`)
    via `ReferenceLibrary` -> `harvested_knowledge.dir`.

    Args:
        category: Optional category subdirectory (e.g., "patterns", "solutions")

    Returns:
        Path to assets/knowledge/harvested or assets/knowledge/harvested/{category}

    Usage:
        >>> from omni.foundation.config.harvested import get_harvest_dir
        >>> get_harvest_dir()
        >>> # Returns: /project/assets/knowledge/harvested
        >>> get_harvest_dir("patterns")
        >>> # Returns: /project/assets/knowledge/harvested/patterns
    """
    from omni.foundation.services.reference import get_reference_path

    harvest_base = get_reference_path("harvested_knowledge.dir")
    if category:
        return Path(harvest_base) / category
    return Path(harvest_base)


def get_harvest_file(category: str, filename: str) -> Path:
    """Get a file path in the harvested knowledge directory.

    Args:
        category: Category subdirectory (e.g., "patterns")
        filename: File name (e.g., "20260204-patterns-anthropic-skills.md")

    Returns:
        Full path to the file

    Usage:
        >>> from omni.foundation.config.harvested import get_harvest_file
        >>> get_harvest_file("patterns", "my-pattern.md")
        >>> # Returns: /project/assets/knowledge/harvested/patterns/my-pattern.md
    """
    return get_harvest_dir(category) / filename


__all__ = [
    "get_harvest_dir",
    "get_harvest_file",
]
