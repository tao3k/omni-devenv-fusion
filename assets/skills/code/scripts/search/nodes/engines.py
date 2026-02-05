"""
Search Engines - Unified interface to AST, Vector, and Grep search

Wraps:
- AST Engine: code_tools.smart_ast.engine.SmartAstEngine (using omni.ast Rust bindings)
- Vector Engine: omni.core.knowledge.librarian.Librarian
- Grep Engine: ripgrep via subprocess
"""

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from ..state import SearchGraphState, SearchResult


logger = logging.getLogger(__name__)


def get_project_root() -> Path:
    """Get project root from environment or current directory."""
    return Path(os.environ.get("PRJ_ROOT", "."))


def run_ast_search(query: str) -> List[SearchResult]:
    """Execute AST-based structural search using SmartAstEngine."""
    results: List[SearchResult] = []

    try:
        from code_tools.scripts.smart_ast.engine import SmartAstEngine

        engine = SmartAstEngine()

        # Extract structural pattern from query
        pattern = extract_ast_pattern(query)
        if not pattern:
            return results

        # Execute AST search
        output = engine.execute(
            query=pattern,
            path=str(get_project_root()),
            mode="pattern",
        )

        # Parse output from SmartAstEngine
        if not output or isinstance(output, str) and not output.strip():
            return results

        # Parse results
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("//") or line.startswith("Total"):
                continue

            # Parse "L57   class Librarian: ..."
            match = re.match(r"L(\d+)\s+(.+)", line)
            if match:
                line_num = int(match.group(1))
                content = match.group(2).strip()
                file_match = re.search(r"// File: (.+)", output)
                file_path = file_match.group(1) if file_match else str(get_project_root())

                results.append(
                    {
                        "engine": "ast",
                        "file": file_path,
                        "line": line_num,
                        "content": content,
                        "score": 0.95,
                    }
                )

    except ImportError as e:
        logger.warning(f"SmartAstEngine not available: {e}")
    except Exception as e:
        logger.warning(f"AST search error: {e}")

    return results


def extract_ast_pattern(query: str) -> Optional[str]:
    """Extract AST search pattern from natural language query."""
    # class Foo -> pattern "class $NAME"
    class_match = re.search(r"class\s+(\w+)", query)
    if class_match:
        return f"class {class_match.group(1)}"

    # Find the class X / definition of class X -> pattern "class $NAME"
    class_match = re.search(r"(?:definition\s+of\s+|the\s+)?class\s+(\w+)", query, re.IGNORECASE)
    if class_match:
        return f"class {class_match.group(1)}"

    # Handle query ending with "class" - find preceding class name
    if query.strip().lower().endswith("class"):
        match = re.search(r"(\w+)\s+class$", query, re.IGNORECASE)
        if match:
            return f"class {match.group(1)}"

    # def foo / fn bar -> pattern "fn $NAME" or "def $NAME"
    fn_match = re.search(r"(def|fn)\s+(\w+)", query)
    if fn_match:
        keyword = fn_match.group(1)  # Preserve original keyword (def or fn)
        name = fn_match.group(2)
        return f"{keyword} {name}"

    # impl Foo -> pattern "impl $NAME"
    impl_match = re.search(r"impl\s+(\w+)", query)
    if impl_match:
        return f"impl {impl_match.group(1)}"

    # struct Foo -> pattern "struct $NAME"
    struct_match = re.search(r"struct\s+(\w+)", query)
    if struct_match:
        return f"struct {struct_match.group(1)}"

    # If query looks like a pattern already (e.g., "connect($$$)", "class $NAME")
    if re.search(r"^[a-z]+\S*", query) and ("(" in query or "$" in query):
        return query

    return None


def run_vector_search(query: str, limit: int = 10) -> List[SearchResult]:
    """Execute semantic search via Librarian."""
    results: List[SearchResult] = []

    try:
        from omni.core.runtime.services import get_librarian

        librarian = get_librarian()
        if librarian is None:
            return results

        raw_results = librarian.search_raw(query, limit=limit)

        for r in raw_results:
            metadata = r.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            results.append(
                {
                    "engine": "vector",
                    "file": r.get("path", "unknown"),
                    "line": metadata.get("start_line", 0) or 0,
                    "content": r.get("text", "")[:200],
                    "score": r.get("score", 0.0),
                }
            )

    except ImportError:
        logger.warning("Librarian not available")
    except Exception as e:
        logger.warning(f"Vector search error: {e}")

    return results


def run_grep_search(query: str, file_pattern: Optional[str] = None) -> List[SearchResult]:
    """Execute exact text search via ripgrep."""
    results: List[SearchResult] = []

    if not shutil.which("rg"):
        logger.warning("ripgrep not installed")
        return results

    try:
        root = get_project_root()

        cmd = [
            "rg",
            "--json",
            "--line-number",
        ]

        for glob in ["!*test*", "!*_test.*", "!*_pb2.*"]:
            cmd.extend(["--glob", glob])

        if file_pattern:
            cmd.extend(["--glob", file_pattern])

        cmd.append(query)
        cmd.append(str(root))

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    match = data.get("match", {})
                    results.append(
                        {
                            "engine": "grep",
                            "file": data.get("path", {}).get("text", ""),
                            "line": match.get("line_number", 0) or 0,
                            "content": match.get("context", {}).get("text", "")[:200],
                            "score": 0.8,
                        }
                    )
                except (json.JSONDecodeError, KeyError):
                    continue

    except Exception as e:
        logger.warning(f"Grep search error: {e}")

    return results


# Graph node wrappers


def node_run_ast_search(state: SearchGraphState) -> dict:
    """Graph node: Execute AST search."""
    results = run_ast_search(state["query"])
    return {"raw_results": results}


def node_run_vector_search(state: SearchGraphState) -> dict:
    """Graph node: Execute Vector search."""
    results = run_vector_search(state["query"])
    return {"raw_results": results}


def node_run_grep_search(state: SearchGraphState) -> dict:
    """Graph node: Execute Grep search."""
    results = run_grep_search(state["query"])
    return {"raw_results": results}
