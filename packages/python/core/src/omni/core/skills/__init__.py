"""
omni.core.skills - Skills System

Provides skill management:
- registry: Skill discovery and metadata
- runtime: Skill execution context
- discovery: Skill finder
- memory: Skill memory management (Rust-Native Context Hydration)
- extensions: Extension loading system
- tools_loader: Script loading with auto-wiring
- universal: Zero-Code Skill container
- index_loader: Rust-generated skill index loader
- file_cache: Thread-safe file content cache
- ref_parser: required_refs parser
- hydrator: Context assembly for LLM
- indexer: Skill Indexing Pipeline (Rust Scan -> Embed -> Store)
- registry.holographic: Holographic Registry (virtual, LanceDB-backed)

Usage:
    from omni.core.skills.runtime import get_skill_context
    from omni.core.skills.registry import SkillRegistry
    from omni.core.skills.discovery import SkillDiscovery
    from omni.core.skills.memory import SkillMemory
    from omni.core.skills.universal import UniversalScriptSkill
    from omni.core.skills.indexer import SkillIndexer
    from omni.core.skills.registry.holographic import HolographicRegistry

    # Context Hydration (Rust-Native)
    from omni.core.skills import get_skill_memory
    memory = get_skill_memory()
    context = memory.hydrate_skill_context("researcher")
"""

# Registry module (thin client - simplified)
# Discovery module
from .discovery import (
    DiscoveredSkill,
    SkillDiscoveryService,
    is_rust_available,
)

# Extensions module
from .extensions import (
    ExtensionWrapper,
    SkillExtensionLoader,
    get_extension_loader,
)

# Memory module
from .memory import SkillMemory, get_skill_memory

# Context Hydration modules (Rust-Native)
from .index_loader import SkillIndexLoader
from .file_cache import FileCache
from .ref_parser import RefParser
from .hydrator import ContextHydrator

from .registry import (
    SkillRegistry,
    get_skill_registry,
    # Holographic Registry
    HolographicRegistry,
    ToolMetadata,
    LazyTool,
)

# Runtime module
from .runtime import (
    SkillContext,
    SkillManager,
    get_skill_context,
    reset_context,
    run_command,
)

# Tools loader module
from .tools_loader import (
    ToolsLoader,
    create_tools_loader,
    _skill_command_registry,
)

# Universal skill module
from .universal import (
    UniversalScriptSkill,
    UniversalSkillFactory,
    create_skill_from_assets,
    create_universal_skill,
)

# Unified skill run (fast path + kernel fallback)
from .runner import FastPathUnavailable, run_skill, run_skill_with_monitor

# Indexer module
from .indexer import SkillIndexer

__all__ = [
    # Registry
    "SkillRegistry",
    "get_skill_registry",
    # Holographic Registry
    "HolographicRegistry",
    "ToolMetadata",
    "LazyTool",
    # Runtime
    "SkillContext",
    "SkillManager",
    "get_skill_context",
    "reset_context",
    "run_command",
    # Discovery
    "SkillDiscoveryService",
    "DiscoveredSkill",
    "is_rust_available",
    # Memory
    "SkillMemory",
    "get_skill_memory",
    # Context Hydration (Rust-Native)
    "SkillIndexLoader",
    "FileCache",
    "RefParser",
    "ContextHydrator",
    # Extensions
    "SkillExtensionLoader",
    "ExtensionWrapper",
    "get_extension_loader",
    # Tools Loader
    "ToolsLoader",
    "create_tools_loader",
    "_skill_command_registry",
    # Universal
    "UniversalScriptSkill",
    "UniversalSkillFactory",
    "create_universal_skill",
    "create_skill_from_assets",
    # Runner (unified run: fast path + kernel fallback)
    "run_skill",
    "run_skill_with_monitor",
    "FastPathUnavailable",
    # Indexer
    "SkillIndexer",
]
