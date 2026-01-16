---
name: "testing"
version: "1.0.0"
description: "Run unit tests and analyze test results using Pytest."
routing_keywords:
  [
    "test",
    "pytest",
    "unit test",
    "integration test",
    "test result",
    "coverage",
    "fail",
    "pass",
    "assert",
    "spec",
    "validate",
  ]
authors: ["omni-dev-fusion"]
intents:
  - "Run tests"
  - "Add unit tests"
  - "Check test coverage"
  - "Fix failing tests"
---

You have loaded the **Testing Skill**.

- You are responsible for software quality assurance.
- **CRITICAL**: Never commit code that breaks existing tests.
- **STRATEGY**: When debugging a failure, run ONLY the failing test case to isolate the issue.
- **INTERPRETATION**: Analyze the traceback deeply. Don't just say "it failed", explain WHY.
