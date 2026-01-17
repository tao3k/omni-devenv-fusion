"""
Pytest fixture constants for skill testing.

Reserved and builtin fixture names that skills should not override.
"""

# Reserved pytest fixture names that skills should not override
RESERVED_FIXTURES = {
    # Core fixtures
    "request",
    "config",
    "cache",
    "session",
    "workerinput",
    "workeroutput",
    # IO fixtures
    "capsys",
    "capfd",
    "caplog",
    "pytestconfig",
    "record_testsuite_property",
    # Mocking fixtures
    "monkeypatch",
    "patch",
    "mock",
    "pytester",
    # Flow control
    "testdir",
    "localpath",
    "tmp_path",
    "tmp_path_factory",
    "tmpdir",
    "tmpdir_factory",
    # Debugging
    "record_xml_property",
    "record_property",
}

# Pytest built-in fixtures (comprehensive list)
PYTEST_BUILTIN_FIXTURES = {
    "request",
    "pytestconfig",
    "cache",
    "testpath",
    "pytester",
    "capsys",
    "capfd",
    "caplog",
    "record_testsuite_property",
    "record_property",
    "monkeypatch",
    "patch",
    "mock",
    "testdir",
    "localpath",
    "tmpdir",
    "tmpdir_factory",
    "tmp_path",
    "tmp_path_factory",
    "session",
    "workerinput",
    "workeroutput",
    "logging",
    "hookwrapper",
    "mark",
}
