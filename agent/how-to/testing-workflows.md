# Testing Workflows & Standards

> **Rule #1**: Fast tests first. Fail fast.
> **Rule #2**: No feature code without test code.
> **Rule #3**: Modified docs only → Skip tests.

---

## 1. Test Levels

| Level | Path | Scope | Command | Timeout | Rules |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Unit** | `mcp-server/tests/` | Single module | `just test-unit` | < 30s | Fast, no network/disk I/O |
| **Integration** | `tests/integration/` | Module interaction | `just test-int` | < 2m | Can touch DB/FS, mock external APIs |
| **E2E** | `tests/e2e/` | Full system | `just test-e2e` | < 10m | CI only, real external services |
| **MCP** | `mcp-server/tests/test_basic.py` | MCP tools | `just test-mcp` | < 60s | Verify all tools work |

---

## 2. Modified-Code Protocol

When running tests during development:

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Identify modified files (git diff --cached --name-only)│
└─────────────────────────────────────────────────────────────────┘
                            ↓
            ┌───────────────┴───────────────┐
            ↓                               ↓
    Only docs/*.md, agent/*.md changed?   Code files changed?
            ↓                               ↓
        SKIP TESTS              ┌───────────┴───────────┐
                                ↓                       ↓
                        Only mcp-server/            Other code
                        changed?                    changes?
                            ↓                           ↓
                    Run: just test-mcp          Run: just test
                    (fast MCP tests)             (full test suite)
```

### Decision Matrix

| Modified Files | Action | Reason |
| :--- | :--- | :--- |
| `docs/`, `agent/`, `*.md` only | **Skip tests** | Docs don't affect code |
| `mcp-server/*.py` | Run `just test-mcp` | Test MCP tools only |
| `tool-router/**` | Run `just test-mcp` | Test routing only |
| `*.nix`, `devenv.nix` | Run `just test` | Infrastructure affects all |
| Mixed (code + docs) | Run `just test` | Code changes need testing |

---

## 3. Test Commands

```bash
# Agent-friendly commands
just test-unit      # Fast unit tests (< 30s)
just test-int       # Integration tests (< 2m)
just test-mcp       # MCP server tests (< 60s)
just test           # All tests (devenv test)
```

---

## 4. Standards Enforcement

### Test Naming
- Test files must match `test_*.py`
- Test functions must match `test_*`

### Coverage
- New logic must maintain or increase coverage
- Critical paths (orchestrator, coder) require tests

### MCP Tool Tests
Every new MCP tool must have a test in `mcp-server/tests/test_basic.py`:

```python
# === Tool N: tool_name ===
print("\nN️⃣  Testing 'tool_name'...")
success, text = send_tool(process, "tool_name", {...}, N)
if success and ("expected" in text.lower()):
    print(f"✅ tool_name working")
    results["tool_name"] = True
```

---

## 5. CI/CD Testing

In CI, always run the full suite:

```bash
just test-unit && just test-int && just test-mcp
```

---

## 6. Related Documentation

- [Git Workflow](./git-workflow.md) - Commit protocols
- [Writing Style](../../design/writing-style/00_index.md) - Documentation standards

---

*Built on the principle: "Test smart, not hard."*
