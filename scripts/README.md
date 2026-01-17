# Scripts Directory

This directory contains utility scripts for the Omni Agentic OS project.

## Stress Tests

### stress_trinity.py

**Phase 25.4 → Phase 67**: The "Iron Trinity" Stress Test.

Validates the Trinity Architecture (JIT + Hot-Reload + LRU) under extreme stress conditions.

#### Phase 67 Updates

- **JIT Loading**: Skills load on first use (not at startup)
- **LRU Memory Management**: Max 15 loaded skills, pinned core skills
- **Simplified Hot Reload**: No syntax validation, fail-fast philosophy
- **Scripts Pattern**: Uses `scripts/*.py` with `@skill_command` decorator

#### Purpose

- Verify thread-safety and race-condition handling
- Measure JIT + LRU performance under concurrent load
- Validate simplified hot reload stability
- Validate production readiness

#### Usage

```bash
python scripts/stress_trinity.py
```

#### What It Tests

1. **Chaos Monkey**: Randomly modifies `scripts/ping.py` every 50-200ms (tests hot reload)
2. **Spammer**: Fires 1-5 concurrent requests every 10ms (tests JIT + LRU)
3. **Context Loader**: Calls help command 10 times (tests context generation)

#### Phase 67 Expected Output

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
Duration:           5.02s
Skill Modifications: 38
Skill Invocations:   1376
Failed Requests:     0
  - Race Hits:       0 (expected)
  - Real Errors:     0
Avg Context Time:    0.000s
Throughput:          274.08 requests/sec

============================================================
✅  PASSED: Iron Trinity is SOLID. No crashes under fire.

Performance Summary:
  - Hot-reload: Working (file modified 38 times)
  - JIT Loading: Working (auto-load on first use)
  - LRU Memory: Working (adaptive unloading)
  - Throughput: 274.08 req/s
```

#### Interpretation

| Result    | Meaning                                         |
| --------- | ----------------------------------------------- |
| ✅ PASSED | Phase 67 architecture is production-ready       |
| ⚠️ ERRORS | Check logs for race conditions or module errors |

#### Key Metrics

| Metric            | Phase 25.4 | Phase 67  | Meaning        |
| ----------------- | ---------- | --------- | -------------- |
| Hot Reload        | 216 LOC    | 145 LOC   | Simplified     |
| Syntax Validation | Yes        | No        | Fail-fast      |
| Memory Limit      | N/A        | 15 skills | LRU protection |

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
