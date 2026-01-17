"""
agent/core/skill_manager/jit_loader.py
 JIT Skill Loader - Robust Dynamic Execution

Features:
1. Dynamic module loading without global sys.path pollution
2. Support for relative imports (e.g., 'from . import utils')
3. Virtual package namespace for clean isolation
4. Heavy Skill isolation via uv run when pyproject.toml exists

Usage:
    from agent.core.skill_manager.jit_loader import get_jit_loader

    loader = get_jit_loader()
    schema = loader.get_tool_schema(record)
    result = loader.execute_tool(record, {"message": "commit msg"})
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import subprocess
import sys
import types
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING, List, Union

import structlog

from agent.skills.decorators import skill_command

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from omni_core_rs import PyToolRecord


@dataclass
class ToolRecord:
    """
    A tool record for JIT loading.

    Attributes:
        tool_name: Full name including skill prefix (e.g., "git.commit")
        description: Human-readable description
        skill_name: Name of the skill (e.g., "git")
        file_path: Path to the source Python file
        function_name: Name of the function to call
        execution_mode: "script" or "legacy"
        keywords: List of routing keywords
        input_schema: JSON schema placeholder (generated on-demand)
        docstring: Function docstring
    """

    tool_name: str
    description: str
    skill_name: str
    file_path: str
    function_name: str
    execution_mode: str = "script"
    keywords: List[str] = field(default_factory=list)
    input_schema: str = "{}"
    docstring: str = ""

    @classmethod
    def from_rust(cls, rust_record: "PyToolRecord") -> "ToolRecord":
        """Create from Rust PyToolRecord."""
        return cls(
            tool_name=rust_record.tool_name,
            description=rust_record.description,
            skill_name=rust_record.skill_name,
            file_path=rust_record.file_path,
            function_name=rust_record.function_name,
            execution_mode=rust_record.execution_mode,
            keywords=list(rust_record.keywords),
            input_schema=rust_record.input_schema,
            docstring=rust_record.docstring,
        )


class JITSkillLoader:
    """
    Just-In-Time Skill Loader.

     Replaces tools.py-based loading with direct script execution.

    Features:
    - Dynamic module loading from file paths
    - Virtual package namespace for relative import support
    - On-demand JSON Schema generation using inspect
    - Temporary sys.path modification (context manager)
    - Caching for performance
    """

    _instance: Optional["JITSkillLoader"] = None

    def __new__(cls) -> "JITSkillLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._module_cache: Dict[str, types.ModuleType] = {}
        self._func_cache: Dict[str, Callable] = {}

    def get_tool_schema(self, record: ToolRecord) -> Dict[str, Any]:
        """
        JIT generate JSON Schema for a tool.

        Uses inspect.signature to generate accurate schema,
        overriding any placeholder from the database.

        Args:
            record: ToolRecord with file_path and function_name

        Returns:
            JSON Schema dict for MCP/LLM consumption
        """
        try:
            func = self._load_function(record.file_path, record.function_name, record.skill_name)
            return self._generate_schema_from_func(func, record)
        except Exception as e:
            logger.error("Failed to generate schema", tool=record.tool_name, error=str(e))
            return {
                "name": record.tool_name,
                "description": record.description or "Error loading schema",
                "input_schema": {"type": "object", "properties": {}},
            }

    async def execute_tool(self, record: ToolRecord, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool with the given arguments.

        Supports two execution modes:
        1. In-Process: For lightweight skills without pyproject.toml
        2. Isolated (uv run): For Heavy Skills with their own pyproject.toml

        Args:
            record: ToolRecord with execution info
            arguments: Dict of arguments to pass to the function

        Returns:
            Result of the function execution
        """
        import asyncio

        skill_path = Path(record.file_path).parent.parent  # assets/skills/<skill>

        # Check for Heavy Skill isolation (pyproject.toml indicates isolated env)
        if (skill_path / "pyproject.toml").exists():
            return self._execute_isolated(record, arguments, skill_path)

        # Default: In-process execution
        func = self._load_function(record.file_path, record.function_name, record.skill_name)
        result = func(**arguments)

        # Handle async functions - await the coroutine
        if asyncio.iscoroutine(result):
            result = await result

        return result

    def _execute_isolated(
        self, record: ToolRecord, arguments: Dict[str, Any], skill_path: Path
    ) -> Any:
        """
        Execute a Heavy Skill in its isolated uv environment.

        This is used for skills like crawl4ai that have heavy dependencies
        that shouldn't pollute the main agent runtime.

        Args:
            record: ToolRecord with execution info
            arguments: Dict of arguments to pass to the function
            skill_path: Path to the skill directory (containing pyproject.toml)

        Returns:
            Result from the isolated execution
        """
        logger.info(f"Executing isolated skill via uv: {record.tool_name}")

        # Convert file path to module path (e.g., scripts/engine.py -> scripts.engine)
        rel_path = Path(record.file_path).relative_to(skill_path)
        module_path = rel_path.with_suffix("").as_posix().replace("/", ".")

        # Construct bootstrapper script that runs the target function
        args_json = json.dumps(arguments)

        bootstrap_script = f"""
import sys
import json
import asyncio
from {module_path} import {record.function_name}

async def run():
    try:
        args = json.loads(sys.argv[1])
        # Call the function and handle both sync and async results
        result = {record.function_name}(**args)
        # If result is a coroutine, await it
        if asyncio.iscoroutine(result):
            result = await result
        # Output JSON result
        print(json.dumps({{"status": "success", "data": result}}, default=str))
    except Exception as e:
        print(json.dumps({{"status": "error", "error": str(e)}}, default=str))

if __name__ == "__main__":
    asyncio.run(run())
"""

        try:
            # Run in the skill's isolated environment
            cmd = [
                "uv",
                "run",
                "--directory",
                str(skill_path),
                "python",
                "-c",
                bootstrap_script,
                args_json,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                raise RuntimeError(f"Execution failed: {result.stderr}")

            # Parse output - find the last JSON line
            output_lines = result.stdout.strip().split("\n")
            json_output = json.loads(output_lines[-1])

            if json_output.get("status") == "error":
                raise RuntimeError(f"Isolated execution error: {json_output.get('error')}")

            return json_output.get("data")

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Skill execution timed out: {record.tool_name}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse output: {e}, stdout: {result.stdout[:500]}")

    def _load_function(self, file_path: str, func_name: str, skill_name: str) -> Callable:
        """
        Load a function from a Python source file.

        Handles:
        - Dynamic module loading via importlib
        - Virtual package namespace for relative imports
        - Caching for performance
        """
        cache_key = f"{file_path}:{func_name}"

        if cache_key in self._func_cache:
            return self._func_cache[cache_key]

        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Skill script not found: {file_path}")

        # Load the module with virtual package support
        module = self._load_module_isolated(path, skill_name)

        if not hasattr(module, func_name):
            raise AttributeError(f"Function '{func_name}' not found in {file_path}")

        func = getattr(module, func_name)
        self._func_cache[cache_key] = func
        logger.debug("Loaded function", tool=func_name, file=file_path)

        return func

    def _load_module_isolated(self, path: Path, skill_name: str) -> types.ModuleType:
        """
        Load a module treating it as part of a virtual package namespace.

        This enables relative imports (e.g., `from . import utils`) to work correctly.
        """
        # Virtual package name: omni_skills.git.scripts.commit
        pkg_namespace = f"omni_skills.{skill_name}.scripts"
        module_name = f"{pkg_namespace}.{path.stem}"

        if path.as_posix() in self._module_cache:
            return self._module_cache[path.as_posix()]

        # Ensure parent packages exist in sys.modules for relative imports
        self._ensure_virtual_package("omni_skills")
        self._ensure_virtual_package(f"omni_skills.{skill_name}")
        self._ensure_virtual_package(pkg_namespace, path.parent)

        # Create the module spec
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        if not spec or not spec.loader:
            raise ImportError(f"Could not create spec for {path}")

        module = importlib.util.module_from_spec(spec)

        # Set __package__ to enable relative imports
        module.__package__ = pkg_namespace

        # Add to cache and sys.modules
        sys.modules[module_name] = module
        self._module_cache[path.as_posix()] = module

        # Execute with temporary path context
        try:
            with self._execution_path(path.parent):
                spec.loader.exec_module(module)
        except Exception as e:
            del sys.modules[module_name]
            del self._module_cache[path.as_posix()]
            raise ImportError(f"Failed to execute skill script {path}: {e}")

        return module

    def _ensure_virtual_package(self, package_name: str, path: Optional[Path] = None) -> None:
        """
        Create a virtual module in sys.modules if it doesn't exist.

        If path is provided, adds it to the module's __path__ for sibling discovery.
        """
        if package_name not in sys.modules:
            module = types.ModuleType(package_name)
            module.__path__ = [str(path)] if path else []
            sys.modules[package_name] = module

    @contextmanager
    def _execution_path(self, path: Path):
        """
        Temporarily add a path to sys.path for the duration of the context.

        This is safer than permanent modification - no global pollution.
        """
        path_str = str(path)
        if path_str in sys.path:
            yield
            return

        sys.path.insert(0, path_str)
        try:
            yield
        finally:
            if path_str in sys.path:
                sys.path.remove(path_str)

    def _generate_schema_from_func(self, func: Callable, record: ToolRecord) -> Dict[str, Any]:
        """
        Generate JSON Schema from a Python function using inspect.

        This creates an accurate schema based on the actual function
        signature, not the placeholder in the database.
        """
        sig = inspect.signature(func)
        doc = inspect.getdoc(func) or record.description

        properties = {}
        required_params = []

        for name, param in sig.parameters.items():
            # Skip special parameters
            if name in ("self", "cls", "ctx", "project_root"):
                continue

            # Determine type
            param_type = self._python_type_to_json(param.annotation)

            default = param.default
            if default is inspect.Parameter.empty:
                required_params.append(name)

            properties[name] = {
                "type": param_type,
                "description": f"Parameter: {name}",
            }

            if default is not inspect.Parameter.empty:
                properties[name]["default"] = default

        return {
            "name": record.tool_name,
            "description": doc,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required_params if required_params else None,
            },
        }

    def _python_type_to_json(self, annotation: Any) -> str:
        """Convert Python type annotation to JSON Schema type."""
        if annotation is inspect.Parameter.empty:
            return "string"
        if annotation is str:
            return "string"
        if annotation is int:
            return "integer"
        if annotation is float:
            return "number"
        if annotation is bool:
            return "boolean"
        if annotation is list:
            return "array"

        # Handle generic types like list[str], List[str], etc.
        origin = getattr(annotation, "__origin__", None)
        if origin is list:
            return "array"

        # Handle Optional[X] and Union[X, Y]
        if origin is Union:
            args = getattr(annotation, "__args__", ())
            for arg in args:
                if arg is type(None):
                    continue
                # Recursively handle the non-None type (which could be list[str])
                return self._python_type_to_json(arg)

        if annotation is dict:
            return "object"

        return "string"


def get_jit_loader() -> JITSkillLoader:
    """Get the global JITSkillLoader instance."""
    return JITSkillLoader()


async def get_tools_for_skill_jit(skill_name: str) -> list[ToolRecord]:
    """
    Get all tools for a skill using Rust scanner.

    Args:
        skill_name: Name of the skill (e.g., "git")

    Returns:
        List of ToolRecord objects
    """
    try:
        import omni_core_rs
        from common.skills_path import SKILLS_DIR

        skills_path = str(SKILLS_DIR())
        all_tools = omni_core_rs.scan_skill_tools(skills_path)

        skill_tools = [ToolRecord.from_rust(t) for t in all_tools if t.skill_name == skill_name]

        logger.info(
            "JIT loaded tools for skill",
            skill=skill_name,
            count=len(skill_tools),
        )

        return skill_tools

    except ImportError:
        logger.warning("omni_core_rs not available, cannot JIT load tools")
        return []


async def execute_skill_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    Convenience function to execute a skill tool by name.

    Args:
        tool_name: Full tool name (e.g., "git.commit")
        arguments: Arguments to pass to the function

    Returns:
        Result of the function execution
    """
    try:
        import omni_core_rs
        from common.skills_path import SKILLS_DIR

        skills_path = str(SKILLS_DIR())
        all_tools = omni_core_rs.scan_skill_tools(skills_path)

        record = next(
            (t for t in all_tools if t.tool_name == tool_name),
            None,
        )

        if not record:
            raise ValueError(f"Tool '{tool_name}' not found")

        tool_record = ToolRecord.from_rust(record)
        loader = get_jit_loader()

        return loader.execute_tool(tool_record, arguments)

    except ImportError:
        raise RuntimeError("omni_core_rs is required for JIT tool execution")


__all__ = [
    "JITSkillLoader",
    "ToolRecord",
    "get_jit_loader",
    "get_tools_for_skill_jit",
    "execute_skill_tool",
]
