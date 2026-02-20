"""Tests for PDF image extraction (Phase 3.2 UltraRAG build_image_corpus style).

Uses omni.rag API; no hardcoded paths.
Explicit cleanup to avoid pymupdf memory leaks in parallel test runs.
"""

from __future__ import annotations

import gc
from pathlib import Path

import pytest


def test_extract_pdf_images_returns_manifest(tmp_path: Path):
    """extract_pdf_images returns list of {page, image_path, source} for each page."""
    pytest.importorskip("fitz")

    import fitz

    from omni.rag import extract_pdf_images

    # Create minimal 2-page PDF
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    try:
        p1 = doc.new_page()
        p1.insert_text((50, 50), "Page 1")
        p2 = doc.new_page()
        p2.insert_text((50, 50), "Page 2")
        doc.save(str(pdf_path))
    finally:
        doc.close()
        del doc

    out_dir = tmp_path / "images"
    result = extract_pdf_images(pdf_path, output_dir=str(out_dir), dpi=72, format="png")

    assert len(result) == 2
    assert result[0]["page"] == 1
    assert result[1]["page"] == 2
    assert result[0]["source"] == str(pdf_path)
    assert Path(result[0]["image_path"]).exists()
    assert Path(result[1]["image_path"]).exists()

    gc.collect()  # Release pymupdf native allocations


def test_extract_pdf_images_non_pdf_returns_empty(tmp_path: Path):
    """extract_pdf_images on non-PDF returns empty list."""
    pytest.importorskip("fitz")

    from omni.rag import extract_pdf_images

    # Use tmp_path instead of /tmp to avoid cross-test pollution
    result = extract_pdf_images(__file__, output_dir=str(tmp_path / "out"))
    assert result == []
