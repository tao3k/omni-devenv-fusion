# agent/core/vector_store/index.py
"""
Index operations for vector store.

Provides skill tool indexing, sync, and index export functionality.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from common.skills_path import SKILLS_DIR
from .connection import VectorMemory, _get_logger
from .embed import batch_embed


async def create_index(self: VectorMemory, collection: str | None = None) -> bool:
    """Create vector index for a collection.

    Args:
        self: VectorMemory instance
        collection: Optional table name

    Returns:
        True if successful
    """
    store = self._ensure_store()
    if not store:
        return False

    table_name = self._get_table_name(collection)

    try:
        store.create_index(table_name)
        _get_logger().info("Vector index created", table=table_name)
        return True
    except Exception as e:
        _get_logger().error("Failed to create index", error=str(e))
        return False


async def get_tools_by_skill(self: VectorMemory, skill_name: str) -> list[dict]:
    """
    Get all indexed tools for a skill from the database.

    Retrieve tools from vector store instead of rescanning.

    Args:
        self: VectorMemory instance
        skill_name: Name of the skill (e.g., "git")

    Returns:
        List of tool metadata dictionaries
    """
    store = self._ensure_store()
    if not store:
        _get_logger().warning("Vector memory not available for get_tools_by_skill")
        return []

    try:
        tools_json = store.get_tools_by_skill(skill_name)
        tools = [json.loads(t) for t in tools_json if t]
        _get_logger().debug(f"Retrieved {len(tools)} tools for skill", skill=skill_name)
        return tools
    except Exception as e:
        _get_logger().error("Failed to get tools by skill", skill=skill_name, error=str(e))
        return []


async def index_skill_tools(self: VectorMemory, base_path: str, table_name: str = "skills") -> int:
    """
    Index all skill tools from scripts into the vector store.

    Uses Rust scanner to discover @skill_command decorated functions.
    Note: This method uses placeholder schemas. Use index_skill_tools_with_schema()
    for full schema extraction.

    Args:
        self: VectorMemory instance
        base_path: Base path containing skills (e.g., "assets/skills")
        table_name: Table to store tools (default: "skills")

    Returns:
        Number of tools indexed
    """
    store = self._ensure_store()
    if not store:
        _get_logger().warning("Vector memory not available for index_skill_tools")
        return 0

    try:
        count = store.index_skill_tools(base_path, table_name)
        _get_logger().info(f"Indexed {count} skill tools", base_path=base_path)
        return count
    except Exception as e:
        _get_logger().error("Failed to index skill tools", error=str(e))
        return 0


async def index_skill_tools_with_schema(
    self: VectorMemory, base_path: str, table_name: str = "skills"
) -> int:
    """
    Index all skill tools with full schema extraction.

    Uses Rust scanner to discover tools, then Python to extract
    parameter schemas using the agent.scripts.extract_schema module.

    This is the preferred method for production use as it provides proper
    schema information for tool discovery and validation.

    Args:
        self: VectorMemory instance
        base_path: Base path containing skills (e.g., "assets/skills")
        table_name: Table to store tools (default: "skills")

    Returns:
        Number of tools indexed
    """
    store = self._ensure_store()
    if not store:
        _get_logger().warning("Vector memory not available for index_skill_tools_with_schema")
        return 0

    try:
        # Step 1: Scan for tools using Rust (gets file paths, function names)
        tool_jsons = store.scan_skill_tools_raw(base_path)
        if not tool_jsons:
            _get_logger().info("No tools found in scripts")
            return 0

        _get_logger().info(f"Scanned {len(tool_jsons)} tools from scripts")

        # Step 2: Import schema extractor
        from agent.scripts.extract_schema import extract_function_schema

        # Step 3: Build documents for indexing
        ids = []
        contents = []
        metadatas = []

        for tool_json in tool_jsons:
            try:
                tool = json.loads(tool_json)
            except json.JSONDecodeError:
                continue

            tool_name = f"{tool.get('skill_name', '')}.{tool.get('tool_name', '')}"
            ids.append(tool_name)

            # Use description as content
            contents.append(tool.get("description", tool_name))

            # Generate input schema using Python
            file_path = tool.get("file_path", "")
            func_name = tool.get("function_name", "")

            input_schema = "{}"
            if file_path and func_name:
                try:
                    schema = extract_function_schema(file_path, func_name)
                    input_schema = json.dumps(schema, ensure_ascii=False)
                except Exception as e:
                    _get_logger().warning(f"Failed to extract schema for {tool_name}: {e}")

            # Compute file hash for incremental updates
            file_hash = ""
            if file_path:
                try:
                    content = Path(file_path).read_text(encoding="utf-8")
                    file_hash = hashlib.sha256(content.encode()).hexdigest()
                except Exception:
                    pass

            # Build metadata
            metadata = {
                "skill_name": tool.get("skill_name", ""),
                "tool_name": tool.get("tool_name", ""),
                "file_path": file_path,
                "function_name": func_name,
                "execution_mode": tool.get("execution_mode", "script"),
                "keywords": tool.get("keywords", []),
                "file_hash": file_hash,
                "input_schema": input_schema,
                "docstring": tool.get("docstring", ""),
            }
            metadatas.append(json.dumps(metadata, ensure_ascii=False))

        # Step 4: Generate embeddings and add to store
        if not ids:
            return 0

        # Generate embeddings
        vectors = batch_embed(contents)

        # Add to store
        store.add_documents(table_name, ids, vectors, contents, metadatas)

        _get_logger().info(f"Indexed {len(ids)} skill tools with schemas", base_path=base_path)
        return len(ids)

    except Exception as e:
        _get_logger().error("Failed to index skill tools with schema", error=str(e))
        import traceback

        traceback.print_exc()
        return 0


async def sync_skills(self: VectorMemory, base_path: str, table_name: str = "skills") -> dict:
    """
    Incrementally sync skill tools with the database.

    Efficient incremental update using file hash comparison.

    This method:
    1. Fetches current DB state (path -> hash mapping)
    2. Scans filesystem for current state (using Rust scanner)
    3. Computes diff: Added, Modified, Deleted
    4. Executes minimal updates

    Args:
        self: VectorMemory instance
        base_path: Base path containing skills (e.g., "assets/skills")
        table_name: Table to store tools (default: "skills")

    Returns:
        Dict with keys: added, modified, deleted, total
    """
    store = self._ensure_store()
    if not store:
        _get_logger().warning("Vector memory not available for sync_skills")
        return {"added": 0, "modified": 0, "deleted": 0, "total": 0}

    @dataclass
    class SyncStats:
        added: int = 0
        modified: int = 0
        deleted: int = 0

    stats = SyncStats()

    # Use SKILLS_DIR for consistent path handling
    skills_dir = SKILLS_DIR()
    skills_dir_resolved = skills_dir.resolve()
    skills_dir_str = str(skills_dir_resolved)

    def normalize_path(p: str) -> str:
        """Normalize path to relative path from SKILLS_DIR."""
        try:
            path = Path(p)

            if path.is_absolute():
                # Absolute path - make relative to skills_dir
                resolved = path.resolve()
                try:
                    return str(resolved.relative_to(skills_dir_resolved))
                except ValueError:
                    return str(resolved)
            else:
                # Relative path - may already have skills_dir prefix
                p_str = p

                # Handle path with skills_dir prefix
                if skills_dir_str in p_str:
                    p_str = p_str.replace(skills_dir_str, "").strip("/")

                # Handle path with "assets/skills/" prefix (from Rust scanner)
                if p_str.startswith("assets/skills/"):
                    p_str = p_str[len("assets/skills/") :]

                # Handle double assets/skills/ prefix (edge case)
                while p_str.startswith("assets/skills/"):
                    p_str = p_str[len("assets/skills/") :]

                return p_str
        except Exception:
            return p

    try:
        # Step 1: Get existing file hashes from DB
        _get_logger().debug("Fetching existing file hashes from database...")
        if hasattr(store, "get_all_file_hashes"):
            existing_json = store.get_all_file_hashes(table_name)
            existing: Dict[str, Dict] = json.loads(existing_json) if existing_json else {}
        else:
            _get_logger().warning("get_all_file_hashes not available, using empty state")
            existing = {}

        # Normalize existing paths for comparison
        existing_normalized = {normalize_path(p): v for p, v in existing.items()}
        existing_paths = set(existing_normalized.keys())

        _get_logger().debug(f"Found {len(existing_paths)} existing tools in database")

        # Step 2: Scan current filesystem using Rust scanner
        _get_logger().debug("Scanning filesystem for skill tools...")
        current_jsons = store.scan_skill_tools_raw(base_path)
        if not current_jsons:
            _get_logger().debug("No tools found in skills directory")
            return {"added": 0, "modified": 0, "deleted": 0, "total": 0}

        current_tools = []
        for tool_json in current_jsons:
            try:
                current_tools.append(json.loads(tool_json))
            except json.JSONDecodeError:
                continue

        # Normalize current paths and update tools with normalized paths
        current_paths = set()
        for tool in current_tools:
            orig_path = tool.get("file_path", "")
            norm_path = normalize_path(orig_path)
            tool["file_path"] = norm_path
            current_paths.add(norm_path)

        _get_logger().debug(f"Found {len(current_tools)} tools in filesystem")

        # Step 3: Compute Diff
        to_add = []

        for tool in current_tools:
            path = tool.get("file_path", "")
            if not path:
                continue

            # Added: path not in DB
            if path not in existing_paths:
                to_add.append(tool)

        # Find deleted files
        to_delete_paths = existing_paths - current_paths

        _get_logger().debug(
            f"Diff results: +{len(to_add)} added, ~0 modified, -{len(to_delete_paths)} deleted"
        )

        # Step 4: Execute Updates

        # Delete stale records
        if to_delete_paths:
            paths_to_delete = []
            for norm_path in to_delete_paths:
                for orig_path, data in existing.items():
                    if normalize_path(orig_path) == norm_path:
                        paths_to_delete.append(orig_path)

            if paths_to_delete:
                _get_logger().debug(f"Deleting {len(paths_to_delete)} stale tools...")
                store.delete_by_file_path(table_name, paths_to_delete)
                stats.deleted = len(paths_to_delete)

        # Process added tools only
        work_items = to_add
        if work_items:
            _get_logger().debug(f"Processing {len(work_items)} changed tools...")

            # Build documents for indexing
            ids = []
            contents = []
            metadatas = []

            for tool in work_items:
                tool_name = f"{tool.get('skill_name', '')}.{tool.get('tool_name', '')}"
                ids.append(tool_name)
                contents.append(tool.get("description", tool_name))

                # Use input_schema from Rust scanner
                input_schema = tool.get("input_schema", "{}")
                file_path = tool.get("file_path", "")

                # Build metadata
                metadata = {
                    "skill_name": tool.get("skill_name", ""),
                    "tool_name": tool.get("tool_name", ""),
                    "file_path": file_path,
                    "function_name": tool.get("function_name", ""),
                    "execution_mode": tool.get("execution_mode", "script"),
                    "keywords": tool.get("keywords", []),
                    "file_hash": tool.get("file_hash", ""),
                    "input_schema": input_schema,
                    "docstring": tool.get("docstring", ""),
                }
                metadatas.append(json.dumps(metadata, ensure_ascii=False))

            # Generate embeddings and add to store
            vectors = batch_embed(contents)
            store.add_documents(table_name, ids, vectors, contents, metadatas)

            stats.added = len(to_add)
            stats.modified = 0

        # Calculate total
        total = len(current_tools)

        # Log result
        if stats.added > 0 or stats.modified > 0 or stats.deleted > 0:
            _get_logger().info(
                f"Sync complete: +{stats.added} added, ~{stats.modified} modified, -{stats.deleted} deleted, {total} total"
            )
        else:
            _get_logger().debug(
                f"Sync complete: +{stats.added} added, ~{stats.modified} modified, -{stats.deleted} deleted, {total} total"
            )

        return {
            "added": stats.added,
            "modified": stats.modified,
            "deleted": stats.deleted,
            "total": total,
        }

    except Exception as e:
        _get_logger().error("Failed to sync skill tools", error=str(e))
        import traceback

        traceback.print_exc()
        return {"added": 0, "modified": 0, "deleted": 0, "total": 0}


async def export_skill_index(self: VectorMemory, output_path: str | None = None) -> dict:
    """
    Export skill tools from vector store to skill_index.json.

    This method:
    1. Fetches all tools from the skills table
    2. Groups them by skill_name
    3. Builds skill-level metadata from tools
    4. Merges with existing skill_index.json (preserves authors, compliance, etc.)
    5. Writes the result to assets/skills/skill_index.json

    Args:
        self: VectorMemory instance
        output_path: Optional custom path for the output file.
                     Defaults to SKILLS_DIR / "skill_index.json"

    Returns:
        Dict with keys: skills_exported, tools_exported, output_path
    """
    from yaml import safe_load

    store = self._ensure_store()
    if not store:
        _get_logger().warning("Vector memory not available for export_skill_index")
        return {"skills_exported": 0, "tools_exported": 0, "output_path": ""}

    # Determine output path
    if output_path is None:
        output_path = str(SKILLS_DIR() / "skill_index.json")
    output_file = Path(output_path)

    try:
        # Step 1: Load existing skill_index.json for merging
        existing_skills: Dict[str, dict] = {}
        if output_file.exists():
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    for skill in existing_data:
                        # Extract skill name (handle both quoted and unquoted formats)
                        name = skill.get("name", "")
                        if name:
                            # Remove quotes if present (old format had quoted names)
                            if name.startswith('"') and name.endswith('"'):
                                name = name[1:-1]
                            existing_skills[name] = skill
                _get_logger().debug(f"Loaded {len(existing_skills)} existing skills for merging")
            except json.JSONDecodeError as e:
                _get_logger().warning(f"Failed to parse existing skill_index.json: {e}")
                existing_skills = {}

        # Step 2: Fetch all tools from vector store
        count = store.count("skills")
        if count == 0:
            _get_logger().warning("No tools found in skills table")
            return {"skills_exported": 0, "tools_exported": 0, "output_path": output_path}

        # Get all tools by scanning skills directory
        all_tools: List[Dict] = []
        current_jsons = store.scan_skill_tools_raw(str(SKILLS_DIR()))
        for tool_json in current_jsons:
            try:
                tool = json.loads(tool_json)
                all_tools.append(
                    {
                        "skill_name": tool.get("skill_name", ""),
                        "tool_name": tool.get("tool_name", ""),
                        "metadata": tool,
                    }
                )
            except json.JSONDecodeError:
                continue

        # Step 3: Group tools by skill
        skills_tools: Dict[str, List[Dict]] = {}
        for tool in all_tools:
            skill_name = tool.get("skill_name", "")
            if skill_name:
                if skill_name not in skills_tools:
                    skills_tools[skill_name] = []
                skills_tools[skill_name].append(tool)

        # Step 4: Build skill entries
        skill_entries = []
        for skill_name, tools in skills_tools.items():
            # Get existing skill data for merging
            # First try to match by directory name (current format)
            existing = existing_skills.get(skill_name, {})

            # If no match, try to find by title case name from SKILL.md
            if not existing:
                title_name = skill_name.replace("_", " ").title()
                # Handle special cases
                title_name = title_name.replace("Crawl4Ai", "crawl4ai")
                title_name = title_name.replace("Note Taker", "note_taker")
                title_name = title_name.replace("Test Skill", "test-skill")
                existing = existing_skills.get(title_name, {})

            # Read SKILL.md for display name if available
            skill_dir = SKILLS_DIR() / skill_name
            skill_display_name = skill_name
            skill_description = existing.get("description", f'"The {skill_name} skill."')
            skill_version = existing.get("version", '"1.0.0"')
            skill_path = existing.get("path", f'"assets/skills/{skill_name}"')
            skill_routing_keywords = existing.get("routing_keywords", [])
            skill_intents = existing.get("intents", [])
            skill_authors = existing.get("authors", ["omni-dev-fusion"])
            skill_docs_available = existing.get(
                "docs_available",
                {
                    "skill_md": True,
                    "readme": False,
                    "guide": False,
                    "prompts": False,
                    "tests": False,
                },
            )
            skill_oss_compliant = existing.get("oss_compliant", [])
            skill_compliance_details = existing.get("compliance_details", [])

            # Parse SKILL.md for metadata
            skill_md_path = skill_dir / "SKILL.md"
            if skill_md_path.exists():
                try:
                    import re

                    content = skill_md_path.read_text(encoding="utf-8")
                    # Extract YAML frontmatter
                    yaml_match = re.search(r"^---\n([\s\S]*?)\n---", content)
                    if yaml_match:
                        yaml_content = yaml_match.group(1)
                        yaml_data = safe_load(yaml_content) or {}
                        # Extract values from YAML
                        if "name" in yaml_data:
                            skill_display_name = str(yaml_data["name"]).strip('"')
                        if "description" in yaml_data:
                            skill_description = yaml_data["description"]
                        if "version" in yaml_data:
                            skill_version = yaml_data["version"]
                        if "routing_keywords" in yaml_data:
                            kw = yaml_data["routing_keywords"]
                            if isinstance(kw, list):
                                skill_routing_keywords = [str(k).strip() for k in kw]
                        if "intents" in yaml_data:
                            intents = yaml_data["intents"]
                            if isinstance(intents, list):
                                skill_intents = [str(i).strip() for i in intents]
                        if "authors" in yaml_data:
                            authors = yaml_data["authors"]
                            if isinstance(authors, list):
                                skill_authors = [str(a).strip() for a in authors]
                except Exception as e:
                    _get_logger().debug(f"Failed to parse SKILL.md for {skill_name}: {e}")

            # Build tools list from current tools
            tool_list = []
            for tool in tools:
                meta = tool.get("metadata", {})
                tool_entry = {
                    "name": meta.get("tool_name", ""),
                    "description": meta.get("description", ""),
                }
                tool_list.append(tool_entry)

            # Build skill entry
            skill_entry = {
                "name": skill_display_name,
                "description": skill_description,
                "version": skill_version,
                "path": skill_path,
                "tools": tool_list,
                "routing_keywords": skill_routing_keywords,
                "intents": skill_intents,
                "authors": skill_authors,
                "docs_available": skill_docs_available,
                "oss_compliant": skill_oss_compliant,
                "compliance_details": skill_compliance_details,
            }
            skill_entries.append(skill_entry)

        # Step 5: Write to file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(skill_entries, f, indent=2, ensure_ascii=False)

        _get_logger().info(
            f"Exported {len(skill_entries)} skills, {len(all_tools)} tools to {output_path}"
        )

        return {
            "skills_exported": len(skill_entries),
            "tools_exported": len(all_tools),
            "output_path": output_path,
        }

    except Exception as e:
        _get_logger().error("Failed to export skill index", error=str(e))
        import traceback

        traceback.print_exc()
        return {"skills_exported": 0, "tools_exported": 0, "output_path": ""}
