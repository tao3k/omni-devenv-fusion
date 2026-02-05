"""
AST Analysis Engine using omni.ast (Rust ast-grep bindings)

Provides:
- Pattern-based code search
- Code analysis and linting with YAML rules
- Rule registration
- Structural search/replace
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_project_root() -> Path:
    """Get project root from environment or current directory."""
    return Path(os.environ.get("PRJ_ROOT", "."))


# Built-in analysis rules (inline)
BUILTIN_RULES = {
    "resource_leak": {
        "patterns": ["open($$$)", "requests.get($$$)"],
        "message": "Potential resource leak detected",
    },
    "unawaited_async": {
        "patterns": ["await $CALL"],
        "message": "Async call may not be awaited",
    },
    "complexity": {
        "patterns": [
            "for $VAR in $ITER: for $VAR2 in $ITER2",
        ],
        "message": "High complexity detected (nested loops)",
    },
}


class SmartAstEngine:
    """Unified AST search and analysis engine using omni.ast."""

    def __init__(self):
        """Initialize the engine."""
        self.rules_dir = self._find_rules_dir()
        self._load_yaml_rules()

    def _find_rules_dir(self) -> Optional[Path]:
        """Find the rules directory."""
        # Look for rules in the same directory as this module
        module_dir = Path(__file__).parent
        rules_dir = module_dir / "rules"
        if rules_dir.exists():
            return rules_dir
        return None

    def _load_yaml_rules(self) -> None:
        """Load YAML rule files."""
        if not self.rules_dir:
            return

        for yaml_file in self.rules_dir.glob("*.yaml"):
            try:
                import yaml

                with open(yaml_file, "r") as f:
                    rules = yaml.safe_load_all(f)
                    for rule in rules:
                        if rule and "id" in rule:
                            rule_id = rule["id"]
                            # Convert YAML rule to pattern-based rule
                            if "rule" in rule and "any" in rule["rule"]:
                                patterns = []
                                for item in rule["rule"]["any"]:
                                    if "pattern" in item:
                                        patterns.append(item["pattern"])
                                if patterns:
                                    BUILTIN_RULES[rule_id] = {
                                        "patterns": patterns,
                                        "message": rule.get("note", rule_id),
                                    }
                            elif "rule" in rule and "pattern" in rule["rule"]:
                                BUILTIN_RULES[rule_id] = {
                                    "patterns": [rule["rule"]["pattern"]],
                                    "message": rule.get("note", rule_id),
                                }
            except Exception as e:
                logger.debug(f"Error loading rule {yaml_file}: {e}")

    def execute(
        self,
        query: str,
        path: str = ".",
        mode: str = "pattern",
        language: str = "python",
        dry_run: bool = True,
    ) -> str:
        """Execute AST-based search or analysis."""
        try:
            import omni.ast as omni_ast

            if mode == "pattern":
                return self._search_pattern(query, path, language)
            elif mode == "analyze":
                return self._analyze_code(query, language)
            elif mode == "rule":
                return self._apply_rule(query, path, language, dry_run)
            else:
                return f"Unknown mode: {mode}"

        except ImportError as e:
            return f"Error: omni.ast not available. {e}"
        except Exception as e:
            return f"Error executing AST operation: {e}"

    def _search_pattern(self, pattern: str, target: str, language: str) -> str:
        """Search using AST pattern."""
        try:
            import omni.ast as omni_ast

            target_path = Path(target)
            results = []

            if target_path.is_file():
                files = [target_path]
            else:
                files = [f for f in target_path.rglob("*") if f.is_file() and self._is_code_file(f)]

            for file_path in files[:50]:
                try:
                    content = file_path.read_text(errors="ignore")
                    lang = self._detect_language(file_path.suffix)
                    if not lang:
                        continue

                    json_results = omni_ast.py_extract_items(
                        content=content,
                        pattern=pattern,
                        language=lang,
                        captures=None,
                    )

                    parsed = json.loads(json_results) if json_results else []
                    for item in parsed:
                        results.append(
                            f"// File: {file_path}\n"
                            f"L{item.get('line_start', 0)}   {item.get('text', '')}"
                        )

                except Exception as e:
                    logger.debug(f"Error processing {file_path}: {e}")
                    continue

            if results:
                return f"// AST Search Results\n" + "\n".join(results)
            else:
                return f"No matches found for pattern: {pattern}"

        except ImportError:
            return "Error: omni.ast not installed"
        except Exception as e:
            return f"Search error: {e}"

    def _analyze_code(self, target: str, language: str) -> str:
        """Analyze code for patterns and issues using YAML rules."""
        try:
            import omni.ast as omni_ast

            target_path = Path(target)
            if target_path.is_file():
                files = [target_path]
            else:
                files = [f for f in target_path.rglob("*") if f.is_file() and self._is_code_file(f)]

            violations = []

            for file_path in files[:30]:
                try:
                    content = file_path.read_text(errors="ignore")
                    lang = self._detect_language(file_path.suffix)
                    if not lang:
                        continue

                    for rule_name, rule_config in BUILTIN_RULES.items():
                        for pattern in rule_config["patterns"]:
                            json_results = omni_ast.py_extract_items(
                                content=content,
                                pattern=pattern,
                                language=lang,
                                captures=None,
                            )

                            parsed = json.loads(json_results) if json_results else []
                            for item in parsed:
                                violations.append(
                                    f"// {file_path}:{item.get('line_start', 0)}\n"
                                    f"  [{rule_name}] {rule_config['message']}: {item.get('text', '')}"
                                )

                except Exception as e:
                    logger.debug(f"Error analyzing {file_path}: {e}")
                    continue

            if violations:
                return f"// Analysis Results ({len(violations)} issues)\n" + "\n".join(violations)
            else:
                return "No issues found"

        except ImportError:
            return "Error: omni.ast not installed"
        except Exception as e:
            return f"Analysis error: {e}"

    def _apply_rule(self, rule_name: str, target: str, language: str, dry_run: bool) -> str:
        """Apply a registered rule to code."""
        if rule_name in BUILTIN_RULES:
            rule = BUILTIN_RULES[rule_name]
            return (
                f"Rule: {rule_name}\n"
                f"Patterns: {rule['patterns']}\n"
                f"Message: {rule['message']}\n"
                f"Mode: {'DRY RUN' if dry_run else 'APPLY'}"
            )
        else:
            return f"Unknown rule: {rule_name}"

    def register_rule(self, name: str, pattern: str, message: str) -> str:
        """Register a custom analysis rule."""
        BUILTIN_RULES[name] = {
            "patterns": [pattern],
            "message": message,
        }
        return f"Rule '{name}' registered successfully"

    def list_rules(self) -> List[Dict[str, str]]:
        """List all available rules."""
        return [
            {"id": name, "message": config["message"]} for name, config in BUILTIN_RULES.items()
        ]

    def _is_code_file(self, path: Path) -> bool:
        """Check if file is a code file."""
        code_extensions = {".py", ".rs", ".js", ".ts", ".go", ".java", ".c", ".cpp"}
        return path.suffix.lower() in code_extensions

    def _detect_language(self, suffix: str) -> Optional[str]:
        """Detect programming language from file extension."""
        lang_map = {
            ".py": "python",
            ".rs": "rust",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
        }
        return lang_map.get(suffix.lower())

    def extract_skeleton(self, content: str, language: str) -> str:
        """Extract code skeleton (signatures only)."""
        try:
            import omni.ast as omni_ast

            result = omni_ast.py_extract_skeleton(content, language)
            parsed = json.loads(result)
            return parsed.get("skeleton", "")
        except Exception as e:
            return f"Skeleton extraction error: {e}"

    def chunk_code(
        self, content: str, file_path: str, language: str, patterns: List[str]
    ) -> List[Dict[str, Any]]:
        """Chunk code into semantic units."""
        try:
            import omni.ast as omni_ast

            chunks = omni_ast.py_chunk_code(
                content=content,
                file_path=file_path,
                language=language,
                patterns=patterns,
                min_lines=1,
                max_lines=0,
            )
            return [
                {
                    "id": c.id,
                    "type": c.chunk_type,
                    "content": c.content,
                    "line_start": c.line_start,
                    "line_end": c.line_end,
                }
                for c in chunks
            ]
        except Exception as e:
            logger.error(f"Chunking error: {e}")
            return []
