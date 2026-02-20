"""Regression tests for lazy imports in LangGraph namespaces."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap


def _run_python(code: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout.strip())


def test_omni_langgraph_import_is_lazy() -> None:
    payload = _run_python(
        textwrap.dedent(
            """
            import json
            import sys
            import omni.langgraph

            watched = [
                "omni.langgraph.graph",
                "omni.langgraph.orchestrator",
                "omni.langgraph.state",
                "omni.langgraph.visualize",
            ]
            print(json.dumps({name: (name in sys.modules) for name in watched}))
            """
        )
    )
    assert payload == {
        "omni.langgraph.graph": False,
        "omni.langgraph.orchestrator": False,
        "omni.langgraph.state": False,
        "omni.langgraph.visualize": False,
    }


def test_chunked_namespace_import_and_resolution_are_lazy() -> None:
    payload = _run_python(
        textwrap.dedent(
            """
            import json
            import sys
            import omni.langgraph.chunked as chunked

            before = {
                "engine_loaded": "omni.langgraph.chunked.engine" in sys.modules,
                "runner_loaded": "omni.langgraph.chunked.runner" in sys.modules,
            }
            _ = chunked.run_chunked_step
            after = {
                "engine_loaded": "omni.langgraph.chunked.engine" in sys.modules,
                "runner_loaded": "omni.langgraph.chunked.runner" in sys.modules,
            }
            print(json.dumps({"before": before, "after": after}))
            """
        )
    )
    assert payload == {
        "before": {"engine_loaded": False, "runner_loaded": False},
        "after": {"engine_loaded": True, "runner_loaded": True},
    }
