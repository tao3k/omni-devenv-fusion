#!/usr/bin/env python3
"""
scripts/verify_skill_descriptions.py
Verify skill command descriptions meet MCP standards.

This script analyzes all skill scripts and verifies that:
1. Each @skill_command has an explicit description= parameter
2. Description structure follows the standard format
3. First line is a concise action verb summary
4. Args and Returns sections are present when applicable
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

# Add packages to path for imports
_PRJ_ROOT = Path(__file__).parent.parent
_foundation_src = _PRJ_ROOT / "packages/python/foundation/src"
if str(_foundation_src) not in sys.path:
    sys.path.insert(0, str(_foundation_src))

from omni.foundation.config.skills import SKILLS_DIR


STANDARD_TEMPLATE = '''description="""
One-line summary of what this command does.

[Optional] Additional context about when to use this command.

Args:
    param1: Description of param1. Defaults to `X`.

Returns:
    Description of return value.
"""'''


class SkillDescriptionAnalyzer:
    """Analyzes skill scripts for description compliance."""

    def __init__(self, skills_dir: Path | None = None):
        self.skills_dir = skills_dir or SKILLS_DIR()
        self.issues: list[dict[str, Any]] = []
        self.stats = {
            "total_skills": 0,
            "total_commands": 0,
            "commands_with_description": 0,
            "commands_without_description": 0,
            "issues": 0,
        }

    def run(self) -> int:
        """Run the analysis on all skill scripts."""
        print("=" * 60)
        print("Skill Description Verification")
        print("=" * 60)

        skill_files = list(self.skills_dir.glob("*/scripts/*.py"))
        print(f"\nFound {len(skill_files)} skill script files\n")

        for skill_file in sorted(skill_files):
            self._analyze_file(skill_file)

        self._print_summary()
        return 1 if self.issues else 0

    def _analyze_file(self, file_path: Path) -> None:
        """Analyze a single skill script file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except Exception as e:
            print(f"  [ERROR] Could not parse {file_path}: {e}")
            return

        skill_name = file_path.parent.parent.name
        commands: list[dict[str, Any]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                has_skill_command = False
                description: str | None = None
                description_source: str | None = None

                for decorator in node.decorator_list:
                    if self._is_skill_command_decorator(decorator):
                        has_skill_command = True
                        description = self._extract_description(decorator)
                        if description is None:
                            description = self._get_docstring_first_line(node)
                            description_source = "docstring"
                        else:
                            description_source = "explicit_param"

                if has_skill_command:
                    self.stats["total_commands"] += 1
                    commands.append(
                        {
                            "name": node.name,
                            "file": str(file_path.relative_to(self.skills_dir.parent)),
                            "description": description,
                            "source": description_source,
                            "has_explicit_description": description is not None
                            and description_source == "explicit_param",
                        }
                    )

        if not commands:
            return

        self.stats["total_skills"] += 1
        print(f"📁 {skill_name}/")

        for cmd in commands:
            if not cmd["has_explicit_description"]:
                self.stats["commands_without_description"] += 1
                self.issues.append(
                    {
                        "file": cmd["file"],
                        "command": cmd["name"],
                        "issue": "Missing explicit description parameter",
                        "current": cmd["description"] or "(no description)",
                    }
                )
                print(f"  ❌ {cmd['name']}: Missing description")
            else:
                self.stats["commands_with_description"] += 1
                quality_issues = self._check_description_quality(cmd["description"], cmd["name"])
                if quality_issues:
                    self.stats["issues"] += len(quality_issues)
                    for issue in quality_issues:
                        print(f"  ⚠️  {cmd['name']}: {issue}")
                else:
                    print(f"  ✅ {cmd['name']}: OK")

    def _is_skill_command_decorator(self, node: ast.AST) -> bool:
        """Check if node is a @skill_command decorator."""
        if isinstance(node, ast.Name) and node.id == "skill_command":
            return True
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "skill_command":
                return True
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "skill_command":
                    return True
        return False

    def _extract_description(self, decorator: ast.AST) -> str | None:
        """Extract description from decorator keyword arguments."""
        if not isinstance(decorator, ast.Call):
            return None

        for kw in decorator.keywords:
            if kw.arg == "description":
                if isinstance(kw.value, ast.Constant):
                    return kw.value.value
                if isinstance(kw.value, ast.Str):
                    return kw.value.s
        return None

    def _get_docstring_first_line(self, node: ast.FunctionDef) -> str | None:
        """Get the first line of a function's docstring."""
        if node.body and isinstance(node.body[0], ast.Expr):
            if isinstance(node.body[0].value, ast.Constant):
                return node.body[0].value.value
            if isinstance(node.body[0].value, ast.Str):
                return node.body[0].value.s
        return None

    def _check_description_quality(self, description: str, command_name: str) -> list[str]:
        """Check if description meets quality standards."""
        issues: list[str] = []

        if not description:
            return ["Empty description"]

        # Get non-empty lines, preserving order
        lines = [l.strip() for l in description.strip().split("\n") if l.strip()]

        if not lines:
            return ["Description is empty"]

        first_line = lines[0]
        action_verbs = [
            "Create",
            "Get",
            "Search",
            "Update",
            "Delete",
            "Execute",
            "Run",
            "Load",
            "Save",
            "List",
            "Show",
            "Check",
            "Build",
            "Parse",
            "Format",
            "Validate",
            "Generate",
            "Apply",
            "Process",
            "Clear",
            "Index",
            "Ingest",
            "Consult",
            "Bridge",
            "Refine",
            "Summarize",
            "Update",
            "Reload",
            "Unload",
            "Discover",
            "Commit",
            "Amend",
            "Revert",
            "Install",
            "Lists",
            "Retrieves",
            "Returns",
            "Analyzes",
            "Suggest",
            "Suggests",
            "Writes",
            "Reads",
            "Extracts",
            "Parses",
            "Queries",
            "Filters",
            "Saves",
            "Loads",
            "Clears",
            "Indexes",
            "Counts",
            "Applies",
            "Detect",
            "Eject",
            "Outline",
            "Goto",
            "Find",
            "Count",
            "Navigate",
            "Refactor",
            "Analyze",
            "Preview",
            "Replace",
            "Retrieve",
            "Fast",  # For "Fast file location..."
            "Mass",  # For "MASS REFACTORING TOOL"
            "Performs",  # For "Performs structural replace..."
            "Previews",  # For "Previews structural replace..."
            "Copies",  # For "Copies a skill default template..."
        ]

        line_lower = first_line.lower().strip()
        has_verb_start = any(line_lower.startswith(v.lower()) for v in action_verbs)
        has_verb_embedded = any(
            f" {v.lower()} " in line_lower or f" {v.lower()}." in line_lower
            for v in action_verbs
            if len(v) > 3
        )

        if not has_verb_start and not has_verb_embedded:
            issues.append("First line should contain an action verb (e.g., 'Create', 'Replace')")

        if len(lines) > 2:
            has_args = any("Args:" in line for line in lines)
            has_returns = any("Returns:" in line for line in lines)

            if not has_args:
                issues.append("Multi-line description should include Args: section")
            if not has_returns:
                issues.append("Multi-line description should include Returns: section")

        return issues

    def _print_summary(self) -> None:
        """Print the final summary."""
        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Total skill scripts analyzed: {self.stats['total_skills']}")
        print(f"Total commands found: {self.stats['total_commands']}")
        print(f"Commands with explicit description: {self.stats['commands_with_description']}")
        print(
            f"Commands without explicit description: {self.stats['commands_without_description']}"
        )
        print(f"Quality issues: {self.stats['issues']}")

        if self.issues:
            print(f"\n❌ {len(self.issues)} commands need attention:")
            for issue in self.issues[:20]:
                print(f"  - {issue['file']}:{issue['command']}")
                print(f"    {issue['issue']}")
            if len(self.issues) > 20:
                print(f"  ... and {len(self.issues) - 20} more")
        else:
            print("\n✅ All commands have proper descriptions!")

        print("\n" + "=" * 60)
        print("Standard Template:")
        print("=" * 60)
        print(STANDARD_TEMPLATE)


def main() -> int:
    """Main entry point."""
    skills_dir_arg = sys.argv[1] if len(sys.argv) > 1 else None
    skills_dir = Path(skills_dir_arg) if skills_dir_arg else SKILLS_DIR()

    if not skills_dir.exists():
        print(f"Error: Skills directory not found: {skills_dir}")
        return 1

    analyzer = SkillDescriptionAnalyzer(skills_dir)
    return analyzer.run()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
