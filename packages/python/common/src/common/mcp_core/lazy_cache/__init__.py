"""
lazy_cache - Modular lazy loading cache system.

Phase 29: Protocol-based design with slots=True.

Modules:
- base.py: LazyCacheBase abstract class
- file_cache.py: FileCache for file content caching
- markdown_cache.py: MarkdownCache for markdown parsing
- config_cache.py: ConfigCache for configuration files
- repomix_cache.py: RepomixCache for LLM context

Usage:
    from mcp_core.lazy_cache import FileCache, MarkdownCache, ConfigCache

    # File content caching
    cache = FileCache(Path("path/to/file.txt"))
    content = cache.get()

    # Markdown parsing with sections
    md_cache = MarkdownCache(Path("path/to/doc.md"))
    data = md_cache.get()  # {"title": "...", "content": "...", "sections": {...}}

    # Config file caching (auto-detects format)
    config_cache = ConfigCache(Path("cog.toml"))
    config = config_cache.get()

    # Repomix context caching for skills
    from mcp_core.lazy_cache import RepomixCache
    repomix = RepomixCache(target_path=skill_dir)
    xml = repomix.get()
"""

from .base import LazyCacheBase
from .file_cache import FileCache
from .markdown_cache import MarkdownCache
from .config_cache import ConfigCache
from .repomix_cache import RepomixCache

__all__ = [
    "LazyCacheBase",
    "FileCache",
    "MarkdownCache",
    "ConfigCache",
    "RepomixCache",
]
