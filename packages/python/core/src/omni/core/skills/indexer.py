"""
omni.core.skills.indexer
Skill Indexing Pipeline: Python AST -> Python Embed -> Rust DB

Orchestrates the ingestion of skill code into the vector memory.
Pipeline: Python AST (ast module) -> Embedding Service -> Rust Vector Store
"""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from typing import Any

import structlog

from omni.foundation.services.embedding import EmbeddingService, get_embedding_service

logger = logging.getLogger(__name__)


class SkillIndexer:
    """Handles the lifecycle of skill indexing: Scanning, Embedding, and Storing.

    This pipeline orchestrates:
    1. Rust Scanner - Hyper-fast function extraction
    2. Python Embedding - Semantic vector generation
    3. Rust Vector Store - LanceDB persistence with hybrid search
    """

    def __init__(
        self,
        vector_store: Any,  # PyVectorStore
        embedding_service: EmbeddingService | None = None,
        project_root: str | None = None,
    ):
        """Initialize the skill indexer.

        Args:
            vector_store: Rust PyVectorStore instance for persistence
            embedding_service: Optional EmbeddingService (singleton if not provided)
            project_root: Optional project root (for future use)
        """
        self.store = vector_store
        self.embedder = embedding_service or get_embedding_service()
        self.project_root = project_root

    @property
    def table_name(self) -> str:
        """Default table name for skill registry."""
        return "skills_registry"

    async def index_file(self, file_path: str) -> int:
        """Scan a Python file, generate embeddings, and upsert to LanceDB.

        Args:
            file_path: Path to the Python file to index

        Returns:
            Number of functions/tools indexed
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"File not found: {file_path}")
                return 0

            # Step 1: Python AST Parse - Extract function metadata
            content = path.read_text()
            tree = ast.parse(content)

            functions = []
            # Only look at top-level nodes (not nested in classes or other functions)
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Extract docstring
                    docstring = ast.get_docstring(node) or ""

                    # Extract arguments
                    args_list = []
                    for arg in node.args.args:
                        arg_info = {
                            "name": arg.arg,
                            "type": ast.get_source_segment(content, arg.annotation)
                            if arg.annotation
                            else "Any",
                        }
                        args_list.append(arg_info)

                    # Extract return type
                    return_type = "Any"
                    if node.returns:
                        return_type = ast.get_source_segment(content, node.returns) or "Any"

                    functions.append(
                        {
                            "name": node.name,
                            "docstring": docstring,
                            "args": args_list,
                            "return_type": return_type,
                        }
                    )

            if not functions:
                logger.debug(f"No functions found in {path.name}")
                return 0

            logger.info(f"Scanned {len(functions)} functions from {path.name}")

            # Step 2: Python Embedding - Batch semantic vector generation
            texts_to_embed = [
                f"{func.get('name', '')}: {func.get('docstring', '')}" for func in functions
            ]

            vectors = self.embedder.embed_batch(texts_to_embed)

            # Step 3: Prepare records for Rust DB
            ids: list[str] = []
            vector_list: list[list[float]] = []
            contents: list[str] = []
            metadatas: list[str] = []

            for func, vector in zip(functions, vectors):
                # Handle vector: could be list, numpy array, or nested structure
                vector_serialized = vector
                if hasattr(vector, "tolist"):
                    vector_serialized = vector.tolist()
                elif isinstance(vector, list):
                    if len(vector) > 0 and hasattr(vector[0], "tolist"):
                        # Nested list (e.g., [[0.1, 0.2], [0.3, 0.4]])
                        vector_serialized = [
                            v.tolist() if hasattr(v, "tolist") else v for v in vector
                        ]

                # Construct unique tool ID: module_path:function_name
                module_path = str(path)
                tool_id = f"{module_path}:{func.get('name', '')}"

                ids.append(tool_id)
                vector_list.append(vector_serialized)
                contents.append(func.get("docstring", ""))

                metadata = {
                    "name": func.get("name", ""),
                    "module": module_path,
                    "file_path": str(path),
                    "args": func.get("args", []),
                    "return_type": func.get("return_type", "Any"),
                    "docstring": func.get("docstring", "")[:500],
                }
                metadatas.append(json.dumps(metadata))

            # Ensure vectors are plain lists (not numpy arrays)
            vector_list_serialized = []
            for v in vector_list:
                if hasattr(v, "tolist"):
                    vector_list_serialized.append(v.tolist())
                elif isinstance(v, list):
                    vector_list_serialized.append(v)
                else:
                    vector_list_serialized.append(list(v))

            # Step 4: Rust-native batch upsert to LanceDB
            self.store.add_documents(
                table_name=self.table_name,
                ids=ids,
                vectors=vector_list_serialized,
                contents=contents,
                metadatas=metadatas,
            )

            logger.info(f"Indexed {len(ids)} tools from {path.name}")
            return len(ids)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse scan result from {file_path}: {e}")
            return 0
        except SyntaxError as e:
            logger.debug(f"Syntax error in {file_path}: {e}")
            return 0
        except Exception as e:
            logger.error(f"Failed to index {file_path}: {e}")
            return 0

    async def remove_file(self, file_path: str) -> int:
        """Remove all skills associated with a file path.

        Args:
            file_path: Path to the file to remove

        Returns:
            Number of records deleted
        """
        try:
            self.store.delete_by_file_path(
                table_name=self.table_name,
                file_paths=[file_path],
            )
            logger.info(f"Removed skills for {file_path}")
            return 1
        except Exception as e:
            logger.error(f"Failed to remove skills for {file_path}: {e}")
            return 0

    async def reindex_file(self, file_path: str) -> int:
        """Remove then re-index a file (for updates).

        Args:
            file_path: Path to the file to re-index

        Returns:
            Number of functions/tools indexed
        """
        await self.remove_file(file_path)
        return await self.index_file(file_path)

    async def index_directory(self, directory: str, pattern: str = "**/*.py") -> dict[str, int]:
        """Index all Python files in a directory.

        Args:
            directory: Directory to scan
            pattern: Glob pattern for files to include

        Returns:
            Dict mapping file paths to count of indexed functions
        """
        from pathlib import Path as P
        from fnmatch import fnmatch

        base = P(directory)
        results: dict[str, int] = {}

        for py_file in base.rglob("*.py"):
            # Skip test files and __pycache__
            if fnmatch(py_file.name, "*test*.py"):
                continue
            if "__pycache__" in py_file.parts:
                continue

            count = await self.index_file(str(py_file))
            if count > 0:
                results[str(py_file)] = count

        return results

    async def get_index_stats(self) -> dict[str, Any]:
        """Get statistics about the current skill index.

        Returns:
            Dict with index statistics
        """
        try:
            count = self.store.count(self.table_name)
            return {
                "table_name": self.table_name,
                "tool_count": count,
                "embedding_backend": self.embedder.backend,
                "embedding_dimension": self.embedder.dimension,
            }
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {"error": str(e)}
