#!/usr/bin/env python3
"""Generate docs/reference/vector-search-options-contract.md from Python schema source."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the generated content differs from the file on disk.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "packages" / "python" / "foundation" / "src"))

    from omni.foundation.services.vector_schema import render_search_options_contract_markdown

    target = root / "docs" / "reference" / "vector-search-options-contract.md"
    rendered = render_search_options_contract_markdown()

    if args.check:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current != rendered:
            print(f"outdated: {target}")
            return 1
        print(f"up-to-date: {target}")
        return 0

    target.write_text(rendered, encoding="utf-8")
    print(f"wrote: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
