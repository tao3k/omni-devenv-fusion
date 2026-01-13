# Lesson: Always use python_test instead of pytest directly

**Category**: workflow
**Date**: 2025-01-13
**Harvested**: Automatically from development session

## Context

User tried running `pytest` directly but the environment wasn't properly activated, causing the test execution to fail.

## Solution

Always route to `testing` skill and specify the `python_test` tool. The testing skill handles environment activation and proper test execution.

## Key Takeaways

- Use `@omni("testing.run_tests", {...})` for test execution
- Don't run `pytest` directly from terminal skill
- The testing skill automatically activates the correct virtual environment

## Related Files

- `agent/skills/testing/tools.py`
- `agent/skills/testing_protocol/tools.py`
