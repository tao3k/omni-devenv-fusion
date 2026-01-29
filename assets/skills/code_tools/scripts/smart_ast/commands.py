"""smart_ast/commands.py - The One Command to Rule Them All"""

from typing import Any, Optional
import os
from omni.foundation.api.decorators import skill_command
from .engine import SmartAstEngine

_engine = SmartAstEngine()


@skill_command(
    name="smart_ast",
    category="search",
    description="""
    UNIFIED Code Intelligence & Refactoring Tool.
    
    This is the single entry point for all code exploration and modification tasks.
    It supports multiple modes:
    1. Search: query='pattern' or shorthand ('classes', 'functions')
    2. Refactor: provide 'rewrite' string for AST-based replacement
    3. Intelligence: query='analyze' to get a structural health report
    4. Register: mode='register' to save a new YAML rule
    5. Patch: mode='patch' for exact string-based replacement (like apply_file_edit)

    Args:
        - query: str - Pattern, shorthand, rule, or action ('analyze') (required)
        - path: str = . - Target directory or file
        - rewrite: Optional[str] - New code structure for refactoring
        - dry_run: bool = true - Preview changes before applying
        - mode: str = auto - 'auto', 'pattern', 'rule', 'register', 'patch'
        - language: Optional[str] - Programming language hint
        - search_text: Optional[str] - Used ONLY in mode='patch' (text to find)
    """,
)
def smart_ast(
    query: str,
    path: str = ".",
    rewrite: Optional[str] = None,
    dry_run: bool = True,
    mode: str = "auto",
    language: Optional[str] = None,
    search_text: Optional[str] = None,
) -> Any:
    """Unified command for all code tools."""

    # 1. SPECIAL MODE: Analyze (Intelligence Report)
    if query == "analyze" or mode == "analyze":
        return _analyze_intelligence(path, language)

    # 2. SPECIAL MODE: Register (Save Rule)
    if mode == "register":
        return _register_rule(query, rewrite, dry_run)  # reuse query as name, rewrite as yaml

    # 3. SPECIAL MODE: Patch (String-based edit)
    if mode == "patch":
        from omni.foundation.config.paths import ConfigPaths

        if not search_text or not rewrite:
            return "Error: mode='patch' requires 'search_text' and 'rewrite' (new text)."
        return _apply_patch(path, search_text, rewrite, ConfigPaths())

    # 4. DEFAULT: Search and AST-Refactor
    return _engine.execute(query, path, mode, language, rewrite, dry_run)


def _analyze_intelligence(path: str, language: Optional[str]) -> str:
    rules_to_run = ["resource_leaks", "unawaited_async", "complexity", "architecture"]
    report = [f"// 🧠 CODE INTELLIGENCE REPORT: {path}", "=" * 40]
    for rule in rules_to_run:
        res = _engine.execute(rule, path, language=language)
        if "[No matches found" not in res and "Error" not in res:
            report.append(f"\n[!] ISSUE FOUND: {rule.upper()}\n{res[:500]}...")
        else:
            report.append(f"\n[✓] {rule.upper()}: Clear")
    return "\n".join(report)


def _register_rule(name: str, rule_yaml: str, overwrite: bool) -> str:
    if not rule_yaml:
        return "Error: rule_yaml required in 'rewrite' parameter."
    safe_name = "".join(c for c in name if c.isalnum() or c in ("_", "-")).lower()
    rule_path = os.path.join(_engine.rules_dir, f"{safe_name}.yaml")
    if os.path.exists(rule_path) and not overwrite:
        return f"Error: Rule '{safe_name}' already exists."
    with open(rule_path, "w") as f:
        f.write(rule_yaml)
    return f"Registered rule '{safe_name}' at {rule_path}."


def _apply_patch(file_path: str, search_text: str, replace_text: str, paths: Any) -> Any:
    try:
        root = paths.project_root
        target = (root / file_path).resolve()
        if not str(target).startswith(str(root)):
            return "Error: Access denied."
        content = target.read_text(encoding="utf-8")
        if search_text not in content:
            return "Error: search_text not found."
        if content.count(search_text) > 1:
            return f"Error: Ambiguous match ({content.count(search_text)} found)."
        target.write_text(content.replace(search_text, replace_text), encoding="utf-8")
        return f"Successfully patched {file_path}."
    except Exception as e:
        return f"Patch failed: {e}"
