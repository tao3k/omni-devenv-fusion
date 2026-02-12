from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from omni.agent.core.evolution.immune.system import ImmuneSystem


@pytest.mark.asyncio
async def test_process_candidate_rejects_on_static_scan_violation(tmp_path: Path):
    skill_file = tmp_path / "skill_a.py"
    skill_file.write_text("import os\n")

    violations = [
        {
            "rule_id": "FORBIDDEN-IMPORT",
            "description": "Forbidden import: os",
            "line": 1,
            "snippet": "import os",
        }
    ]

    with patch(
        "omni.agent.core.evolution.immune.system.scan_code_security",
        return_value=(False, violations),
    ) as mock_scan:
        immune = ImmuneSystem(require_simulation=False)
        report = await immune.process_candidate(skill_file)

    assert report.promoted is False
    assert report.static_analysis_passed is False
    assert report.static_violations == violations
    assert report.rejection_reason is not None
    mock_scan.assert_called_once()


@pytest.mark.asyncio
async def test_process_candidate_promotes_when_static_scan_passes(tmp_path: Path):
    skill_file = tmp_path / "skill_b.py"
    skill_file.write_text("def ok():\n    return 1\n")

    with patch(
        "omni.agent.core.evolution.immune.system.scan_code_security",
        return_value=(True, []),
    ) as mock_scan:
        immune = ImmuneSystem(require_simulation=False)
        report = await immune.process_candidate(skill_file)

    assert report.promoted is True
    assert report.static_analysis_passed is True
    assert report.static_violations == []
    assert report.rejection_reason is None
    mock_scan.assert_called_once()
