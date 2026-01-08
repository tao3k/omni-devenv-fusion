#!/usr/bin/env python3
"""
scripts/migrate_skills_to_skill_md.py
Phase 33: One-time Migration Script - Convert manifest.json + prompts.md to SKILL.md

This is a ONE-TIME migration script. After running this, all skills will use
SKILL.md format exclusively. The old manifest.json and prompts.md files will
be removed after successful migration.

Usage:
    python scripts/migrate_skills_to_skill_md.py [--dry-run] [--verbose]
    python scripts/migrate_skills_to_skill_md.py --skill git  # Migrate specific skill
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


# =============================================================================
# Migration Logic
# =============================================================================


def migrate_skill(skill_dir: Path, *, dry_run: bool = False, verbose: bool = False) -> bool:
    """
    Migrate a single skill from manifest.json + prompts.md to SKILL.md.

    This migration is IRREVERSIBLE. After migration:
    - SKILL.md will be created
    - manifest.json will be removed
    - prompts.md will be removed (content merged into SKILL.md)

    Args:
        skill_dir: Path to skill directory
        dry_run: If True, only print what would be done
        verbose: If True, print detailed output

    Returns:
        True if migration was successful
    """
    manifest_file = skill_dir / "manifest.json"
    prompts_file = skill_dir / "prompts.md"
    skill_md_file = skill_dir / "SKILL.md"

    # Check if already migrated
    if skill_md_file.exists():
        if verbose:
            print(f"  SKIP: {skill_dir.name} - already has SKILL.md")
        return True

    # Check if manifest exists
    if not manifest_file.exists():
        if verbose:
            print(f"  SKIP: {skill_dir.name} - no manifest.json")
        return False

    # Read manifest
    try:
        manifest = json.loads(manifest_file.read_text())
    except json.JSONDecodeError as e:
        print(f"  ERROR: {skill_dir.name} - invalid JSON: {e}")
        return False

    # Read prompts (optional)
    prompts = ""
    if prompts_file.exists():
        prompts = prompts_file.read_text().strip()

    # Build frontmatter from manifest
    frontmatter_lines = ["---"]
    frontmatter_lines.append(f'name: "{manifest["name"]}"')
    frontmatter_lines.append(f'version: "{manifest["version"]}"')

    desc = manifest.get("description", "").replace('"', '\\"')
    if desc:
        frontmatter_lines.append(f'description: "{desc}"')

    if manifest.get("execution_mode"):
        frontmatter_lines.append(f"execution_mode: {manifest['execution_mode']}")
    if manifest.get("routing_keywords"):
        frontmatter_lines.append(f"routing_keywords: {manifest['routing_keywords']}")
    if manifest.get("intents"):
        frontmatter_lines.append(f"intents: {manifest['intents']}")
    if manifest.get("author"):
        frontmatter_lines.append(f'authors: ["{manifest["author"]}"]')
    elif manifest.get("authors"):
        frontmatter_lines.append(f"authors: {manifest['authors']}")
    if manifest.get("dependencies"):
        frontmatter_lines.append(f"dependencies: {manifest['dependencies']}")
    if manifest.get("permissions"):
        frontmatter_lines.append(f"permissions: {manifest['permissions']}")

    frontmatter_lines.append("---")
    frontmatter_content = "\n".join(frontmatter_lines)

    # Build SKILL.md content
    content = prompts.strip()
    if content:
        skill_md_content = f"{frontmatter_content}\n\n{content}"
    else:
        skill_md_content = frontmatter_content

    if dry_run:
        print(f"  DRY-RUN: {skill_dir.name}")
        print(f"    Would create: {skill_md_file}")
        print(f"    Would remove: {manifest_file.name}, {prompts_file.name}")
    else:
        # Write SKILL.md
        skill_md_file.write_text(skill_md_content)

        # Remove old files
        manifest_file.unlink()
        if prompts_file.exists():
            prompts_file.unlink()

        if verbose:
            print(f"  MIGRATED: {skill_dir.name}")
            print(f"    Created: {skill_md_file.name}")
            print(f"    Removed: {manifest_file.name}, {prompts_file.name}")

    return True


def migrate_all_skills(
    skills_dir: Path, *, dry_run: bool = False, verbose: bool = False
) -> dict[str, bool]:
    """
    Migrate all skills in the skills directory.

    Args:
        skills_dir: Path to assets/skills
        dry_run: If True, only print what would be done
        verbose: If True, print detailed output

    Returns:
        Dictionary mapping skill name to migration success
    """
    results: dict[str, bool] = {}

    if verbose or dry_run:
        print(f"\n{'DRY-RUN ' if dry_run else ''}ONE-TIME MIGRATION")
        print("=" * 60)
        print("This will convert all skills to SKILL.md format.")
        print("Old manifest.json and prompts.md files will be REMOVED.\n")

    entries = sorted(skills_dir.iterdir())
    total = sum(1 for e in entries if e.is_dir() and not e.name.startswith("_"))
    current = 0

    for entry in entries:
        if not entry.is_dir() or entry.name.startswith("_"):
            continue

        current += 1
        skill_name = entry.name

        if verbose or dry_run:
            print(f"[{current}/{total}] ", end="")

        success = migrate_skill(entry, dry_run=dry_run, verbose=verbose)
        results[skill_name] = success

    if verbose or dry_run:
        print("\n" + "=" * 60)
        print(f"Total: {len(results)} skills")
        print(f" Migrated: {sum(1 for v in results.values() if v)}")
        print(f" Skipped:  {sum(1 for v in results.values() if not v)}")

    return results


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ONE-TIME Migration: Convert manifest.json + prompts.md to SKILL.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
WARNING: This is a ONE-TIME migration. After running:
- All skills will use SKILL.md format
- manifest.json files will be DELETED
- prompts.md files will be DELETED (content merged into SKILL.md)

Examples:
    # Dry run to see what would be migrated
    python migrate_skills_to_skill_md.py --dry-run

    # Execute migration (this will delete old files)
    python migrate_skills_to_skill_md.py

    # Migrate specific skill
    python migrate_skills_to_skill_md.py --skill git

    # Verbose output
    python migrate_skills_to_skill_md.py --verbose
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--skill", "-s", type=str, help="Migrate specific skill only")
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=Path("assets/skills"),
        help="Path to skills directory (default: assets/skills)",
    )

    args = parser.parse_args()

    # Use SKILLS_DIR from common.skills_path
    from common.skills_path import SKILLS_DIR

    skills_dir = SKILLS_DIR()

    if not skills_dir.exists():
        print(f"ERROR: Skills directory not found: {skills_dir}")
        return 1

    if args.skill:
        # Migrate specific skill
        skill_dir = skills_dir / args.skill
        if not skill_dir.exists():
            print(f"ERROR: Skill not found: {skill_dir}")
            return 1
        migrate_skill(skill_dir, dry_run=args.dry_run, verbose=args.verbose)
    else:
        # Migrate all skills
        migrate_all_skills(skills_dir, dry_run=args.dry_run, verbose=args.verbose)

    return 0


if __name__ == "__main__":
    exit(main())
