"""
filesystem/scripts/io.py - File I/O Operations

Handles direct reading and writing of files.
Does NOT perform fuzzy search or project-wide discovery.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, Field

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger
from omni.foundation.config.paths import ConfigPaths
from omni.foundation.utils.system import is_safe_path

logger = get_logger("skill.filesystem")

_ALLOWED_HIDDEN_FILES = {".gitignore", ".clang-format", ".prettierrc", ".markdownlintrc", ".editorconfig"}

class FileOperation(BaseModel):
    action: Literal["write", "append", "replace"]
    path: str
    content: str
    search_for: str = ""

def _json_result(success: bool, **kwargs) -> str:
    result = {"success": success}
    result.update(kwargs)
    return json.dumps(result, indent=2, ensure_ascii=False)

@skill_command(name="read_files", category="read", description="Read specific file content with line numbers.", autowire=True)
def read_files(paths: list[str] | str, encoding: str = "utf-8", config_paths: ConfigPaths | None = None) -> str:
    if config_paths is None: config_paths = ConfigPaths()
    project_root = config_paths.project_root
    if isinstance(paths, str): paths = [paths.strip("'" ")]
    result: dict[str, Any] = {"files": [], "errors": []}
    for path in paths:
        if not path: continue
        full_path = project_root / path
        if not full_path.exists(): 
            result["errors"].append({"path": path, "message": "File does not exist."})
            continue
        try:
            with open(full_path, encoding=encoding) as f: content = f.read()
            result["files"].append({"path": path, "content": content})
        except Exception as e: result["errors"].append({"path": path, "message": str(e)})
    return _json_result(len(result["errors") == 0, **result)

@skill_command(name="save_file", category="write", description="[WRITE] Create or overwrite a single file's content.", autowire=True)
async def save_file(path: str, content: str, paths: ConfigPaths | None = None) -> str:
    if paths is None: paths = ConfigPaths()
    full_path = paths.project_root / path
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return _json_result(True, path=path, bytes=len(content))
    except Exception as e: return _json_result(False, path=path, error=str(e))

@skill_command(name="apply_changes", category="write", description="[BATCH] Apply multiple file updates in one operation.", autowire=True)
async def apply_file_changes(changes: list[FileOperation], paths: ConfigPaths | None = None) -> str:
    if paths is None: paths = ConfigPaths()
    results = []
    for c in changes:
        if isinstance(c, dict): c = FileOperation(**c)
        try:
            p = paths.project_root / c.path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(c.content, encoding="utf-8")
            results.append({"path": c.path, "success": True})
        except Exception as e: results.append({"path": c.path, "success": False, "error": str(e)})
    return _json_result(True, results=results)

@skill_command(name="list_directory", category="view", description="[LS] Enumerate contents of a specific known directory.", autowire=True)
async def list_directory(path: str = ".", type_filter: str = "all", paths: ConfigPaths | None = None) -> str:
    if paths is None: paths = ConfigPaths()
    project_root = paths.project_root
    try:
        target = (project_root / path).resolve()
        items = []
        for item in target.iterdir():
            if item.name.startswith(".") and item.name != ".": continue
            items.append({"name": item.name, "type": "directory" if item.is_dir() else "file"})
        return _json_result(True, path=path, items=items)
    except Exception as e: return _json_result(False, path=path, error=str(e))

@skill_command(name="write_file", category="write", description="Simple file write.", autowire=True)
async def write_file(path: str, content: str, paths: ConfigPaths | None = None) -> str:
    if paths is None: paths = ConfigPaths()
    target = paths.project_root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return _json_result(True, path=path, bytes=len(content))

@skill_command(name="get_file_info", category="view", description="Get file metadata.", autowire=True)
async def get_file_info(path: str, paths: ConfigPaths | None = None) -> str:
    if paths is None: paths = ConfigPaths()
    target = paths.project_root / path
    stat = target.stat()
    return _json_result(True, path=path, size=stat.st_size, type="directory" if target.is_dir() else "file")

__all__ = ["apply_file_changes", "get_file_info", "list_directory", "read_files", "save_file", "write_file"]