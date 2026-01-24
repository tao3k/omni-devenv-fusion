# Foundation package for omni-dev-fusion - Level 1 Infrastructure Layer

# Defer expensive imports for faster module load
# importlib.metadata.version() takes ~70ms - defer until actually needed

_cached_version: str | None = None


def _get_version() -> str:
    """Lazy version lookup - called on first access."""
    global _cached_version
    if _cached_version is None:
        from importlib.metadata import PackageNotFoundError, version

        try:
            _cached_version = version("omni-foundation")
        except PackageNotFoundError:
            _cached_version = "0.0.0-dev"
    return _cached_version


# Lazy-loaded submodule cache
_bridge_module = None
_api_module = None
_services_module = None
_utils_module = None
_runtime_module = None
_config_module = None
_checkpoint_module = None


def __getattr__(name: str):
    """Lazy module attributes - defer expensive lookups."""
    global \
        _bridge_module, \
        _api_module, \
        _services_module, \
        _utils_module, \
        _runtime_module, \
        _config_module, \
        _checkpoint_module

    if name == "__version__":
        return _get_version()

    # Lazy load utils.skills (Skill-related utilities)
    if name in (
        "current_skill_dir",
        "skill_path",
        "skill_asset",
        "skill_command",
        "skill_reference",
        "skill_data",
    ):
        from . import utils

        return getattr(utils.skills, name)

    # Lazy load utils.common (Common helper functions)
    if name in ("project_root", "common_src", "agent_src", "setup_import_paths"):
        from . import utils

        return getattr(utils.common, name)

    # Lazy load utils.templating
    if name == "render_string":
        from . import utils

        return getattr(utils.templating, name)

    # Lazy load config.dirs (PRJ_SPEC directories including cache)
    if name in (
        "PRJ_DIRS",
        "PRJ_DATA",
        "PRJ_CACHE",
        "PRJ_CONFIG",
        "PRJ_RUNTIME",
        "PRJ_PATH",
        "PRJ_CHECKPOINT",
        "get_prj_dir",
        "get_data_dir",
        "get_cache_dir",
        "get_config_dir",
        "get_runtime_dir",
        "get_checkpoint_db_path",
        "get_checkpoint_table_name",
    ):
        from . import config

        return getattr(config.dirs, name)

    # Lazy load checkpoint module (unified checkpoint storage)
    if name in (
        "get_checkpointer",
        "save_workflow_state",
        "load_workflow_state",
        "get_workflow_history",
        "delete_workflow_state",
        "save_workflow_state_sqlite",
        "load_workflow_state_sqlite",
    ):
        if _checkpoint_module is None:
            _checkpoint_module = __import__("omni.foundation.checkpoint", fromlist=[""])
        return getattr(_checkpoint_module, name)

    # Lazy load config.settings
    if name in ("get_setting",):
        from . import config

        return getattr(config.settings, name)

    # Lazy load config.paths
    if name in (
        "get_api_key",
        "get_mcp_config_path",
        "get_anthropic_settings_path",
        "get_project_config_path",
    ):
        from . import config

        return getattr(config.paths, name)

    # Lazy load config.logging
    if name in ("configure_logging",):
        from . import config

        return getattr(config.logging, name)

    # Lazy load config directory functions
    if name in ("get_conf_dir", "set_conf_dir"):
        from . import config

        return getattr(config.directory, name)

    # Lazy load runtime.gitops
    if name in (
        "get_project_root",
        "get_spec_dir",
        "get_instructions_dir",
        "get_docs_dir",
        "get_agent_dir",
        "get_src_dir",
        "is_git_repo",
        "is_project_root",
        "PROJECT",
    ):
        from . import runtime

        return getattr(runtime.gitops, name)

    # Lazy load runtime.isolation
    if name in ("run_skill_command",):
        from . import runtime

        return getattr(runtime.isolation, name)

    # Lazy load services.vector
    if name in (
        "get_vector_store",
        "VectorStoreClient",
        "SearchResult",
        "search_knowledge",
        "add_knowledge",
    ):
        if _services_module is None:
            _services_module = __import__("omni.foundation.services", fromlist=[""])
        return getattr(_services_module.vector, name)

    # Lazy load services.embedding
    if name in (
        "get_embedding_service",
        "EmbeddingService",
        "embed_text",
        "embed_batch",
        "get_dimension",
    ):
        if _services_module is None:
            _services_module = __import__("omni.foundation.services", fromlist=[""])
        return getattr(_services_module.embedding, name)

    # Lazy load bridge module (Rust bindings isolation layer)
    if name == "bridge":
        if _bridge_module is None:
            _bridge_module = __import__("omni.foundation.bridge", fromlist=[""])
        return _bridge_module

    # Lazy load api module (foundation decorators and utilities)
    if name == "api":
        if _api_module is None:
            _api_module = __import__("omni.foundation.api", fromlist=[""])
        return _api_module

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
