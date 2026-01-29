"""
kernel/engine.py - Core Agent Engine

Trinity Architecture - Core Layer

Single entry point for agent core, providing:
- Unified lifecycle management
- Component registry
- Dependency injection
- Clean separation between core and domain modules
- Zero-Code skill loading via UniversalScriptSkill
- Hot Reload for skill development

Logging: Uses Foundation layer (omni.foundation.config.logging)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from omni.foundation.config.logging import configure_logging, get_logger
from omni.foundation.config.skills import SKILLS_DIR

from .lifecycle import LifecycleManager, LifecycleState
from .watcher import RustKernelWatcher
from .reactor import get_reactor, EventTopic

if TYPE_CHECKING:
    from omni.core.router.sniffer import IntentSniffer
    from omni.core.security import SecurityValidator
    from omni.core.skills.runtime import SkillContext

# Ensure logging is configured before getting logger
configure_logging(level="INFO")
logger = get_logger("omni.core.kernel")

# Global kernel singleton
_kernel_instance: Kernel | None = None


class Kernel:
    """Kernel - single entry point for agent core.

    Responsibilities:
    - Lifecycle management (init -> ready -> running -> shutdown)
    - Component registry for dependency injection
    - Clean separation between core and domain modules
    - Bridge to existing skill_runtime system
    - Rust-powered skill discovery integration
    - Hot Reload for skill development
    - Security Enforcement (Permission Gatekeeper)

    Usage:
        kernel = get_kernel()
        await kernel.initialize()
        await kernel.start()
        # Secure execution:
        await kernel.execute_tool("filesystem.read_files", {"path": "..."}, caller="calculator")
        await kernel.shutdown()
    """

    __slots__ = (
        "_background_tasks",  # Track background tasks for cleanup
        "_components",
        "_discovered_skills",
        "_discovery_service",
        "_lifecycle",
        "_project_root",
        "_reactor",  # Event-driven reactor for reactive architecture
        "_router",
        "_security",  # Security Validator (Permission Gatekeeper)
        "_skill_context",
        "_skills_dir",
        "_sniffer",  # Intent Sniffer for context detection
        "_watcher",
    )

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        skills_dir: Path | None = None,
    ) -> None:
        """Initialize kernel with optional paths.

        Args:
            project_root: Project root directory (auto-detected if None)
            skills_dir: Skills directory (defaults to project_root/assets/skills)
        """
        self._lifecycle = LifecycleManager(
            on_ready=self._on_ready,
            on_running=self._on_running,
            on_shutdown=self._on_shutdown,
        )
        self._components: dict[str, Any] = {}
        self._skill_context: SkillContext | None = None
        self._discovery_service = None
        self._discovered_skills: list[Any] = []
        self._watcher: RustKernelWatcher | None = None
        self._router = None
        self._sniffer: IntentSniffer | None = None  # Lazy init in sniffer property
        self._security = None  # Security Validator (Permission Gatekeeper) - lazy init
        self._reactor = None  # Event-driven reactor - initialized in _on_ready
        self._background_tasks: set[asyncio.Task] = set()

        # Resolve paths
        from omni.foundation.runtime.gitops import get_project_root

        self._project_root = project_root or get_project_root()
        self._skills_dir = skills_dir or SKILLS_DIR()

    # =========================================================================
    # Lifecycle
    # =========================================================================

    @property
    def state(self) -> LifecycleState:
        """Get current lifecycle state."""
        return self._lifecycle.state

    @property
    def is_ready(self) -> bool:
        """Check if kernel is ready."""
        return self._lifecycle.is_ready()

    @property
    def is_running(self) -> bool:
        """Check if kernel is running."""
        return self._lifecycle.is_running()

    async def initialize(self) -> None:
        """Initialize kernel and all components."""
        await self._lifecycle.initialize()

    async def start(self) -> None:
        """Start kernel (transition to running state)."""
        await self._lifecycle.start()

    async def shutdown(self) -> None:
        """Shutdown kernel and cleanup all components."""
        await self._lifecycle.shutdown()

    # =========================================================================
    # Components
    # =========================================================================

    def register_component(self, name: str, component: Any) -> None:
        """Register a component by name.

        Args:
            name: Component name
            component: Component instance

        Raises:
            ValueError: If component already registered
        """
        if name in self._components:
            raise ValueError(f"Component '{name}' already registered")
        self._components[name] = component

    def get_component(self, name: str) -> Any:
        """Get a registered component.

        Args:
            name: Component name

        Returns:
            Component instance

        Raises:
            KeyError: If component not found
        """
        return self._components[name]

    def has_component(self, name: str) -> bool:
        """Check if a component is registered."""
        return name in self._components

    # =========================================================================
    # Security (Permission Gatekeeper)
    # =========================================================================

    @property
    def security(self) -> SecurityValidator:
        """Get the Security Validator (Permission Gatekeeper).

        Uses Rust-powered PermissionGatekeeper for high-performance checks.
        Lazy initialization to avoid startup overhead.
        """
        if self._security is None:
            from omni.core.security import SecurityValidator

            self._security = SecurityValidator()
        return self._security

    async def execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        caller: str | None = None,
    ) -> Any:
        """
        Execute a tool with mandatory security checks.

        This is the primary entry point for all skill-to-skill and agent-to-skill calls.
        All tool invocations must pass through this method for proper permission enforcement.

        Args:
            tool_name: Full tool name in format "skill.command" (e.g., "filesystem.read_files")
            args: Tool arguments as a dictionary
            caller: Name of the calling skill (e.g., "calculator"). None = Root/User (full access)

        Returns:
            Tool execution result (CommandResult)

        Raises:
            SecurityError: If permission is denied
            ValueError: If tool name format is invalid or tool not found
        """
        from omni.core.security import SecurityError

        # 1. Validate Tool Identifier
        if "." not in tool_name:
            raise ValueError(
                f"Invalid tool name format '{tool_name}'. Expected 'skill.command' format."
            )

        target_skill_name, command_name = tool_name.split(".", 1)

        # 2. Permission Gatekeeper (Enforcement)
        if caller:
            # Look up the caller's manifest to check permissions
            caller_skill = self.skill_context.get_skill(caller)
            if not caller_skill:
                raise SecurityError(
                    skill_name=caller,
                    tool_name=tool_name,
                    required_permission="identity_verification_failed",
                )

            # Check if caller has permission to invoke target_tool
            # Uses Rust-powered PermissionGatekeeper under the hood
            permissions = getattr(caller_skill.metadata, "permissions", [])

            # Cognitive Enhancement: Pass protocol guidance for re-anchoring
            protocol_guidance = None
            if hasattr(caller_skill, "protocol_content"):
                protocol_guidance = caller_skill.protocol_content

            self.security.validate_or_raise(
                skill_name=caller,
                tool_name=tool_name,
                skill_permissions=permissions,
                protocol_guidance=protocol_guidance,
            )

        # 3. Resolve Target
        target_skill = self.skill_context.get_skill(target_skill_name)
        if not target_skill:
            raise ValueError(f"Target skill '{target_skill_name}' not found.")

        # 4. Execute
        if not hasattr(target_skill, "execute"):
            raise ValueError(f"Skill '{target_skill_name}' is not executable.")

        logger.debug(f"🔐 Executing {tool_name} (Caller: {caller or 'ROOT'})")
        result = await target_skill.execute(command_name, **args)

        # 5. Proactive Cognitive Management
        # If successfully executed but skills are overloaded, inject a subtle warning
        if caller:
            warning = self.security.get_overload_warning(proactive=True)
            if warning:
                # Append warning to result if it's a string, or log it
                if isinstance(result, str):
                    result = f"{result}\n{warning}"
                elif isinstance(result, dict) and "message" in result:
                    result["message"] = f"{result['message']}\n{warning}"
                elif isinstance(result, dict):
                    result["_cognition"] = warning

        return result

    # =========================================================================
    # Skill Discovery (Rust-Powered)
    # =========================================================================

    @property
    def discovery_service(self):
        """Get the skill discovery service (lazy initialization).

        Uses Rust scanner for high-performance batch scanning.
        """
        if self._discovery_service is None:
            from omni.core.skills.discovery import SkillDiscoveryService

            self._discovery_service = SkillDiscoveryService()
        return self._discovery_service

    @property
    def discovered_skills(self) -> list[Any]:
        """Get list of discovered skills."""
        return self._discovered_skills

    def discover_skills(self) -> list[Any]:
        """Discover all skills using Rust scanner.

        This is called during kernel boot for fast skill discovery.

        Returns:
            List of DiscoveredSkill objects
        """
        if not self._discovered_skills:
            logger.info(f"🔍 Discovering skills in {self._skills_dir}")
            self._discovered_skills = self.discovery_service.discover_all([str(self._skills_dir)])
            # Note: Discovery count is logged by discovery_service.discover_all()
        return self._discovered_skills

    def load_universal_skill(self, skill_name: str) -> Any:
        """Load a skill using UniversalScriptSkill (Zero-Code Architecture).

        Args:
            skill_name: Name of the skill (e.g., "git", "filesystem")

        Returns:
            UniversalScriptSkill instance (loaded and ready)
        """
        from omni.core.skills.universal import UniversalScriptSkill

        skill_path = self._skills_dir / skill_name
        if not skill_path.exists():
            raise ValueError(f"Skill not found: {skill_name} (path: {skill_path})")

        skill = UniversalScriptSkill(skill_name=skill_name, skill_path=skill_path)
        return skill

    def load_all_universal_skills(self) -> list[Any]:
        """Load all discovered skills using UniversalScriptSkill.

        Returns:
            List of loaded UniversalScriptSkill instances
        """
        from omni.core.skills.universal import UniversalSkillFactory

        # Use project root for path resolution (discovered paths are relative to project root)
        factory = UniversalSkillFactory(self._project_root)

        # Use Index-based discovery (Rust-First Indexing)
        discovered_skills = self.discover_skills()

        skills = []
        for ds in discovered_skills:
            try:
                # Use create_from_discovered to avoid SKILL.md parsing
                skill = factory.create_from_discovered(ds)
                skills.append(skill)
                logger.debug(f"Loaded universal skill: {skill.name}")
            except Exception as e:
                logger.error(f"Failed to load skill {ds.name}: {e}")

        logger.info(f"Loaded {len(skills)} universal skills via Index")
        return skills

    # =========================================================================
    # Skill Runtime Integration
    # =========================================================================

    @property
    def skill_context(self) -> SkillContext:
        """Get the skill context with all skills loaded (lazy initialization).

        This property automatically discovers, loads, and registers all skills
        on first access, ensuring tools are available for the ReAct loop.
        """
        if self._skill_context is None:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            from omni.core.skills.runtime import SkillContext

            self._skill_context = SkillContext(self._skills_dir)

            # Auto-discover, load, and register all skills
            try:
                # Discover skills
                discovered_skills = self.discover_skills()

                def load_skills_sync():
                    """Load all skills synchronously in a thread."""

                    async def load_all_skills_async():
                        for ds in discovered_skills:
                            try:
                                from omni.core.skills.universal import UniversalSkillFactory

                                factory = UniversalSkillFactory(self._project_root)
                                skill = factory.create_from_discovered(ds)
                                await skill.load()
                                self._skill_context.register_skill(skill)
                            except Exception as e:
                                logger.warning(f"Failed to load skill {ds.name}: {e}")

                    # Create a NEW event loop for this thread (avoids conflicts with main loop)
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(load_all_skills_async())
                    finally:
                        loop.close()

                # Run in a thread pool to avoid event loop conflicts
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(load_skills_sync)
                    future.result()  # Wait for completion

                logger.debug(f"Skill context initialized with {len(discovered_skills)} skills")
            except Exception as e:
                logger.warning(f"Failed to auto-load skills: {e}")

        return self._skill_context

    # =========================================================================
    # Semantic Router (The Cortex)
    # =========================================================================

    @property
    def router(self):
        """Get the semantic router (lazy initialization).

        The Cortex provides intent-to-action mapping using vector search.
        """
        if self._router is None:
            from omni.core.router import FallbackRouter, SemanticRouter, SkillIndexer, UnifiedRouter

            indexer = SkillIndexer()
            semantic_router = SemanticRouter(indexer)
            self._router = UnifiedRouter(semantic_router, FallbackRouter())
        return self._router

    # =========================================================================
    # Intent Sniffer (The Nose) - Context Detection
    # =========================================================================

    @property
    def sniffer(self) -> IntentSniffer:
        """Get the intent sniffer (lazy initialization).

        The Sniffer detects context from the file system to activate skills.
        Powered by Rust-generated LanceDB index.
        """
        if self._sniffer is None:
            from omni.core.router.sniffer import IntentSniffer

            self._sniffer = IntentSniffer()
        return self._sniffer

    async def load_sniffer_rules(self) -> int:
        """Load declarative sniffing rules from LanceDB.

        This bridges the Rust Scanner (Producer) and Python Sniffer (Consumer).
        Returns the number of rules loaded.
        """
        count = await self.sniffer.load_rules_from_lancedb()
        logger.info(f"👃 Sniffer loaded with {count} declarative rules from LanceDB")
        return count

    async def build_cortex(self) -> None:
        """Build the semantic cortex from loaded skills.

        Called during kernel boot to index all skills for routing.
        """
        from omni.core.router import SkillIndexer

        indexer = SkillIndexer()
        # Pass kernel reference for keyword routing access to skill_context
        indexer._kernel = self

        self._router = self.router
        self._router._semantic._indexer = indexer

        # Collect skill metadata for indexing
        skills_data = []
        if self._skill_context is not None:
            for skill in self._skill_context._skills.values():
                # Get command names and create command entries
                cmd_names = skill.list_commands() if hasattr(skill, "list_commands") else []
                commands = [{"name": cmd, "description": ""} for cmd in cmd_names]

                skills_data.append(
                    {
                        "name": skill.name,
                        "description": getattr(skill.metadata, "description", ""),
                        "commands": commands,
                    }
                )

        await indexer.index_skills(skills_data)
        logger.info(f"Cortex built with {indexer.get_stats()['entries_indexed']} entries")

    # =========================================================================
    # Event-Driven Reactor (Reactive Architecture)
    # =========================================================================

    @property
    def reactor(self):
        """Get the event-driven reactor (lazy initialization).

        The Reactor consumes events from the Rust Event Bus and dispatches
        to registered Python handlers. This enables reactive architecture:
        - Cortex auto-indexing on file changes
        - Async checkpoint saving
        - Sniffer context updates
        """
        if self._reactor is None:
            self._reactor = get_reactor()
        return self._reactor

    async def _on_file_changed_cortex(self, event: dict) -> None:
        """Reactive Handler: Updates Cortex index when files change.

        Triggered by file/changed and file/created events from the Rust watcher.
        Performs incremental indexing without blocking the main thread.
        """
        try:
            payload = event.get("payload", {})
            path = payload.get("path")

            if not path:
                return

            logger.debug(f"⚡ Cortex reacting to file change: {path}")

            # Delegate to the indexer for incremental indexing
            # The indexer handles debouncing and batching internally
            if hasattr(self, "_router") and self._router is not None:
                if hasattr(self._router, "_semantic") and hasattr(
                    self._router._semantic, "_indexer"
                ):
                    indexer = self._router._semantic._indexer
                    if hasattr(indexer, "index_file"):
                        await indexer.index_file(path)

        except Exception as e:
            logger.error(f"Failed to update Cortex for file change: {e}")

    # =========================================================================
    # Paths
    # =========================================================================

    @property
    def project_root(self) -> Path:
        """Get project root directory."""
        return self._project_root

    @property
    def skills_dir(self) -> Path:
        """Get skills directory."""
        return self._skills_dir

    # =========================================================================
    # Hot Reload
    # =========================================================================

    def enable_hot_reload(self) -> None:
        """Start the file system watcher for hot reload (development mode).

        Watches:
        - assets/skills/ directory for skill script changes
        - .cache/omni-vector/ for LanceDB changes

        Handles both skill reload and LanceDB index reload.
        """
        import os
        from pathlib import Path

        if self._watcher is not None and self._watcher.is_running:
            return  # Already running

        def callback_bridge(event_path: str) -> None:
            """Bridge Rust watcher callback to async reload.

            Handles skill changes - LanceDB will be updated on next sync.
            """
            filename = os.path.basename(event_path)
            logger.debug(f"File changed: {filename}")

            # Reload sniffer rules from LanceDB
            self._reload_sniffer_sync_wrapper()
            return

            # Handle Skill Script Change
            try:
                rel = Path(event_path).relative_to(self._skills_dir)
                if len(rel.parts) > 0:
                    skill_name = rel.parts[0]
                    if not skill_name.startswith("_"):
                        logger.info(f"🔄 Triggering reload for {skill_name}...")
                        self._reload_skill_sync_wrapper(skill_name)
            except ValueError:
                pass  # Path not relative to skills_dir

        self._watcher = RustKernelWatcher(self._skills_dir, callback_bridge)
        if self._watcher is not None:
            self._watcher.start()
            logger.info("🔁 Hot reload enabled (watches skills/ and LanceDB)")

    def _reload_sniffer_sync_wrapper(self) -> None:
        """Sync wrapper for sniffer reload (triggered by LanceDB change)."""
        try:
            count = self.sniffer.load_rules_from_lancedb()
            logger.info(f"✅ Sniffer rules reloaded ({count} rules active)")
        except Exception as e:
            logger.error(f"❌ Failed to reload sniffer rules: {e}")

    def _reload_skill_sync_wrapper(self, skill_name: str) -> None:
        """Sync wrapper to trigger reload task."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.reload_skill(skill_name))
        except RuntimeError:
            # No loop running, run synchronously
            asyncio.run(self.reload_skill(skill_name))

    async def reload_skill(self, skill_name: str) -> None:
        """Reload a single skill (for hot reload)."""
        logger.info(f"♻️ Reloading skill: {skill_name}")

        try:
            # Load fresh skill instance
            skill = self.load_universal_skill(skill_name)
            await skill.load({"cwd": str(self._project_root)})

            # Update in skill context
            self.skill_context.register_skill(skill)
            logger.info(f"✅ Hot Reload Complete: {skill_name}")

            # Notify MCP clients to refresh their tool list (descriptions may have changed)
            await self._notify_clients_tool_list_changed()
        except Exception as e:
            logger.error(f"❌ Hot Reload Failed for {skill_name}: {e}")

    async def _safe_build_cortex(self) -> None:
        """Wrapper for build_cortex to handle background execution safety."""
        try:
            await self.build_cortex()
        except Exception as e:
            logger.error(f"Failed to build Cortex in background: {e}")

    async def _notify_clients_tool_list_changed(self) -> None:
        """Send tool list changed notification to MCP clients."""
        try:
            # Import from agent's lifespan module
            from omni.agent.mcp_server.lifespan import _notify_tools_changed

            await _notify_tools_changed({})
        except Exception as e:
            logger.debug(f"⚠️ Failed to notify clients of tool list change: {e}")

    # =========================================================================
    # Lifecycle Callbacks
    # =========================================================================

    async def _on_ready(self) -> None:
        """Called when kernel reaches READY state."""
        import time as _time

        t0 = _time.time()
        logger.info("🟢 Kernel initializing...")

        # Step 1: Initialize skill context
        skill_ctx = self.skill_context
        logger.debug(f"Skill context initialized: {self._skills_dir}")

        t1 = _time.time()

        # Step 2: Load and Register Universal Skills
        # Use UniversalScriptSkill to load all skills from assets
        logger.info(f"📦 Loading skills from {self._skills_dir}...")
        loaded_skills = self.load_all_universal_skills()

        # Count total commands
        total_commands = 0
        skills_loaded = 0
        for skill in loaded_skills:
            # Step 3: Load the skill (extensions & scripts)
            try:
                await skill.load({"cwd": str(self._project_root)})
                skill_ctx.register_skill(skill)
                cmd_count = len(skill.list_commands())
                total_commands += cmd_count
                skills_loaded += 1
                logger.debug(f"  ✅ {skill.name}: {cmd_count} commands")
            except Exception as e:
                logger.error(f"  ❌ Failed to load skill '{skill.name}': {e}")

        t2 = _time.time()

        # Step 4: Build Semantic Cortex (The Cortex)
        # Run in background to prevent blocking kernel startup (critical for MCP connection)
        logger.info("🧠 Building Semantic Cortex (Background)...")
        cortex_task = asyncio.create_task(self._safe_build_cortex())
        self._background_tasks.add(cortex_task)
        cortex_task.add_done_callback(self._background_tasks.discard)

        t3 = _time.time()

        # Step 5: Initialize Intent Sniffer (The Nose)
        # Loads declarative rules from LanceDB (populated by Rust scanner)
        logger.info("👃 Initializing Context Sniffer...")
        await self.load_sniffer_rules()

        t4 = _time.time()

        # Step 6: Initialize Event Reactor (Reactive Architecture)
        # Wire Cortex, Checkpoint, and Sniffer to the Rust Event Bus
        logger.info("🔗 Initializing Event Reactor...")
        self._reactor = get_reactor()

        # Wire Cortex to File Events (auto-increment indexing)
        self._reactor.register_handler(
            EventTopic.FILE_CHANGED, self._on_file_changed_cortex, priority=10
        )
        self._reactor.register_handler(
            EventTopic.FILE_CREATED, self._on_file_changed_cortex, priority=10
        )

        # Wire Sniffer to File Events (reactive context detection)
        self.sniffer.register_to_reactor()

        # Start the reactor consumer loop
        await self._reactor.start()
        logger.info("🧠 Cortex hooked into Reactive Bus")

        # Step 7: Log extension summary (if any extensions were loaded)
        from omni.core.skills.extensions.loader import log_extension_summary

        log_extension_summary()

        # Timing summary
        t5 = _time.time()
        total_time = t5 - t0
        logger.info(
            f"[TIMING] Kernel startup: {total_time:.2f}s "
            f"(skills: {t1 - t0:.2f}s, load: {t2 - t1:.2f}s, "
            f"cortex_bg: {t3 - t2:.2f}s, sniffer: {t4 - t3:.2f}s, reactor: {t5 - t4:.2f}s)"
        )

        # Summary of active services
        logger.info("━" * 60)
        logger.info("🚀 Kernel Services Active:")
        core_commands = len(self.skill_context.get_core_commands())
        logger.info(f"   • Skills:    {skills_loaded} loaded, {core_commands} core commands")
        logger.info("   • Cortex:    Semantic routing index ready (Reactive)")
        logger.info("   • Sniffer:   Context detection active")
        logger.info("   • Security:  Permission Gatekeeper active (Zero Trust)")
        logger.info("   • Watcher:   File monitoring enabled (hot reload)")
        logger.info("   • Reactor:   Event-driven architecture active")
        logger.info("━" * 60)

    async def _on_running(self) -> None:
        """Called when kernel reaches RUNNING state."""
        pass

    async def _on_shutdown(self) -> None:
        """Called when kernel starts shutting down - graceful cleanup."""
        logger.info("🛑 Kernel shutting down...")

        # Step 0: Cancel background tasks
        if self._background_tasks:
            logger.debug(f"Cancelling {len(self._background_tasks)} background tasks")
            for task in self._background_tasks:
                task.cancel()

            # Wait for tasks to finish cancelling
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()

        # Step 1: Unregister sniffer from reactor (cleanup handlers)
        if self._sniffer is not None:
            self._sniffer.unregister_from_reactor()
            logger.debug("Sniffer unregistered from reactor")

        # Step 1: Stop reactor first (no more event processing)
        if self._reactor is not None and self._reactor.is_running:
            await self._reactor.stop()
            self._reactor = None
            logger.debug("Event reactor stopped")

        # Step 2: Stop file watcher (no more file events)
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None
            logger.debug("File watcher stopped")

        # Step 3: Save any persistent state (vector index, caches)
        # Note: In-memory stores can't be persisted, but we log the intent
        if hasattr(self, "_router") and self._router is not None:
            if hasattr(self._router, "_semantic") and hasattr(self._router._semantic, "_indexer"):
                indexer = self._router._semantic._indexer
                stats = indexer.get_stats()
                if stats.get("entries_indexed", 0) > 0:
                    logger.info(f"💾 Index contains {stats['entries_indexed']} entries (in-memory)")

        # Step 4: Unregister all skills gracefully
        if self._skill_context is not None:
            skills_count = self._skill_context.skills_count
            from omni.core.skills.runtime import reset_context

            reset_context()
            logger.debug(f"Unregistered {skills_count} skills")

        # Step 5: Cleanup components
        self._components.clear()

        logger.info("👋 Kernel shutdown complete")


def get_kernel() -> Kernel:
    """Get the global kernel instance (singleton)."""
    global _kernel_instance
    if _kernel_instance is None:
        _kernel_instance = Kernel()
    return _kernel_instance


def reset_kernel() -> None:
    """Reset the global kernel instance (for testing)."""
    global _kernel_instance
    _kernel_instance = None
