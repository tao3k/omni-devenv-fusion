# agent/cli/commands/skill/manage.py
"""
Management commands for skill CLI.

Contains: run, test, check commands.
(install/update deprecated in thin client model)
"""

from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from .base import SKILLS_DIR, cli_log_handler, err_console, run_skills, skill_app


@skill_app.command("run")
def skill_run(
    command: str = typer.Argument(..., help="Skill command in format 'skill.command'"),
    args_json: str | None = typer.Argument(None, help="JSON arguments for the command"),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output raw JSON instead of markdown content"
    ),
):
    """Execute a skill command."""
    commands = [command]
    if args_json:
        commands.append(args_json)
    run_skills(commands, json_output=json_output, log_handler=cli_log_handler)


# Deprecated commands - remote install/update not available in thin client model
@skill_app.command("install")
def skill_install(
    url: str = typer.Argument(..., help="Git repository URL"),
    name: str | None = typer.Argument(None, help="Skill name (derived from URL if not provided)"),
    version: str = typer.Option("main", "--version", "-v", help="Git ref (default: main)"),
):
    """Install a skill from a remote repository. [DEPRECATED]"""
    err_console.print(
        Panel(
            "Remote skill installation is not available in thin client mode.\n"
            "Skills are loaded from assets/skills/ automatically.",
            title="⚠️ Deprecated",
            style="yellow",
        )
    )


@skill_app.command("update")
def skill_update(
    name: str = typer.Argument(..., help="Skill name"),
    version: str = typer.Option("main", "--version", "-v", help="Git ref"),
):
    """Update an installed skill. [DEPRECATED]"""
    err_console.print(
        Panel(
            "Remote skill updates are not available in thin client mode.\n"
            "Skills are loaded from assets/skills/ automatically.",
            title="⚠️ Deprecated",
            style="yellow",
        )
    )


@skill_app.command("test")
def skill_test(
    skill_name: str | None = typer.Argument(None, help="Skill name to test (default: all skills)"),
    all_skills: bool = typer.Option(False, "--all", help="Test all skills with tests/ directory"),
):
    """Test skills using the testing framework."""
    from omni.foundation.config.skills import SKILLS_DIR
    import subprocess
    import json
    import tempfile

    skills_dir = SKILLS_DIR()

    if not skill_name and not all_skills:
        err_console.print(
            Panel(
                "Specify a skill name or use --all to test all skills",
                title="ℹ️ Usage",
                style="blue",
            )
        )
        return

    if all_skills:
        # Collect all test directories
        test_dirs = []
        for skill_path in sorted(skills_dir.iterdir()):
            if skill_path.is_dir() and not skill_path.name.startswith("_"):
                tests_dir = skill_path / "tests"
                if tests_dir.exists() and list(tests_dir.glob("test_*.py")):
                    test_dirs.append(str(tests_dir))

        if not test_dirs:
            err_console.print(Panel("No skill tests found", title="ℹ️ Info", style="blue"))
            return

        # Run all tests together with JSON output
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json_output_path = f.name

        try:
            # Run pytest with JSON report - output flows through to terminal
            err_console.print(
                f"[bold]Running tests in {len(test_dirs)} skill test directories...[/]"
            )
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-v",
                    "--tb=short",
                    "--json-report",
                    f"--json-report-file={json_output_path}",
                    "-o",
                    "addopts=-p no:randomly",  # Disable random order for consistent output
                ]
                + test_dirs,
                cwd=str(skills_dir),
                stdout=None,  # Inherit parent stdout (show pytest output)
                stderr=None,  # Inherit parent stderr
            )

            # Parse JSON report and display results
            try:
                with open(json_output_path) as f:
                    report = json.load(f)

                # Build results by skill
                skill_results = {}
                for test in report.get("tests", []):
                    nodeid = test.get("nodeid", "")
                    outcome = test.get("outcome", "unknown")

                    # Extract skill name from path (handle both relative and absolute paths)
                    skill_name = None
                    for skill_path in sorted(skills_dir.iterdir()):
                        if skill_path.is_dir() and not skill_path.name.startswith("_"):
                            tests_dir = skill_path / "tests"
                            tests_dir_str = str(tests_dir)
                            # Check both relative and absolute paths
                            if (
                                tests_dir_str in nodeid
                                or nodeid.startswith(str(skill_path.name) + "/")
                                or "assets/skills/" + skill_path.name + "/tests" in nodeid
                            ):
                                skill_name = skill_path.name
                                break

                    # Skip if skill name not found
                    if skill_name is None:
                        continue

                    # Initialize skill results dict
                    if skill_name not in skill_results:
                        skill_results[skill_name] = {
                            "passed": 0,
                            "failed": 0,
                            "skipped": 0,
                            "errors": [],
                        }

                    # Count by outcome
                    if outcome == "passed":
                        skill_results[skill_name]["passed"] += 1
                    elif outcome == "failed":
                        skill_results[skill_name]["failed"] += 1
                        shortrepr = test.get("shortrepr", "")
                        skill_results[skill_name]["errors"].append(shortrepr)
                    elif outcome == "skipped":
                        skill_results[skill_name]["skipped"] += 1

                # Display results table
                from rich.table import Table

                table = Table(title="🧪 Skill Test Results", show_header=True)
                table.add_column("Skill", style="bold")
                table.add_column("Passed", justify="right")
                table.add_column("Failed", justify="right")
                table.add_column("Skipped", justify="right")
                table.add_column("Status")

                total_passed = total_failed = total_skipped = 0
                for skill, stats in sorted(skill_results.items()):
                    total_passed += stats["passed"]
                    total_failed += stats["failed"]
                    total_skipped += stats["skipped"]

                    status = "✅ PASS" if stats["failed"] == 0 else "❌ FAIL"
                    style = "green" if stats["failed"] == 0 else "red"

                    if stats["failed"] > 0:
                        errors = ", ".join(stats["errors"][:2])
                        if len(stats["errors"]) > 2:
                            errors += f"... +{len(stats['errors']) - 2} more"
                        details = f"[{style}]{status}[/] ({errors})"
                    else:
                        details = f"[{style}]{status}[/]"

                    table.add_row(
                        skill,
                        str(stats["passed"]),
                        str(stats["failed"]),
                        str(stats["skipped"]),
                        details,
                    )

                err_console.print(table)

                # Summary
                total = total_passed + total_failed + total_skipped
                summary_style = "green" if total_failed == 0 else "red"
                err_console.print(
                    Panel(
                        f"Total: {total} | Passed: {total_passed} | Failed: {total_failed} | Skipped: {total_skipped}",
                        title=f"📊 Summary",
                        style=summary_style,
                    )
                )

            except (json.JSONDecodeError, FileNotFoundError) as e:
                err_console.print(
                    Panel(f"Failed to parse test results: {e}", title="❌ Error", style="red")
                )
                # Fallback to raw output
                if result.stdout:
                    err_console.print(result.stdout)
                if result.stderr:
                    err_console.print(result.stderr)

        finally:
            import os

            if os.path.exists(json_output_path):
                os.unlink(json_output_path)

        raise typer.Exit(0 if result.returncode == 0 else 1)

    elif skill_name:
        skill_path = skills_dir / skill_name
        tests_dir = skill_path / "tests"
        if not skill_path.exists():
            err_console.print(
                Panel(f"Skill '{skill_name}' not found", title="❌ Error", style="red")
            )
            raise typer.Exit(1)
        if not tests_dir.exists():
            err_console.print(
                Panel(f"No tests directory for '{skill_name}'", title="❌ Error", style="red")
            )
            raise typer.Exit(1)
        # Run tests for specific skill - output flows through to terminal
        err_console.print(f"[bold]Running tests for '{skill_name}'...[/]")
        result = subprocess.run(
            ["uv", "run", "pytest", str(tests_dir), "-v", "--tb=short"],
            cwd=str(skills_dir),
            stdout=None,  # Inherit parent stdout
            stderr=None,  # Inherit parent stderr
        )
        raise typer.Exit(result.returncode)


@skill_app.command("check")
def skill_check(
    skill_name: str | None = typer.Argument(None, help="Skill name to check (default: all skills)"),
    show_example: bool = typer.Option(
        False, "--example", "-e", help="Show _template skill example"
    ),
):
    """Validate skill structure or show template example."""
    from pathlib import Path

    from omni.foundation.config.skills import SKILLS_DIR

    # Handle --example option
    if show_example:
        template_path = SKILLS_DIR() / "_template" / "SKILL.md"
        if template_path.exists():
            content = template_path.read_text()
            err_console.print(
                Panel(
                    content,
                    title="_template/SKILL.md",
                    subtitle=f"Path: {template_path}",
                    expand=False,
                )
            )
        else:
            err_console.print(
                Panel(
                    f"Template not found at: {template_path}",
                    title="❌ Error",
                    style="red",
                )
            )
        return

    skills_dir = SKILLS_DIR()

    def check_skill(name: str) -> tuple[bool, list[str], list[str]]:
        """Check a single skill and return (success, found, missing)."""
        skill_dir = skills_dir / name

        if not skill_dir.exists():
            return False, [], [f"Skill directory not found: {name}"]

        required_files = ["SKILL.md"]
        optional_files = ["scripts/", "tests/", "prompts.md", "README.md"]

        missing = []
        found = []

        for f in required_files:
            path = skill_dir / f
            if path.exists():
                found.append(f)
            else:
                missing.append(f)

        for f in optional_files:
            path = skill_dir / f
            if path.exists():
                found.append(f)

        return len(missing) == 0, found, missing

    if skill_name:
        success, found, missing = check_skill(skill_name)
        if success:
            err_console.print(
                Panel(
                    f"✅ Skill '{skill_name}' is valid\nFound: {', '.join(found)}",
                    title="✅ Valid",
                    style="green",
                )
            )
        else:
            err_console.print(
                Panel(
                    f"❌ Missing: {', '.join(missing)}\nFound: {', '.join(found)}",
                    title="❌ Invalid",
                    style="red",
                )
            )
    else:
        # Check all skills
        table = Table(title="🔍 Skill Structure Check", show_header=True)
        table.add_column("Skill", style="bold")
        table.add_column("Status")
        table.add_column("Details")

        for skill_path in sorted(skills_dir.iterdir()):
            if skill_path.is_dir() and not skill_path.name.startswith("_"):
                success, found, missing = check_skill(skill_path.name)
                status = "✅ Valid" if success else "❌ Invalid"
                style = "green" if success else "red"
                details = (
                    f"Found: {len(found)}" if success else f"Missing: {', '.join(missing[:2])}"
                )
                table.add_row(skill_path.name, f"[{style}]{status}[/]", details)

        err_console.print(table)
