"""
code_tools/scripts/navigation.py - Code Navigation Commands

AST-based code search and exploration (The Cartographer).

Commands:
- outline_file: Generate file skeleton/outline
- list_symbols: Extract structured symbols from file
- count_symbols: Count symbols by kind
- search_code: Search AST patterns in file
- search_directory: Search AST patterns recursively
- goto_definition: Find symbol definition location
"""

from pathlib import Path
from typing import Any

import structlog

from omni.core.skills.script_loader import skill_command
from omni.foundation.config.paths import get_project_root

logger = structlog.get_logger(__name__)

# Check if Rust bindings are available
try:
    import omni_core_rs

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logger.warning("omni_core_rs not found. CodeNavigation will use fallback.")


# =============================================================================
# Helper Types
# =============================================================================


class SymbolInfo:
    """Structured symbol information."""

    def __init__(self, name: str, kind: str, line: int, signature: str):
        self.name = name
        self.kind = kind
        self.line = line
        self.signature = signature

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "line": self.line,
            "signature": self.signature,
        }


def _parse_outline_to_symbols(outline: str, file_path: str) -> list[SymbolInfo]:
    """Parse outline output into structured SymbolInfo objects."""
    symbols = []
    for line in outline.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Parse format: L123  [class]     ClassName class name(...)
        # Or: L123  [function] func_name (params)
        if line.startswith("L") and "[" in line and "]" in line:
            try:
                # Extract line number
                parts = line.split()
                line_num = int(parts[0][1:])

                # Extract kind
                kind_start = line.find("[") + 1
                kind_end = line.find("]")
                kind = line[kind_start:kind_end].lower()

                # Extract name and signature (rest of line after kind)
                rest = line[kind_end + 1 :].strip()
                name_parts = rest.split(None, 1)
                name = name_parts[0] if name_parts else ""
                signature = name_parts[1] if len(name_parts) > 1 else ""

                symbols.append(SymbolInfo(name, kind, line_num, signature))
            except (ValueError, IndexError):
                continue

    return symbols


def _validate_path(path: str) -> tuple[Path | None, str | None]:
    """Validate path is within project root."""
    root = get_project_root()
    try:
        target = (root / path).resolve()
        if not str(target).startswith(str(root)):
            return None, "Access denied to paths outside project root."
        if not target.exists():
            return None, f"File not found: {path}"
        return target, None
    except Exception as e:
        return None, f"Path error: {e}"


@skill_command(
    name="outline_file",
    category="read",
    description="Generate a high-level outline (skeleton) of a source file.",
)
def outline_file(path: str, language: str | None = None) -> str:
    """
    Generate a high-level outline (skeleton) of a source file.

    Reduces context usage by providing symbolic representation instead of full content.
    AX Philosophy: "Map over Territory" - understand structure before diving into details.
    """
    if not RUST_AVAILABLE:
        # Fallback: simple file read (not efficient but functional)
        try:
            content = Path(path).read_text()
            lines = content.split("\n")
            outline = []
            outline.append(f"// OUTLINE: {path}")
            outline.append(f"// Total lines: {len(lines)}")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("class ") or stripped.startswith("def "):
                    outline.append(f"L{i} {stripped}")
            if not outline:
                return f"// 🗺️ OUTLINE: {path}\n[No structural symbols found.]"
            return "\n".join(outline)
        except Exception as e:
            return f"Error reading file: {str(e)}"

    try:
        outline = omni_core_rs.get_file_outline(path, language)
        if not outline or outline.strip() == "":
            return f"// 🗺️ OUTLINE: {path}\n[No structural symbols found.]"
        return outline
    except Exception as e:
        logger.error("Failed to outline file", path=path, error=str(e))
        return f"Error generating outline: {str(e)}"


@skill_command(
    name="count_symbols",
    category="read",
    description="Count the number of symbols (classes, functions, etc.) in a file.",
)
def count_symbols(path: str, language: str | None = None) -> dict[str, Any]:
    """
    Count the number of symbols (classes, functions, etc.) in a file.

    Useful for quickly assessing file complexity before reading.
    """
    if not RUST_AVAILABLE:
        return {"error": "omni_core_rs not available"}

    try:
        outline = omni_core_rs.get_file_outline(path, language)
        if "No symbols found" in outline:
            return {"total": 0, "by_kind": {}}

        # Parse outline to count symbols
        lines = outline.split("\n")
        counts: dict[str, int] = {}
        for line in lines[2:]:  # Skip header lines
            if line.strip():
                # Extract kind from [class], [function], etc.
                start = line.find("[")
                end = line.find("]")
                if start != -1 and end != -1:
                    kind = line[start + 1 : end].lower()
                    counts[kind] = counts.get(kind, 0) + 1

        return {"total": sum(counts.values()), "by_kind": counts}
    except Exception as e:
        logger.error("Failed to count symbols", path=path, error=str(e))
        return {"error": str(e)}


@skill_command(
    name="search_code",
    category="read",
    description="Search for AST patterns in a single file using ast-grep syntax.",
)
def search_code(path: str, pattern: str, language: str | None = None) -> str:
    """
    Search for AST patterns in a single file using ast-grep syntax.

    Unlike text search (grep), this searches for CODE PATTERNS, not strings.
    Perfect for finding specific code constructs like function calls, class definitions, etc.
    """
    if not RUST_AVAILABLE:
        # Fallback: simple grep (less precise but available)
        try:
            content = Path(path).read_text()
            lines = content.split("\n")
            results = [f"// SEARCH: {path}", f"// Pattern: {pattern} (fallback: text search)"]
            for i, line in enumerate(lines, 1):
                if pattern.lower() in line.lower():
                    results.append(f"L{i}: {line.strip()}")
            if len(results) == 2:
                return f"[No matches for pattern in {path}]"
            return "\n".join(results)
        except Exception as e:
            return f"Error searching file: {str(e)}"

    try:
        result = omni_core_rs.search_code(path, pattern, language)
        return result
    except Exception as e:
        logger.error("Failed to search file", path=path, pattern=pattern, error=str(e))
        return f"Error searching: {str(e)}"


@skill_command(
    name="search_directory",
    category="read",
    description="Search for AST patterns recursively in a directory.",
)
def search_directory(path: str, pattern: str, file_pattern: str | None = None) -> str:
    """
    Search for AST patterns recursively in a directory.

    Unlike naive grep, this uses AST patterns for precise, semantic matching.
    """
    if not RUST_AVAILABLE:
        return "Error: Rust bindings (omni_core_rs) not available. Run 'just build-rust' first."

    try:
        result = omni_core_rs.search_directory(path, pattern, file_pattern)
        return result
    except Exception as e:
        logger.error(
            "Failed to search directory",
            path=path,
            pattern=pattern,
            error=str(e),
        )
        return f"Error searching directory: {str(e)}"


# =============================================================================
# Symbol Navigation (The Cartographer)
# =============================================================================


@skill_command(
    name="list_symbols",
    category="read",
    description="Extract and list all symbols (classes, functions, methods) from a file in structured format.",
)
def list_symbols(file_path: str, language: str | None = None) -> list[dict]:
    """
    Extract structured symbol information from a file.

    Returns a list of symbols with their name, kind, line number, and signature.
    Useful for building index or understanding file structure programmatically.

    Example:
        [{"name": "Agent", "kind": "class", "line": 5, "signature": "class Agent:"}, ...]
    """
    target, error = _validate_path(file_path)
    if error:
        return [{"error": error}]

    if not RUST_AVAILABLE:
        # Fallback: parse file directly
        symbols = []
        try:
            content = target.read_text()
            for i, line in enumerate(content.split("\n"), 1):
                stripped = line.strip()
                if stripped.startswith("class "):
                    name = stripped.split()[1].split("(")[0]
                    symbols.append(
                        {
                            "name": name,
                            "kind": "class",
                            "line": i,
                            "signature": stripped,
                        }
                    )
                elif stripped.startswith("def ") or stripped.startswith("async def "):
                    name = stripped.split()[1].split("(")[0]
                    symbols.append(
                        {
                            "name": name,
                            "kind": "async_function"
                            if stripped.startswith("async")
                            else "function",
                            "line": i,
                            "signature": stripped,
                        }
                    )
            return symbols
        except Exception as e:
            return [{"error": str(e)}]

    try:
        outline = omni_core_rs.get_file_outline(str(target), language)
        if "No symbols found" in outline:
            return []

        parsed_symbols = _parse_outline_to_symbols(outline, str(target))
        return [s.to_dict() for s in parsed_symbols]
    except Exception as e:
        logger.error("Failed to list symbols", path=file_path, error=str(e))
        return [{"error": str(e)}]


@skill_command(
    name="goto_definition",
    category="search",
    description="Find the file and line number where a symbol is defined.",
)
def goto_definition(symbol: str, root_path: str = ".") -> list[dict]:
    """
    Search for a symbol definition across the project.

    Uses AST patterns to find class/function definitions matching the symbol name.
    Returns locations where the symbol is defined.

    Args:
        symbol: The symbol name to find (e.g., "Kernel", "Agent", "connect")
        root_path: Root directory to search in (default: current directory)

    Returns:
        List of locations with file path and line number.

    Example:
        [{"file": "src/kernel.py", "line": 42, "kind": "class", "signature": "class Kernel:"}]
    """
    root = get_project_root()
    target = (root / root_path).resolve()

    if not target.exists():
        return [{"error": f"Directory not found: {root_path}"}]

    # Build AST patterns to search for the symbol definition
    patterns = [
        f"class {symbol}",
        f"struct {symbol}",
        f"trait {symbol}",
        f"enum {symbol}",
        f"def {symbol}",
        f"async def {symbol}",
        f"fn {symbol}",
        f"interface {symbol}",
    ]

    results: list[dict] = []

    if RUST_AVAILABLE:
        try:
            for pattern in patterns:
                search_result = omni_core_rs.search_directory(str(target), pattern, "**/*.py")
                # Parse results (simplified - extract from formatted output)
                if "SEARCH:" in search_result and "Total matches:" in search_result:
                    # Parse the search output for matches
                    for line in search_result.split("\n"):
                        if line.startswith("L") and ":" in line:
                            # Format: L123:456 content
                            parts = line.split(":", 2)
                            if len(parts) >= 3:
                                try:
                                    line_num = int(parts[0][1:].strip())
                                    file_match = (
                                        search_result.split("SEARCH:")[1].split("\n")[0].strip()
                                    )
                                    results.append(
                                        {
                                            "file": file_match,
                                            "line": line_num,
                                            "kind": "class"
                                            if pattern.startswith("class")
                                            else "function",
                                            "signature": parts[2].strip(),
                                        }
                                    )
                                except (ValueError, IndexError):
                                    continue
        except Exception as e:
            logger.error("Failed to search for definition", symbol=symbol, error=str(e))
            return [{"error": str(e)}]
    else:
        # Fallback: simple grep-based search
        import subprocess

        try:
            for ext in ["py", "rs", "ts", "js"]:
                result = subprocess.run(
                    ["grep", "-rn", f"^{symbol}\\b", str(target)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split(":", 2)
                        if len(parts) >= 2:
                            try:
                                line_num = int(parts[1])
                                results.append(
                                    {
                                        "file": parts[0],
                                        "line": line_num,
                                        "kind": "definition",
                                        "context": parts[2][:100] if len(parts) > 2 else "",
                                    }
                                )
                            except (ValueError, IndexError):
                                continue
        except Exception as e:
            return [{"error": str(e)}]

    # Remove duplicates
    seen = set()
    unique_results = []
    for r in results:
        key = (r.get("file"), r.get("line"))
        if key not in seen:
            seen.add(key)
            unique_results.append(r)

    return unique_results


@skill_command(
    name="find_references",
    category="search",
    description="Find all references/usage of a symbol in the project.",
)
def find_references(symbol: str, root_path: str = ".") -> list[dict]:
    """
    Find all usages of a symbol across the project.

    Searches for patterns where the symbol is used (not just defined).
    This includes function calls, class instantiations, type annotations, etc.

    Args:
        symbol: The symbol name to search for
        root_path: Root directory to search in

    Returns:
        List of usage locations with file path and line number.
    """
    root = get_project_root()
    target = (root / root_path).resolve()

    if not target.exists():
        return [{"error": f"Directory not found: {root_path}"}]

    # Search for the symbol being used
    patterns = [
        f"{symbol}(",
        f"{symbol}.",
        f" {symbol} ",
        f"={symbol}",
    ]

    results: list[dict] = []

    if RUST_AVAILABLE:
        try:
            # Use AST search for function calls like symbol(...)
            call_pattern = f"{symbol}($$$)"
            search_result = omni_core_rs.search_directory(str(target), call_pattern, "**/*.py")

            # Parse search results
            for line in search_result.split("\n"):
                if line.startswith("L"):
                    parts = line.split(":", 2)
                    if len(parts) >= 2:
                        try:
                            line_num = int(parts[0][1:].strip())
                            results.append(
                                {
                                    "file": search_result.split("SEARCH:")[1]
                                    .split("\n")[0]
                                    .strip(),
                                    "line": line_num,
                                    "kind": "call",
                                    "context": parts[2].strip()[:100] if len(parts) > 2 else "",
                                }
                            )
                        except (ValueError, IndexError):
                            continue
        except Exception as e:
            logger.error("Failed to find references", symbol=symbol, error=str(e))
            return [{"error": str(e)}]

    # Fallback to grep if Rust not available or no results
    if not results:
        import subprocess

        try:
            result = subprocess.run(
                ["grep", "-rn", symbol, str(target)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(":", 2)
                    if len(parts) >= 2:
                        try:
                            line_num = int(parts[1])
                            results.append(
                                {
                                    "file": parts[0],
                                    "line": line_num,
                                    "kind": "reference",
                                    "context": parts[2][:100] if len(parts) > 2 else "",
                                }
                            )
                        except (ValueError, IndexError):
                            continue
        except Exception as e:
            return [{"error": str(e)}]

    return results
