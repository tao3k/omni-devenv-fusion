# Testing Workflows & Standards

> **Rule #1**: Fast tests first. Fail fast.
> **Rule #2**: No feature code without test code.
> **Rule #3**: Modified docs only → Skip tests.

---

## 1. Test Levels

| Level           | Path                                                           | Scope                   | Command          | Timeout | Rules                               |
| :-------------- | :------------------------------------------------------------- | :---------------------- | :--------------- | :------ | :---------------------------------- |
| **Unit**        | `packages/python/agent/src/agent/tests/`                       | Single module           | `just test-unit` | < 30s   | Fast, no network/disk I/O           |
| **Integration** | `tests/integration/`                                           | Module interaction      | `just test-int`  | < 2m    | Can touch DB/FS, mock external APIs |
| **E2E**         | `tests/e2e/`                                                   | Full system             | `just test-e2e`  | < 10m   | CI only, real external services     |
| **MCP**         | `packages/python/agent/src/agent/tests/test_phase13_skills.py` | MCP tools + Performance | `just test-mcp`  | < 60s   | Verify all tools work + benchmarks  |

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

| Modified Files                 | Action              | Reason                     |
| :----------------------------- | :------------------ | :------------------------- |
| `docs/`, `agent/`, `*.md` only | **Skip tests**      | Docs don't affect code     |
| `mcp-server/*.py`              | Run `just test-mcp` | Test MCP tools only        |
| `tool-router/**`               | Run `just test-mcp` | Test routing only          |
| `*.nix`, `devenv.nix`          | Run `just test`     | Infrastructure affects all |
| Mixed (code + docs)            | Run `just test`     | Code changes need testing  |

---

## 3. Test Commands

```bash
# Agent-friendly commands
just test-unit      # Fast unit tests (< 30s)
just test-int       # Integration tests (< 2m)
just test-mcp       # MCP server tests + Performance benchmarks (< 60s)
just test           # All tests (devenv test)
```

---

## 4. Phase 25+ MCP Test Patterns

### Async/Await Tests

All MCP tool tests must use `pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_omni_git_status(skill_manager):
    """Test omni tool with git.status command."""
    from agent.mcp_server import omni

    result = await omni("git.status")
    assert "Git Status" in result or "branch" in result
```

### Performance Benchmarks

Performance tests validate async architecture benefits:

```python
class TestAsyncPerformance:
    @pytest.mark.asyncio
    async def test_skill_manager_run_performance(self, skill_manager):
        """Benchmark SkillManager.run() execution time."""
        import time

        # Warm up
        await skill_manager.run("git", "git_status", {})

        # Benchmark
        iterations = 10
        start = time.perf_counter()
        for _ in range(iterations):
            await skill_manager.run("git", "git_status", {})
        elapsed = time.perf_counter() - start

        avg_time = elapsed / iterations
        assert avg_time < 0.1, f"Run too slow: {avg_time*1000:.2f}ms"

    @pytest.mark.asyncio
    async def test_concurrent_command_execution(self, skill_manager):
        """Test concurrent command execution (async benefit)."""
        import asyncio

        tasks = [
            skill_manager.run("git", "git_status", {}),
            skill_manager.run("git", "git_log", {"n": 2}),
            skill_manager.run("git", "git_branch", {}),
        ]
        results = await asyncio.gather(*tasks)
        assert len(results) == 3
        assert all(isinstance(r, str) for r in results)
```

### Multimodal Return Tests

Tests for Image and Context capabilities:

```python
class TestMultimodalReturns:
    def test_image_creation(self):
        """Test creating an Image object."""
        from mcp.server.fastmcp import Image
        import base64

        png_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==")
        image = Image(data=png_data)
        assert image.data == png_data

    @pytest.mark.asyncio
    async def test_context_progress_reporting(self):
        """Test Context.progress reporting."""
        from unittest.mock import MagicMock, AsyncMock
        from mcp.server.fastmcp import Context

        mock_ctx = MagicMock(spec=Context)
        mock_ctx.report_progress = AsyncMock()

        await mock_ctx.report_progress(0, 100)
        await mock_ctx.report_progress(100, 100)

        assert mock_ctx.report_progress.call_count == 2
```

### Architecture Compliance Tests

Verify Phase 25+ architecture:

```python
class TestArchitectureCompliance:
    def test_only_one_tool_registered(self):
        """MCP server should only have ONE tool registered."""
        from agent.mcp_server import mcp

        tools = list(mcp._tool_manager._tools.values())
        assert len(tools) == 1

    def test_skill_manager_is_async(self):
        """SkillManager.run() should be async."""
        from agent.core.skill_manager import SkillManager
        import asyncio

        assert asyncio.iscoroutinefunction(SkillManager.run)
```

---

## 5. Test Categories

| Category                    | Test Class                   | Purpose                         |
| :-------------------------- | :--------------------------- | :------------------------------ |
| **Core Skills**             | `TestSkillDiscovery`         | Skill discovery and loading     |
| **Phase 25 Omni CLI**       | `TestSkillManagerOmniCLI`    | Single entry point commands     |
| **One Tool Architecture**   | `TestOneToolArchitecture`    | Verify `omni` tool registration |
| **Performance**             | `TestAsyncPerformance`       | Async execution benchmarks      |
| **Multimodal**              | `TestMultimodalReturns`      | Image, Context capabilities     |
| **Context Injection**       | `TestContextInjection`       | Context parameter validation    |
| **Architecture Compliance** | `TestArchitectureCompliance` | Phase 25+ requirements          |

---

## 6. Standards Enforcement

### Test Naming

- Test files must match `test_*.py`
- Test functions must match `test_*`
- Async tests must have `@pytest.mark.asyncio`

### Coverage

- New logic must maintain or increase coverage
- Critical paths (orchestrator, coder) require tests
- Performance benchmarks for async operations

### MCP Tool Tests

Every new MCP tool must have tests in `test_phase13_skills.py`:

```python
@pytest.mark.asyncio
async def test_omni_dispatch_to_new_skill(skill_manager):
    """Test dispatch to new skill."""
    from agent.mcp_server import omni

    result = await omni("new_skill.command", {"arg": "value"})
    assert isinstance(result, str)
```

---

## 7. CI/CD Testing

In CI, always run the full suite:

```bash
just test-unit && just test-int && just test-mcp
```

### MCP Test Output Example

```
[Performance] SkillManager.run() avg: 12.34ms
[Performance] omni dispatch avg: 8.45ms
[Performance] 3 concurrent commands: 15.67ms
[Performance] Skill loading: 234.56ms
======================== 96 passed, 4 warnings in 1.58s ========================
```

---

## 8. Related Documentation

- [Git Workflow](./git-workflow.md) - Commit protocols
- [MCP Best Practices](../../docs/reference/mcp-best-practices.md) - MCP SDK patterns
- Writing Style - Documentation standards

---

_Built on the principle: "Test smart, not hard."_
