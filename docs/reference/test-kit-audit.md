# Test Kit Audit

> Audit of omni-test-kit usage and recommended updates (2025-02)

## Summary

| Category            | Status     | Action                                                           |
| ------------------- | ---------- | ---------------------------------------------------------------- |
| testpaths           | Missing    | Add `packages/python/test-kit/tests`                             |
| plugin.py           | Bug        | Add `Path` import                                                |
| fixtures export     | Incomplete | Add `mock_knowledge_graph_store` to `__init__`                   |
| foundation conftest | Duplicate  | Use test_kit `project_root` / `skills_root`                      |
| core conftest       | Overlap    | Consider `SkillTestBuilder` for `skills_path` / `git_skill_path` |

---

## 1. testpaths

**Current:** `pyproject.toml` testpaths do not include `packages/python/test-kit/tests`.

**Impact:** `uv run pytest` does not run test-kit's own tests (59 tests: arrow, file, rag, scanner, skill_tester, link_graph, benchmarks).

**Recommendation:** Add `packages/python/test-kit/tests` to testpaths.

---

## 2. plugin.py – Missing Path Import

**Location:** `packages/python/test-kit/src/omni/test_kit/plugin.py`

**Issue:** `pytest_generate_tests` uses `Path` (line 41) but `Path` is not imported. Any test using `@omni_data_driven` would raise `NameError`.

**Fix:** Add `from pathlib import Path` at top of plugin.py.

---

## 3. Fixtures Export

**Location:** `packages/python/test-kit/src/omni/test_kit/fixtures/__init__.py`

**Issue:** `mock_knowledge_graph_store` is defined and exported in `rag.py` but not re-exported in fixtures `__init__.py`. Knowledge skill conftest imports it directly from `omni.test_kit.fixtures.rag`, which works, but for consistency and discoverability it should be in `__init__`.

**Recommendation:** Add `mock_knowledge_graph_store` to the rag import block and `__all__` in fixtures `__init__.py`.

---

## 4. Foundation conftest – Duplicate Fixtures

**Location:** `packages/python/foundation/tests/conftest.py`

**Issue:** Defines `project_root` and `skills_dir` that duplicate test_kit's `project_root` and `skills_root`. Test_kit provides these via the plugin (loaded project-wide).

**Recommendation:** Remove `project_root` and `skills_dir` from foundation conftest; use test_kit fixtures. Rename usages: `skills_dir` → `skills_root` in foundation tests.

---

## 5. Core conftest – Overlap with SkillTestBuilder

**Location:** `packages/python/core/tests/conftest.py`

**Issue:** `skills_path` and `git_skill_path` create temp skill directories manually. Test_kit provides `SkillTestBuilder`, `skill_directory`, `skill_test_suite` for similar purposes.

**Recommendation:** Low priority. Core fixtures are tailored for specific tests (`test_testing_layers_example` uses `skills_path`). Consolidation would require refactoring dependent tests. Document the overlap for future cleanup.

---

## 6. Test Kit Usage Across Project

| Package / Skill                                          | Uses test_kit                                  |
| -------------------------------------------------------- | ---------------------------------------------- |
| agent                                                    | Yes (conftest notes it; fixtures from plugin)  |
| core                                                     | Yes (asserts, vector fixtures, router tests)   |
| foundation                                               | Partial (has own project_root/skills_dir)      |
| knowledge                                                | Yes (rag fixtures, mock_knowledge_graph_store) |
| researcher                                               | Yes (omni_skill decorator)                     |
| git, code, advanced_tools, omniCell, memory, skill, demo | Yes (omni_skill, temp_yaml_file, etc.)         |

---

## 7. Documentation

- `docs/reference/test-kit.md` – Up to date; mentions `pytest_plugins = ["omni.test_kit"]` and fixtures.
- `docs/developer/testing.md` – References `@omni_data_driven`; no tests currently use it (plugin Path bug would break it).

---

## Recommended Changes (Priority)

1. **High:** Fix `plugin.py` Path import. ✅ Done
2. **High:** Add `packages/python/test-kit/tests` to testpaths. ✅ Done
3. **Medium:** Add `mock_knowledge_graph_store` to fixtures `__init__.py`. ✅ Done
4. **Low:** Refactor foundation conftest to use test_kit fixtures.
5. **Low:** Document core `skills_path` / test_kit overlap for future consolidation.

## Fixes Applied (Audit Follow-up)

- **SkillCommandTester.run()** – Added `_unwrap_mcp_content()` to parse MCP-style `content[0].text` JSON back to raw dict for simpler test assertions.
- **test_skill_command_tester_uses_repo_fallback_skills_path** – Replaced fragile `co_filename` path assertion with behavior check (echo output).
