# Test-Driven Auto-Fix Loop (Scenario 1)

## Overview

**Scenario**: Test-driven auto-fix闭环 (Red-Green-Refactor Loop)

**Goal**: Enable the Agent to:

1. Run tests → 2. Find failures → 3. **Directly locate error line code** → 4. Read context → 5. Fix code → 6. Run tests again → 7. Success → 8. Commit

## Architecture Components

### 1. Testing Skill (`testing/scripts/pytest.py`)

Executes tests and returns structured failure data:

```python
@skill_command(
    name="run_pytest",
    description="Run pytest and return STRUCTURED failure data for auto-fixing.",
    autowire=True,
)
def run_pytest(
    target: str = ".",
    max_fail: int = 5,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
```

**Return Structure**:

```python
{
    "success": bool,           # All tests passed
    "failed": bool,            # Any failures
    "exit_code": int,          # Pytest return code
    "target": str,             # Test target path
    "summary": str,            # Output summary
    "failure_count": int,      # Number of failures
    "failures": [              # Structured failure list
        {
            "file": "path/to/file.py",    # File path
            "line": 42,                   # Error line number
            "test": "test_func_name",     # Test name
            "error": "AssertionError: ...", # Error message
            "traceback": "...",           # Traceback info
        },
    ],
    "raw_output": str,         # Raw output (on failure)
}
```

### 2. Filesystem Skill (`filesystem/scripts/io.py`)

Surgically reads file context:

```python
@skill_command(
    name="read_file_context",
    category="read",
    description="[SURGICAL READ] Read specific lines around a target line.",
    autowire=True,
)
def read_file_context(
    file_path: str,
    line_number: int,
    context_lines: int = 10,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
```

**Return Structure**:

```python
{
    "success": bool,           # Success status
    "file": "path/to/file.py", # File path
    "focus_line": 42,          # Focused line number
    "focus_content": "...",    # Content of focused line
    "context_before": 10,      # Lines before
    "context_after": 10,       # Lines after
    "total_lines": 100,        # Total lines in file
    "snippet": """             # Code snippet
       32 | def foo():
       33 |     x = 1
    -> 42 |     assert x == 2
       43 |     return x
    """,
}
```

## Complete Scenario Test

### Scenario: Test-Driven Code Fix Loop

#### Step 1: Run tests, find failure

```python
# Agent calls
result = run_pytest(target="tests/test_calculator.py")

# Returns
{
    "success": False,
    "failed": True,
    "exit_code": 1,
    "target": "tests/test_calculator.py",
    "failure_count": 1,
    "failures": [
        {
            "file": "tests/test_calculator.py",
            "line": 42,
            "test": "test_add_negative_numbers",
            "error": "AssertionError: -2 != 2",
            "traceback": """...
tests/test_calculator.py:42: in test_add_negative_numbers
    assert calculator.add(-1, -1) == 2
E   AssertionError: -2 != 2
..."""}
    ]
}
```

#### Step 2: Surgically read error context

```python
# Agent calls
context = read_file_context(
    file_path="tests/test_calculator.py",
    line_number=42,
    context_lines=5
)

# Returns
{
    "success": True,
    "file": "tests/test_calculator.py",
    "focus_line": 42,
    "focus_content": "assert calculator.add(-1, -1) == 2",
    "context_before": 5,
    "context_after": 5,
    "total_lines": 50,
    "snippet": """   37 | def test_add_positive_numbers():
   38 |     assert calculator.add(1, 2) == 3
   39 |
   40 | def test_add_negative_numbers():
   41 |     calc = Calculator()
-> 42 |     assert calculator.add(-1, -1) == 2
   43 |
   44 | def test_add_zero():
   45 |     assert calculator.add(5, 0) == 5"""
}
```

#### Step 3: View source implementation

```python
# Agent views Calculator.add implementation
source = read_file_context(
    file_path="src/calculator.py",
    line_number=15,
    context_lines=5
)
```

#### Step 4: Fix the code

```python
# Agent fixes the bug
apply_file_changes(changes=[
    FileOperation(
        action="replace",
        path="src/calculator.py",
        search_for="""    def add(self, a: int, b: int) -> int:
        return a + b""",
        content="""    def add(self, a: int, b: int) -> int:
        result = a + b
        if a < 0 and b < 0:
            return result  # Negative numbers sum correctly
        return result"""
    )
])
```

#### Step 5: Run tests again to verify

```python
# Agent runs tests again
result = run_pytest(target="tests/test_calculator.py")

# Returns
{
    "success": True,
    "failed": False,
    "exit_code": 0,
    "failure_count": 0,
    "failures": [],
    "summary": "=== 3 passed in 0.02s ==="
}
```

#### Step 6: Commit the fix

```python
# Agent uses smart-commit to commit
# /commit "fix: Calculator.add handles negative number addition
#
# - Fix test_add_negative_numbers test failure
# - Issue: add method returned wrong result for negatives
# - Fix: Confirmed negative addition logic is correct
#
# Tests: 3 passed"
```

## Integration Test Cases

### Test Case 1: Structured Failure Parsing

```python
def test_structured_failure_parsing():
    """Test run_pytest returns structured failure data."""
    sample_output = """============================= test session starts ==============================
tests/unit/test_example.py::test_divide_by_zero FAILED [100%]
tests/unit/test_example.py::test_divide_by_zero - AssertionError: 1 != 0

def test_divide_by_zero():
>   assert 1 / 0 == 0
E   AssertionError: 1 != 0
======
============================= short test summary info ===============================
FAILED tests/unit/test_example.py::test_divide_by_zero - AssertionError: 1 != 0
=========================== 1 failed in 0.01s ==========================="""

    failures = _parse_failures(sample_output, "")

    assert len(failures) >= 1
    assert failures[0]["file"] == "tests/unit/test_example.py"
    assert failures[0]["line"] > 0
    assert "test_divide_by_zero" in failures[0]["test"]
    assert "AssertionError" in failures[0]["error"]
```

### Test Case 2: Surgical File Reading

```python
def test_surgical_file_reading():
    """Test read_file_context returns correct context."""
    # Create test file
    content = "\n".join([f"line {i}" for i in range(1, 21)])

    # Read line 10, with 3 lines of context
    result = read_file_context(
        file_path="test.txt",
        line_number=10,
        context_lines=3
    )

    assert result["success"] is True
    assert result["focus_line"] == 10
    assert "line 10" in result["focus_content"]
    assert result["context_before"] == 3
    assert result["context_after"] == 3
    assert "-> 10" in result["snippet"]  # Focus line marker
```

### Test Case 3: Complete Fix Loop

```python
def test_full_fix_loop():
    """Test complete test-fix-verify loop."""
    from testing.scripts.pytest import run_pytest
    from filesystem.scripts.io import read_file_context
    from filesystem.scripts.io import apply_file_changes, FileOperation

    # 1. Run tests, simulate failure
    mock_failures = [
        {
            "file": "src/buggy.py",
            "line": 10,
            "test": "test_example",
            "error": "AssertionError",
        }
    ]

    # 2. Read error context
    context = read_file_context("src/buggy.py", line_number=10)
    assert context["success"] is True

    # 3. Fix the code
    result = apply_file_changes(changes=[
        FileOperation(
            action="replace",
            path="src/buggy.py",
            search_for="result = wrong_value",
            content="result = correct_value",
        )
    ])
    assert "Success" in result

    # 4. Verify tests pass (would use mock in actual test)
    verify_result = run_pytest("src/buggy.py")
```

## Performance and Security

### Performance Features

- **Failure Limit**: Max 10 failures returned to prevent token explosion
- **Timeout Control**: Test execution timeout set to 300 seconds
- **Fast Fail**: Uses `--maxfail 5` parameter

### Security Features

- **Path Safety Check**: All paths validated with `is_safe_path()`
- **Project Root Restriction**: Operations limited to project root
- **Read-First**: `read_file_context` is read-only operation

## Running Tests

```bash
# Run scenario tests
uv run pytest assets/skills/testing/tests/test_qa_skills.py -v
uv run pytest assets/skills/filesystem/tests/test_filesystem_io.py -v

# Run integration tests
uv run pytest packages/python/agent/tests/scenarios/ -v

# Run full test suite
uv run pytest packages/python/ -v
```

## Related Files

| File                                                   | Description                     |
| ------------------------------------------------------ | ------------------------------- |
| `assets/skills/testing/scripts/pytest.py`              | Testing skill implementation    |
| `assets/skills/filesystem/scripts/io.py`               | Filesystem skill implementation |
| `assets/skills/testing/tests/test_qa_skills.py`        | Testing skill tests             |
| `assets/skills/filesystem/tests/test_filesystem_io.py` | Filesystem skill tests          |
