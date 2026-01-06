# Scripts Directory

This directory contains utility scripts for the Omni Agentic OS project.

## Stress Tests

### stress_trinity.py

Phase 25.4: The "Iron Trinity" Stress Test.

Validates the Trinity Architecture (Hot-Reload + Repomix + State) under extreme stress conditions.

#### Purpose

- Verify thread-safety and race-condition handling
- Measure performance under concurrent load
- Validate production readiness

#### Usage

```bash
python scripts/stress_trinity.py
```

#### What It Tests

1. **Chaos Monkey**: Randomly modifies skill `tools.py` every 50-200ms
2. **Spammer**: Fires 1-5 concurrent requests every 10ms
3. **Context Loader**: Calls help command 10 times to test Repomix performance

#### Expected Output

```
🛡️  Omni Trinity Architecture Stress Test  🛡️

This test verifies stability under:
  1. Rapid file modifications (Chaos Monkey)
  2. High concurrency requests (Spammer)
  3. Context generation load (Repomix)

...

============================================================
📊  TEST REPORT  📊
============================================================
Duration:           5.08s
Skill Modifications: 31
Skill Invocations:   966
Failed Requests:     0
  - Race Hits:       0 (expected)
  - Real Errors:     0
Avg Context Time:    0.109s
Throughput:          190.31 requests/sec

============================================================
✅  PASSED: Iron Trinity is SOLID. No crashes under fire.
```

#### Interpretation

| Result    | Meaning                                         |
| --------- | ----------------------------------------------- |
| ✅ PASSED | Architecture is production-ready                |
| ⚠️ ERRORS | Check logs for race conditions or module errors |

#### CI Integration

Add to pre-commit or CI pipeline:

```bash
python scripts/stress_trinity.py
if [ $? -ne 0 ]; then
    echo "Stress test failed!"
    exit 1
fi
```

## Adding New Scripts

When adding new scripts:

1. Use Python and follow project coding standards
2. Add docstrings explaining purpose and usage
3. Make scripts executable (`chmod +x`)
4. Document in this file if significant
