"""
omni.core.skills - Skills System

Provides skill management:
- registry: Skill discovery and metadata
- runtime: Skill execution context
- discovery: Skill finder
- memory: Skill memory management
- extensions: Extension loading system
- script_loader: Script loading with auto-wiring
- universal: Zero-Code Skill container

Usage:
    from omni.core.skills.runtime import get_skill_context
    from omni.core.skills.registry import SkillRegistry
    from omni.core.skills.discovery import SkillDiscovery
    from omni.core.skills.memory import SkillMemory
    from omni.core.skills.universal import UniversalScriptSkill
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
from .registry import (
    SkillRegistry,
    discover_skills,
    get_skill_registry,
    get_skill_tools,
    install_remote_skill,
    jit_install_skill,
    list_installed_skills,
    security_scan_skill,
    suggest_skills_for_task,
    update_remote_skill,
)

# Runtime module
from .runtime import (
    SkillContext,
    SkillManager,
    get_skill_context,
    get_skill_manager,
    reset_context,
    run_command,
)

# Script loader module
from .script_loader import (
    ScriptLoader,
    SkillScriptLoader,
    create_script_loader,
    skill_command,
)

# Universal skill module
from .universal import (
    UniversalScriptSkill,
    UniversalSkillFactory,
    create_skill_from_assets,
    create_universal_skill,
)

__all__ = [
    # Registry
    "SkillRegistry",
    "get_skill_registry",
    "install_remote_skill",
    "update_remote_skill",
    "jit_install_skill",
    "security_scan_skill",
    "discover_skills",
    "suggest_skills_for_task",
    "list_installed_skills",
    "get_skill_tools",
    # Runtime
    "SkillContext",
    "SkillManager",
    "get_skill_context",
    "get_skill_manager",
    "reset_context",
    "run_command",
    # Discovery
    "SkillDiscoveryService",
    "DiscoveredSkill",
    "is_rust_available",
    # Memory
    "SkillMemory",
    "get_skill_memory",
    # Extensions
    "SkillExtensionLoader",
    "ExtensionWrapper",
    "get_extension_loader",
    # Script Loader
    "ScriptLoader",
    "SkillScriptLoader",
    "create_script_loader",
    "skill_command",
    # Universal
    "UniversalScriptSkill",
    "UniversalSkillFactory",
    "create_universal_skill",
    "create_skill_from_assets",
]
