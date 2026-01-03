# Skill: Testing & QA

## Overview

This skill allows you to verify code correctness using `pytest`. Always run tests after modifying code to ensure no regressions.

## Capabilities

- **Run Tests**: `run_tests` (Run specific files or directories)
- **Coverage**: `run_coverage` (Check test coverage) [Optional]
- **List Tests**: `list_tests` (Discover available tests)

## Workflow Rules

1.  **Red-Green-Refactor**: If writing new features, ensure tests exist.
2.  **Targeted Testing**: Do not run the entire test suite (`.`) if you only changed one file. Run the relevant test file (e.g., `tests/test_my_module.py`) to save time.
3.  **Read the Output**: If tests fail, read the `FAILURES` section carefully. It contains the exact line number and assertion error.
4.  **No Flaky Tests**: If a test fails randomly, mark it or fix it. Do not ignore it.
