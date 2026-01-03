"""
src/agent/capabilities/skill_manager.py
The Interface between the Brain and the Skill Kernel.
"""
import json
from mcp.server.fastmcp import FastMCP
from agent.core.skill_registry import get_skill_registry


def register_skill_tools(mcp: FastMCP):
    """Register skill management tools."""
    registry = get_skill_registry()

    @mcp.tool()
    async def list_available_skills() -> str:
        """
        [Skill System] List all discoverable skills in the library.
        """
        skills = registry.list_available_skills()
        if not skills:
            return "No skills found in agent/skills/."

        descriptions = []
        for skill in skills:
            manifest = registry.get_skill_manifest(skill)
            if manifest:
                descriptions.append(f"- **{skill}**: {manifest.description}")
            else:
                descriptions.append(f"- **{skill}**")

        return "Available Skills:\n" + "\n".join(descriptions)

    @mcp.tool()
    async def load_skill(skill_name: str) -> str:
        """
        [Skill System] Dynamically load a skill's tools and knowledge.
        """
        success, message = registry.load_skill(skill_name, mcp)

        if not success:
            return f"Failed to load '{skill_name}': {message}"

        context = registry.get_skill_context(skill_name)

        return f"""
Skill '{skill_name}' loaded successfully!

{message}

=== PROCEDURAL KNOWLEDGE ({skill_name.upper()}) ===
{context}
==================================================
"""

    @mcp.tool()
    async def get_active_skills() -> str:
        """Check which skills are currently loaded in memory."""
        loaded = list(registry.loaded_skills.keys())
        if not loaded:
            return "No skills currently loaded."
        return f"Active Skills: {', '.join(loaded)}"

    @mcp.tool()
    async def skill(skill: str, call: str) -> str:
        """
        [Auto-Load] Execute a skill operation with automatic skill loading.

        Usage:
        - skill("filesystem", 'list_directory(path=".")')
        - skill("filesystem", 'read_file(path="README.md")')
        - skill("filesystem", 'write_file(path="test.txt", content="hello")')
        - skill("filesystem", 'search_files(pattern="*.py")')
        - skill("git", 'git_status()')
        - skill("git", 'smart_commit(message="feat: add new feature")')

        Args:
            skill: The skill to use (filesystem, git, python, etc.)
            call: Function call string like 'operation(arg1="value1", arg2="value2")'
        """
        # Parse the call string
        import ast

        try:
            # Parse function call syntax
            node = ast.parse(call, mode='eval')
            call_node = node.body

            if not isinstance(call_node, ast.Call):
                return f"Invalid call syntax: {call}"

            operation = call_node.func.id if isinstance(call_node.func, ast.Name) else None
            if not operation:
                return f"Could not parse operation from: {call}"

            # Parse arguments
            kwargs = {}
            for kw in call_node.keywords:
                if isinstance(kw.value, ast.Constant):
                    kwargs[kw.arg] = kw.value.value
                elif isinstance(kw.value, ast.Dict):
                    # Handle dict literals
                    kwargs[kw.arg] = {}
                    for k, v in zip(kw.value.keys, kw.value.values):
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                            kwargs[kw.arg][k.value] = v.value

        except SyntaxError as e:
            return f"Invalid call syntax: {call}\nError: {e}"

        return await _execute_skill_operation(skill, operation, kwargs, mcp, registry)

    @mcp.tool()
    async def invoke_skill(skill: str, tool: str, args: dict) -> str:
        """
        [Structured] Execute a skill operation with structured arguments.

        This is a safer alternative to skill() that avoids AST parsing issues
        with special characters (quotes, newlines, etc.).

        Usage:
        - invoke_skill("filesystem", "list_directory", {"path": "."})
        - invoke_skill("git", "git_status", {})
        - invoke_skill("git", "smart_commit", {"message": "feat: add feature"})

        Args:
            skill: The skill name (e.g., "filesystem", "git", "terminal")
            tool: The function name to call (e.g., "list_directory", "git_status")
            args: Arguments as a JSON object/dict
        """
        return await _execute_skill_operation(skill, tool, args, mcp, registry)


async def _execute_skill_operation(skill: str, operation: str, kwargs: dict, mcp: FastMCP, registry) -> str:
    """Common execution logic for skill() and invoke_skill()."""
    # Auto-load skill if not already loaded
    if skill not in registry.loaded_skills:
        success, msg = registry.load_skill(skill, mcp)
        if not success:
            return f"Failed to load skill '{skill}': {msg}"
        context = registry.get_skill_context(skill)
        return f"""
Skill '{skill}' auto-loaded!

{msg}

=== PROCEDURAL KNOWLEDGE ===
{context}
==================================================

Now call: invoke_skill('{skill}', '{operation}', {kwargs})"""

    # Get the loaded module
    module = registry.module_cache.get(skill)
    if not module:
        return f"Skill '{skill}' not found in module cache."

    # Execute operation (functions are now at module level)
    if hasattr(module, operation):
        func = getattr(module, operation)
        if callable(func):
            try:
                import inspect
                if inspect.iscoroutinefunction(func):
                    result = await func(**kwargs)
                else:
                    result = func(**kwargs)
                return result
            except Exception as e:
                return f"Error executing {operation}: {e}"
        else:
            return f"'{operation}' is not callable."
    else:
        return f"Operation '{operation}' not found in skill '{skill}'."
