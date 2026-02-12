"""API forwarding tests for omni.foundation.config.dirs."""

from __future__ import annotations

from omni.foundation.config import database, harvested, prj
from omni.foundation.config import dirs as dirs_mod


def test_dirs_forwards_prj_symbols() -> None:
    assert dirs_mod.PRJ_DIRS is prj.PRJ_DIRS
    assert dirs_mod.PRJ_CONFIG is prj.PRJ_CONFIG
    assert dirs_mod.PRJ_DATA is prj.PRJ_DATA
    assert dirs_mod.PRJ_CACHE is prj.PRJ_CACHE
    assert dirs_mod.PRJ_RUNTIME is prj.PRJ_RUNTIME
    assert dirs_mod.get_prj_dir is prj.get_prj_dir
    assert dirs_mod.get_config_dir is prj.get_config_dir
    assert dirs_mod.get_data_dir is prj.get_data_dir
    assert dirs_mod.get_cache_dir is prj.get_cache_dir
    assert dirs_mod.get_runtime_dir is prj.get_runtime_dir
    assert dirs_mod.get_skills_dir is prj.get_skills_dir


def test_dirs_forwards_database_and_harvested_symbols() -> None:
    assert dirs_mod.get_vector_db_path is database.get_vector_db_path
    assert dirs_mod.get_memory_db_path is database.get_memory_db_path
    assert dirs_mod.get_harvest_dir is harvested.get_harvest_dir
    assert dirs_mod.get_harvest_file is harvested.get_harvest_file
