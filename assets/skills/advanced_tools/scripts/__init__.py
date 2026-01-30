"""
advanced_tools/scripts - High-Performance Toolchain

Commands organized by responsibility:
- search.py: Fast search (rg) and find (fd)
- mutation.py: Stream editing (sed)

Philosophy:
- Modern Rust-based tools for performance
- Zero config: Environment PATH is the source of truth
- Security: All operations constrained to ConfigPaths.project_root
"""

# Re-export all commands for skill loader
from .mutation import regex_replace
from .search import smart_find, smart_search

__all__ = [
    "regex_replace",
    "smart_find",
    "smart_search",
]
