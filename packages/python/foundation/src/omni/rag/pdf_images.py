"""
PDF image extraction — UltraRAG-style build_image_corpus.

Extracts page images from PDFs via pymupdf (page.get_pixmap), saves to cache,
returns manifest of (page_num, image_path) for downstream use.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

try:
    import fitz  # pymupdf

    PYMUPDF_AVAILABLE = True
except ImportError:
    fitz = None  # type: ignore[assignment]
    PYMUPDF_AVAILABLE = False


def extract_pdf_images(
    pdf_path: str | Path,
    output_dir: str | Path | None = None,
    dpi: int = 150,
    format: str = "png",
) -> list[dict[str, Any]]:
    """Extract page images from a PDF (UltraRAG build_image_corpus style).

    Uses pymupdf page.get_pixmap() per page, saves to output_dir.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory for saved images. Default: PRJ_CACHE(omni-vector/images/{stem}).
        dpi: Resolution for pixmap (default 150).
        format: Output format: "png" or "jpeg".

    Returns:
        List of dicts: [{"page": 1, "image_path": "...", "source": "..."}, ...].
        Empty list if pymupdf unavailable or not a PDF.
    """
    if not PYMUPDF_AVAILABLE:
        return []

    path = Path(pdf_path)
    if path.suffix.lower() != ".pdf":
        return []

    try:
        from omni.foundation import PRJ_CACHE
    except ImportError:
        return []

    if output_dir is None:
        stem = path.stem
        safe_stem = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:12]
        output_dir = PRJ_CACHE("omni-vector", "images", f"{stem}_{safe_stem}")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    source_str = str(path)

    try:
        doc = fitz.open(path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            ext = "png" if format.lower() == "png" else "jpg"
            img_path = out / f"page_{page_num + 1:04d}.{ext}"
            pix.save(str(img_path))
            results.append(
                {
                    "page": page_num + 1,
                    "image_path": str(img_path),
                    "source": source_str,
                }
            )
            del pix  # Release pymupdf native memory (avoids leak in test loops)
        doc.close()
    except Exception:
        return []

    return results
