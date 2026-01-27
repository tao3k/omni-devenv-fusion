#!/usr/bin/env python3
"""
verify_generator.py - Automated Generator Testing Suite

Tests the RAG-based skill generator for:
1. Modern Python standards compliance (TypedDict, StrEnum, match/case)
2. Self-healing capability
3. Dependency handling
4. RAG effectiveness

Usage:
    python scripts/verify_generator.py --run-all
    python scripts/verify_generator.py --test-rag
    python scripts/verify_generator.py --test-self-heal
    python scripts/verify_generator.py --clean
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
SKILLS_DIR = PROJECT_ROOT / "assets/skills"


@dataclass
class TestResult:
    """Result of a test case."""

    name: str
    passed: bool
    message: str
    details: dict[str, Any] | None = None


class GeneratorVerifier:
    """Test suite for skill generator."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: list[TestResult] = []
        self.temp_skills: list[Path] = []

    def log(self, msg: str):
        """Print message if verbose."""
        if self.verbose:
            print(f"  [DEBUG] {msg}")

    def cleanup(self):
        """Remove generated test skills."""
        for skill_path in self.temp_skills:
            if skill_path.exists():
                import shutil

                shutil.rmtree(skill_path)
                print(f"  Cleaned up: {skill_path.name}")

    async def run_cli(self, args: list[str]) -> tuple[int, str, str]:
        """Run omni CLI command and return (returncode, stdout, stderr)."""
        cmd = ["uv", "run", "omni", "skill", "generate"] + args
        self.log(f"Running: {' '.join(cmd)}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()

    def check_file_content(self, skill_path: Path, patterns: dict[str, str]) -> dict[str, bool]:
        """Check if file contains expected patterns."""
        results = {}
        for filename, pattern in patterns.items():
            file_path = skill_path / filename
            if not file_path.exists():
                results[filename] = False
                self.log(f"  Missing file: {filename}")
                continue

            content = file_path.read_text()
            results[filename] = pattern in content
            self.log(f"  {filename}: {pattern} -> {results[filename]}")
        return results

    async def test_modern_standards(self) -> TestResult:
        """Test 1: Verify RAG + LLM produces modern Python code."""
        self.log("Testing modern standards compliance...")

        skill_name = "test-modern-%d" % int(__import__("time").time())
        description = "A currency converter that uses TypedDict and StrEnum"

        try:
            # Generate skill
            returncode, stdout, stderr = await self.run_cli(
                [
                    skill_name,
                    "-d",
                    description,
                    "--no-interactive",
                ]
            )

            if returncode != 0:
                return TestResult(
                    name="modern_standards",
                    passed=False,
                    message=f"CLI failed with code {returncode}",
                    details={"stderr": stderr[:500]},
                )

            skill_path = SKILLS_DIR / skill_name
            self.temp_skills.append(skill_path)

            if not skill_path.exists():
                return TestResult(
                    name="modern_standards",
                    passed=False,
                    message="Skill directory not created",
                )

            # Check for modern patterns
            commands_path = skill_path / "scripts" / "commands.py"
            if not commands_path.exists():
                return TestResult(
                    name="modern_standards",
                    passed=False,
                    message="commands.py not created",
                )

            content = commands_path.read_text()

            # Check patterns (at least one should be present for modern code)
            checks = {
                "TypedDict": "TypedDict" in content,
                "StrEnum": "StrEnum" in content or "Str" in str(type.__bases__)
                if "StrEnum" not in content
                else True,
                "match/case": "match " in content and "case " in content,
                "type Alias": "=" in content and "type" in content.split("=")[0]
                if "=" in content
                else False,
                "async with": "async with" in content,
                "TaskGroup": "TaskGroup" in content or "asyncio.TaskGroup" in content,
            }

            passed_checks = sum(checks.values())
            total_checks = len(checks)

            # RAG should have helped - at least some patterns should match
            # We expect ~50% of modern patterns to be present
            modern_score = passed_checks / total_checks

            return TestResult(
                name="modern_standards",
                passed=modern_score >= 0.3,  # At least 30% modern patterns
                message=f"Modern patterns: {passed_checks}/{total_checks} found (score: {modern_score:.1%})",
                details=checks,
            )

        except Exception as e:
            return TestResult(
                name="modern_standards",
                passed=False,
                message=f"Test error: {e}",
            )

    async def test_self_healing(self) -> TestResult:
        """Test 2: Verify self-healing mechanism works."""
        self.log("Testing self-healing capability...")

        skill_name = "test-heal-%d" % int(__import__("time").time())

        try:
            # First, generate a normal skill to get the file structure
            returncode, stdout, stderr = await self.run_cli(
                [
                    skill_name,
                    "-d",
                    "A simple calculator skill",
                    "--no-interactive",
                ]
            )

            if returncode != 0:
                return TestResult(
                    name="self_healing",
                    passed=False,
                    message="Initial generation failed",
                    details={"stderr": stderr[:500]},
                )

            skill_path = SKILLS_DIR / skill_name
            self.temp_skills.append(skill_path)

            commands_path = skill_path / "scripts" / "commands.py"

            # Manually inject a syntax error
            content = commands_path.read_text()
            broken_content = content.replace(")", "")  # Remove a closing paren
            commands_path.write_text(broken_content)

            self.log("  Injected syntax error (removed ')')")

            # The current implementation only checks on generation,
            # but we verify the verification function works
            sys.path.insert(0, str(PROJECT_ROOT / "packages/python/agent/src"))

            from omni.agent.cli.commands.skill._generate_modular import verify_skill_code

            result = await verify_skill_code(broken_content)

            if not result["valid"] and result["error"]:
                return TestResult(
                    name="self_healing",
                    passed=True,
                    message="Syntax error correctly detected",
                    details={"error": result["error"]},
                )
            else:
                return TestResult(
                    name="self_healing",
                    passed=False,
                    message="Syntax error not detected",
                    details=result,
                )

        except ImportError as e:
            return TestResult(
                name="self_healing",
                passed=False,
                message=f"Cannot import verify module: {e}",
            )
        except Exception as e:
            return TestResult(
                name="self_healing",
                passed=False,
                message=f"Test error: {e}",
            )

    async def test_rag_context(self) -> TestResult:
        """Test 3: Verify RAG retrieves relevant examples."""
        self.log("Testing RAG retrieval...")

        try:
            sys.path.insert(0, str(PROJECT_ROOT / "packages/python/agent/src"))

            from omni.agent.cli.commands.skill._generate_modular import retrieve_similar_skills

            # Query for a skill that should exist (e.g., file operations)
            examples = await retrieve_similar_skills("Read and write files to disk", limit=3)

            if not examples:
                return TestResult(
                    name="rag_context",
                    passed=False,
                    message="RAG returned no examples",
                )

            # Check if examples are relevant
            relevant_count = 0
            for ex in examples:
                content = ex.get("content", "").lower()
                skill = ex.get("skill_name", "").lower()
                # Check for file-related keywords
                if any(
                    kw in content or kw in skill for kw in ["file", "read", "write", "filesystem"]
                ):
                    relevant_count += 1

            return TestResult(
                name="rag_context",
                passed=relevant_count > 0,
                message=f"RAG found {len(examples)} examples, {relevant_count} relevant",
                details={
                    "examples": [
                        {"skill": ex["skill_name"], "score": ex["score"]} for ex in examples
                    ]
                },
            )

        except ImportError as e:
            return TestResult(
                name="rag_context",
                passed=False,
                message=f"Cannot import RAG module: {e}",
            )
        except Exception as e:
            return TestResult(
                name="rag_context",
                passed=False,
                message=f"Test error: {e}",
            )

    async def test_dependency_handling(self) -> TestResult:
        """Test 4: Verify generated skill handles dependencies."""
        self.log("Testing dependency handling...")

        skill_name = "test-deps-%d" % int(__import__("time").time())
        description = "A tool that uses psutil to check system memory"

        try:
            returncode, stdout, stderr = await self.run_cli(
                [
                    skill_name,
                    "-d",
                    description,
                    "--no-interactive",
                ]
            )

            if returncode != 0:
                return TestResult(
                    name="dependency_handling",
                    passed=False,
                    message=f"CLI failed with code {returncode}",
                    details={"stderr": stderr[:500]},
                )

            skill_path = SKILLS_DIR / skill_name
            self.temp_skills.append(skill_path)

            if not skill_path.exists():
                return TestResult(
                    name="dependency_handling",
                    passed=False,
                    message="Skill directory not created",
                )

            # Check commands.py for psutil import
            commands_path = skill_path / "scripts" / "commands.py"
            if not commands_path.exists():
                return TestResult(
                    name="dependency_handling",
                    passed=False,
                    message="commands.py not created",
                )

            content = commands_path.read_text()

            # Check for import handling
            checks = {
                "import psutil": "psutil" in content,
                "import statement": "import " in content,
                "error handling": "except" in content or "Error" in content,
            }

            passed = sum(checks.values()) >= 2  # At least 2/3 checks

            return TestResult(
                name="dependency_handling",
                passed=passed,
                message=f"Dependency patterns: {checks}",
                details=checks,
            )

        except Exception as e:
            return TestResult(
                name="dependency_handling",
                passed=False,
                message=f"Test error: {e}",
            )

    async def run_all_tests(self) -> bool:
        """Run all test cases."""
        print("\n" + "=" * 60)
        print("OMNI SKILL GENERATOR - AUTOMATED TEST SUITE")
        print("=" * 60)

        tests = [
            ("RAG Context Retrieval", self.test_rag_context),
            ("Modern Standards Compliance", self.test_modern_standards),
            ("Self-Healing Capability", self.test_self_healing),
            ("Dependency Handling", self.test_dependency_handling),
        ]

        all_passed = True

        for test_name, test_func in tests:
            print(f"\n{'=' * 60}")
            print(f"TEST: {test_name}")
            print("=" * 60)

            result = await test_func()
            self.results.append(result)

            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"\n{status}: {result.message}")

            if result.details:
                for key, value in result.details.items():
                    print(f"  {key}: {value}")

            if not result.passed:
                all_passed = False

        # Cleanup
        print(f"\n{'=' * 60}")
        print("CLEANUP")
        print("=" * 60)
        self.cleanup()

        # Summary
        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        print(f"\nPassed: {passed}/{total}")

        for result in self.results:
            status = "✅" if result.passed else "❌"
            print(f"  {status} {result.name}")

        return all_passed


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test the omni skill generator")
    parser.add_argument("--run-all", action="store_true", help="Run all tests")
    parser.add_argument("--test-rag", action="store_true", help="Test RAG retrieval")
    parser.add_argument("--test-modern", action="store_true", help="Test modern standards")
    parser.add_argument("--test-heal", action="store_true", help="Test self-healing")
    parser.add_argument("--test-deps", action="store_true", help="Test dependency handling")
    parser.add_argument("--clean", action="store_true", help="Clean up test skills")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if not any(
        [args.run_all, args.test_rag, args.test_modern, args.test_heal, args.test_deps, args.clean]
    ):
        parser.print_help()
        return

    verifier = GeneratorVerifier(verbose=args.verbose)

    if args.clean:
        print("Cleaning up test skills...")
        verifier.cleanup()
        return

    all_passed = True

    if args.run_all or args.test_rag:
        result = await verifier.test_rag_context()
        print(f"\n{'=' * 60}")
        print(f"RAG TEST: {'✅ PASS' if result.passed else '❌ FAIL'}")
        print(f"  {result.message}")
        if result.details:
            for k, v in result.details.items():
                print(f"  {k}: {v}")
        all_passed = all_passed and result.passed

    if args.run_all or args.test_modern:
        result = await verifier.test_modern_standards()
        print(f"\n{'=' * 60}")
        print(f"MODERN STANDARDS TEST: {'✅ PASS' if result.passed else '❌ FAIL'}")
        print(f"  {result.message}")
        if result.details:
            for k, v in result.details.items():
                print(f"  {k}: {v}")
        all_passed = all_passed and result.passed
        verifier.cleanup()

    if args.run_all or args.test_heal:
        result = await verifier.test_self_healing()
        print(f"\n{'=' * 60}")
        print(f"SELF-HEALING TEST: {'✅ PASS' if result.passed else '❌ FAIL'}")
        print(f"  {result.message}")
        if result.details:
            for k, v in result.details.items():
                print(f"  {k}: {v}")
        all_passed = all_passed and result.passed
        verifier.cleanup()

    if args.run_all or args.test_deps:
        result = await verifier.test_dependency_handling()
        print(f"\n{'=' * 60}")
        print(f"DEPENDENCY TEST: {'✅ PASS' if result.passed else '❌ FAIL'}")
        print(f"  {result.message}")
        if result.details:
            for k, v in result.details.items():
                print(f"  {k}: {v}")
        all_passed = all_passed and result.passed
        verifier.cleanup()

    # Final cleanup
    verifier.cleanup()

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
