import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


@dataclass
class SkillTestCase:
    name: str
    input: dict[str, Any]
    expected: Any
    context: dict[str, Any] | None = None
    config: dict[str, Any] | None = None


def load_test_cases(data_path: str) -> list[SkillTestCase]:
    path = Path(data_path)
    if not path.exists():
        return []

    data = []
    if path.suffix == ".json":
        with open(path) as f:
            data = json.load(f)
    elif path.suffix in [".yaml", ".yml"]:
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f)

    if not isinstance(data, list):
        return []

    return [
        SkillTestCase(
            name=case.get("name", f"case_{i}"),
            input=case.get("input", {}),
            expected=case.get("expected"),
            context=case.get("context"),
            config=case.get("config"),
        )
        for i, case in enumerate(data)
    ]


def data_driven(data_path: str):
    return pytest.mark.omni_data_driven(data_path=data_path)


def omni_skill(name: str):
    return pytest.mark.omni_skill(name=name)
