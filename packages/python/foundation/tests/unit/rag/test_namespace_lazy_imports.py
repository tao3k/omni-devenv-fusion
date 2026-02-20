"""Regression tests for lazy import contracts in `omni.rag` namespace."""

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


def test_omni_rag_import_is_lazy() -> None:
    payload = _run_python(
        textwrap.dedent(
            """
            import json
            import sys
            import omni.rag

            watched = [
                "omni.rag.analyzer",
                "omni.rag.graph",
                "omni.rag.multimodal",
                "omni.rag.retrieval",
            ]
            print(json.dumps({name: (name in sys.modules) for name in watched}))
            """
        )
    )
    assert payload == {
        "omni.rag.analyzer": False,
        "omni.rag.graph": False,
        "omni.rag.multimodal": False,
        "omni.rag.retrieval": False,
    }


def test_omni_rag_loads_retrieval_module_on_attribute_access() -> None:
    payload = _run_python(
        textwrap.dedent(
            """
            import json
            import sys
            import omni.rag as rag

            _ = rag.RetrievalConfig
            print(
                json.dumps(
                    {
                        "retrieval_loaded": "omni.rag.retrieval" in sys.modules,
                        "analyzer_loaded": "omni.rag.analyzer" in sys.modules,
                    }
                )
            )
            """
        )
    )
    assert payload == {
        "retrieval_loaded": True,
        "analyzer_loaded": False,
    }
