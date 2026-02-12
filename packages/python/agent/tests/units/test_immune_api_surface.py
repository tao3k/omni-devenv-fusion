from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from omni.agent.core.evolution.immune import __all__ as immune_exports
from omni.agent.core.evolution.immune.validator import SecurityViolation, StaticValidator


def test_immune_module_exports_expected_symbols():
    expected = {
        "ImmuneSystem",
        "ImmuneReport",
        "create_immune_system",
        "StaticValidator",
        "SecurityViolation",
        "scan_file",
        "scan_content",
        "quick_check",
        "SkillSimulator",
        "SimulationResult",
        "verify_skill",
        "rust_immune",
    }
    assert expected.issubset(set(immune_exports))


def test_static_validator_scan_content_adapts_rust_violation_dicts():
    rust_violations = [
        {
            "rule_id": "FORBIDDEN-IMPORT",
            "description": "Forbidden import: subprocess",
            "line": 2,
            "snippet": "import subprocess",
        }
    ]

    with patch(
        "omni.agent.core.evolution.immune.validator.scan_code_security",
        return_value=(False, rust_violations),
    ) as mock_scan:
        is_safe, violations = StaticValidator.scan_content("import subprocess\n", "x.py")

    assert is_safe is False
    assert len(violations) == 1
    assert isinstance(violations[0], SecurityViolation)
    assert violations[0].rule_id == "FORBIDDEN-IMPORT"
    mock_scan.assert_called_once_with("import subprocess\n")


def test_static_validator_scan_reads_file_and_calls_rust_backend(tmp_path: Path):
    py_file = tmp_path / "safe.py"
    py_file.write_text("def ok():\n    return 1\n")

    with patch(
        "omni.agent.core.evolution.immune.validator.scan_code_security",
        return_value=(True, []),
    ) as mock_scan:
        is_safe, violations = StaticValidator.scan(py_file)

    assert is_safe is True
    assert violations == []
    mock_scan.assert_called_once_with("def ok():\n    return 1\n")


def test_quick_check_uses_rust_is_code_safe():
    with patch(
        "omni.agent.core.evolution.immune.validator.is_code_safe",
        return_value=False,
    ) as mock_safe:
        result = StaticValidator.quick_check("eval('x')")

    assert result is False
    mock_safe.assert_called_once_with("eval('x')")


def test_validate_imports_extracts_import_rules():
    with patch(
        "omni.agent.core.evolution.immune.validator.scan_code_security",
        return_value=(
            False,
            [
                {"rule_id": "FORBIDDEN-IMPORT", "line": 1},
                {"rule_id": "DANGEROUS-CALL", "line": 3},
                {"rule_id": "IMPORT-RESTRICTED", "line": 5},
            ],
        ),
    ):
        rule_ids = StaticValidator.validate_imports("import os\nx=1\neval('x')\n")

    assert rule_ids == ["FORBIDDEN-IMPORT", "IMPORT-RESTRICTED"]
