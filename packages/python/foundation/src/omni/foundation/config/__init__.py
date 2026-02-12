# config
"""
Foundation Configuration Module.

Modularized subpackage providing centralized configuration management.

Modules:
- prj: Project directory utilities (PRJ_DIRS, PRJ_DATA, etc.)
- database: Database path management
- harvested: Harvested knowledge utilities
- zk: Zettelkasten notebook utilities
- settings: Settings class and functions
- paths: Semantic path resolution

SSOT (Single Source of Truth):
    references.yaml - Path and directory configurations
    settings.yaml - Feature and behavior settings

Usage:
    from omni.foundation.config import PRJ_DIRS, get_vector_db_path
    from omni.foundation.config.prj import PRJ_DATA, get_cache_dir
    from omni.foundation.config.zk import get_zk_notebook_dir
    from omni.foundation.config.settings import get_setting
"""

from .prj import (
    PRJ_CACHE,
    PRJ_CHECKPOINT,
    PRJ_CONFIG,
    PRJ_DATA,
    PRJ_DIRS,
    PRJ_PATH,
    PRJ_RUNTIME,
    get_cache_dir,
    get_config_dir,
    get_data_dir,
    get_prj_dir,
    get_runtime_dir,
    get_skills_dir,
)
from .database import (
    get_checkpoint_db_path,
    get_checkpoint_table_name,
    get_database_path,
    get_database_paths,
    get_memory_db_path,
    get_vector_db_path,
)
from .harvested import (
    get_harvest_dir,
    get_harvest_file,
)
from .paths import (
    ConfigPaths,
    get_config_paths,
)
from .settings import (
    Settings,
    get_setting,
    get_settings,
)
from .zk import (
    get_zk_config_path,
    get_zk_notebook_dir,
)


__all__ = [
    # Project directories (from prj.py)
    "PRJ_CACHE",
    "PRJ_CHECKPOINT",
    "PRJ_CONFIG",
    "PRJ_DATA",
    "PRJ_DIRS",
    "PRJ_PATH",
    "PRJ_RUNTIME",
    "get_cache_dir",
    "get_config_dir",
    "get_data_dir",
    "get_prj_dir",
    "get_runtime_dir",
    "get_skills_dir",
    # Database utilities (from database.py)
    "get_checkpoint_db_path",
    "get_checkpoint_table_name",
    "get_database_path",
    "get_database_paths",
    "get_memory_db_path",
    "get_vector_db_path",
    # Harvested knowledge (from harvested.py)
    "get_harvest_dir",
    "get_harvest_file",
    # Zettelkasten (from zk.py)
    "get_zk_config_path",
    "get_zk_notebook_dir",
    # Settings
    "Settings",
    "get_setting",
    "get_settings",
    # Paths
    "ConfigPaths",
    "get_config_paths",
]
