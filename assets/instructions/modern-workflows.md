# Modern Engineering Workflows (SOP)

This document defines the **Standard Operating Procedures (SOP)** for utilizing the Omni-Agent modern toolchain. You MUST adhere to these workflows to ensure efficiency, safety, and code quality.

## 1. The Architect Loop (New Features & Patterns)

**Trigger**: When asked to implement a new feature, library, or complex pattern.

**Anti-Pattern**: Guessing API usage or writing non-idiomatic code.

**Protocol**:

1. **Consult**: Use `knowledge.get_best_practice(topic="...")` immediately.
   - _Why_: This retrieves both the "Theory" (Docs) and "Practice" (Existing Code).
2. **Analyze**: Review the returned snippets to understand the project's specific style.
3. **Plan**: Draft a plan that mimics the existing patterns found in step 1.
4. **Implement**: Write code that is consistent with the codebase.

**Example**:

```python
# User: "Add a new CLI command with click"
# Step 1: Consult
best_practice = knowledge.get_best_practice(topic="click CLI commands")

# Step 2-4: Analyze -> Plan -> Implement based on patterns found
```

---

## 2. The Refactoring Loop (Search-and-Destroy)

**Trigger**: Renaming variables, updating APIs, or making bulk changes across multiple files (> 3 files).

**Anti-Pattern**: Editing files one by one using `code_tools.apply_file_edit`. This consumes excessive tokens and time.

**Protocol**:

1. **Discovery**: Use `advanced_tools.smart_search(pattern="...")` to assess the blast radius.
2. **Preview**: Use `advanced_tools.batch_replace(pattern="...", replacement="...", dry_run=True)`.
   - _Why_: Verify the regex captures exactly what you want (and nothing else) via the generated Diff.
3. **Apply**: If the Diff is correct, run `advanced_tools.batch_replace(..., dry_run=False)`.
4. **Verify**: Run `testing.run_pytest` to ensure no regressions.

**Example**:

```python
# User: "Rename all 'old_function' to 'new_function' in Python files"
# Step 1: Discovery
search = advanced_tools.smart_search(pattern="old_function", file_type="py")

# Step 2: Preview (SAFETY FIRST)
preview = advanced_tools.batch_replace(
    pattern="old_function",
    replacement="new_function",
    file_glob="**/*.py",
    dry_run=True
)

# Review diff...
# Step 3: Apply
apply = advanced_tools.batch_replace(
    pattern="old_function",
    replacement="new_function",
    file_glob="**/*.py",
    dry_run=False
)

# Step 4: Verify
test = testing.run_pytest(target="**/*.py")
```

---

## 3. The Quality Loop (Test-Driven Repair)

**Trigger**: Fixing bugs or test failures.

**Anti-Pattern**: Reading the entire file to find a bug mentioned in line 42.

**Protocol**:

1. **Diagnose**: Run `testing.run_pytest`. Look at the structured failures.
2. **Surgical Read**: Use `read_file(file_path="...", offset=42, limit=10)`.
   - _Why_: Focus only on the error location. Save tokens.
3. **Fix**: Use `code_tools.apply_file_edit` to fix the specific logic.
4. **Verify**: Rerun `testing.run_pytest` to confirm the fix (Green state).

**Example**:

```python
# User: "Fix the failing test"
# Step 1: Diagnose
result = testing.run_pytest(target="tests/test_calculator.py")

# result["failures"][0] = {"file": "tests/test_calculator.py", "line": 42, "error": "..."}

# Step 2: Surgical Read
context = read_file(
    file_path="tests/test_calculator.py",
    offset=42,
    limit=5
)

# Step 3: Fix
code_tools.apply_file_edit(
    file="tests/test_calculator.py",
    search_for="assert calculator.add(-1, -1) == 2",  # From context snippet
    replacement="assert calculator.add(-1, -1) == -2"
)

# Step 4: Verify
test = testing.run_pytest(target="tests/test_calculator.py")
assert test["success"] is True
```

---

## 4. The Toolchain Hierarchy

Always prefer the most specialized tool for the job:

| Single File Edit | `code_tools.apply_file_edit` |
| Multi-File Edit | `advanced_tools.batch_replace` |
| Surgical Read | `read_file` (with offset/limit) |
| Test Execution | `testing.run_pytest` |

---

## 5. Safety First Principles

### Batch Replace Safety Rules

1. **ALWAYS** use `dry_run=True` first
2. **REVIEW** the diff before applying
3. **LIMIT** scope with `file_glob` (e.g., `**/*.py`)
4. **CHECK** `files_matched` count - if unexpectedly high, refine pattern

### Surgical Reading

1. Use `read_file` (offset/limit) instead of full file reads
2. Set `limit` appropriately (5-10 is usually sufficient)
3. Focus on the error line returned by `run_pytest`

---

## 6. Workflow Quick Reference

| Scenario                     | Tools to Chain                                                                                 |
| ---------------------------- | ---------------------------------------------------------------------------------------------- |
| New feature with unknown API | `knowledge.get_best_practice` → Implement                                                      |
| Bulk rename/refactor         | `smart_search` → `batch_replace(dry_run=True)` → `batch_replace(dry_run=False)` → `run_pytest` |
| Fix test failure             | `run_pytest` → `read_file` → `apply_file_edit` → `run_pytest`                                  |
| Find patterns                | `smart_search` (prefer over `search_code`)                                                     |
| List files                   | `smart_find` (prefer over `list_directory`)                                                    |
| View structure               | `tree_view`                                                                                    |
