---
name: stress_test_skill
description: Internal skill for testing skill hot-reload functionality
version: 0.0.1
---

# Stress Test Skill

Internal utility skill for testing the skill loading and hot-reload system.

## Tools

### ping

Simple ping/pong test to verify skill was loaded correctly.

```python
from assets.skills.stress_test_skill.tools import ping

result = ping()  # Returns "pong_v0"
```

## Usage

Used by the test suite to verify:

- Skill hot-reload functionality
- Dynamic skill loading/unloading
- Version tracking during development
