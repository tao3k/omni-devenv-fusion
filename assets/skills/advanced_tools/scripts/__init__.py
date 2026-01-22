"""
advanced_tools/scripts - High-Performance Toolchain

Commands organized by responsibility:
- search.py: Fast search (rg) and find (fd)
- fs.py: Directory tree visualization (tree)
- mutation.py: Stream editing (sed)

Philosophy:
- Modern Rust-based tools for performance
- Zero config: Environment PATH is the source of truth
- Security: All operations constrained to ConfigPaths.project_root
"""

# Re-export all commands for skill loader
from .search import smart_search, smart_find
from .fs import tree_view
from .mutation import regex_replace

__all__ = [
    "smart_search",
    "smart_find",
    "tree_view",
    "regex_replace",
]
