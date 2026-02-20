#!/usr/bin/env python3
"""Recall an ingested paper from knowledge_chunks and write chunks to a file.
Usage: uv run python scripts/recall_paper_to_file.py [query] [output_path]
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Add project packages to path when run as script
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "packages" / "python" / "foundation" / "src")
)
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "packages" / "python" / "core" / "src")
)


async def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "Pensieve StateLM stateful context memory tools"
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("pensieve-recalled.txt")

    from omni.foundation.services.vector import get_vector_store

    store = get_vector_store()
    if not store.store:
        print("Vector store not initialized. Run from repo root after ingest.", file=sys.stderr)
        sys.exit(1)

    results = await store.search(query, n_results=35, collection="knowledge_chunks")
    if not results:
        print("No results.", file=sys.stderr)
        sys.exit(1)

    lines = [f"# Recalled: {query}\n", f"# Chunks: {len(results)}\n\n"]
    for i, r in enumerate(results, 1):
        content = getattr(r, "content", "") or ""
        score = getattr(r, "distance", 0)
        score = 1.0 - score if hasattr(r, "distance") else getattr(r, "score", 0)
        lines.append(f"--- Chunk {i} (score={score:.3f}) ---\n")
        lines.append(content.strip() + "\n\n")

    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"Wrote {len(results)} chunks to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
