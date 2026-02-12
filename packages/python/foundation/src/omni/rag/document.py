"""
document.py - Document Parsing Integration

Provides document parsing capabilities using RAG-Anything's parser hierarchy:
- DoclingParser for PDF and document understanding
- MineruParser for PDF extraction
- Batch processing for multiple files
"""

from __future__ import annotations

import asyncio
import os
import re
import structlog
import tempfile
from pathlib import Path
from typing import Any

logger = structlog.get_logger(__name__)

# Document formats supported by RAG-Anything
SUPPORTED_FORMATS = {
    ".pdf": ["docling", "mineru"],
    ".docx": ["libreoffice"],
    ".pptx": ["libreoffice"],
    ".xlsx": ["libreoffice"],
    ".md": ["text"],
    ".txt": ["text"],
    ".png": ["ocr"],
    ".jpg": ["ocr"],
    ".jpeg": ["ocr"],
}


class DocumentParser:
    """
    Document parser using RAG-Anything's parsing pipeline.

    Supports:
    - PDF files via Docling or MinerU
    - Office documents (docx, pptx, xlsx) via LibreOffice
    - Images via OCR
    - Plain text/markdown
    """

    def __init__(
        self,
        llm_complete_func: callable | None = None,
        default_method: str = "auto",
    ):
        """
        Initialize the document parser.

        Args:
            llm_complete_func: Optional LLM function for enhanced parsing
            default_method: Default parsing method (auto, docling, mineru)
        """
        self.llm_complete = llm_complete_func
        self.default_method = default_method
        self._parser_cache: dict[str, Any] = {}

    def _clean_text(self, text: str) -> str:
        """Remove base64 image data to save tokens."""
        # Pattern to match markdown image with base64: ![alt](data:image/...)
        # We capture the alt text to preserve it
        pattern = r"!\[(.*?)\]\(data:image\/[a-zA-Z]+;base64,[^\)]+\)"
        return re.sub(pattern, r"![\1]([Image Data Removed])", text)

    async def parse(
        self,
        file_path: str,
        method: str | None = None,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        Parse a document into structured content blocks.

        Args:
            file_path: Path to the document
            method: Parsing method (auto, docling, mineru, etc.)
            **kwargs: Additional parser options

        Returns:
            List of content blocks with type, text, and metadata
        """
        ext = Path(file_path).suffix.lower()

        if ext not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {ext}")

        # Use default method if not specified
        method = method or self.default_method

        try:
            # Use RAG-Anything's BatchParser
            from raganything.batch_parser import BatchParser

            parser = BatchParser(
                parser_type=method if method != "auto" else "docling",
                max_workers=4,
                show_progress=False,
            )

            # Create temp dir for outputs
            with tempfile.TemporaryDirectory() as temp_dir:
                # Parse the document
                status = await asyncio.to_thread(
                    parser.process_single_file,
                    file_path,
                    output_dir=temp_dir,  # Provide valid temp dir
                    parse_method=method,
                )

                # Check status (raganything returns (success, path, error))
                if isinstance(status, tuple) and len(status) >= 3:
                    success, _, error = status
                    if not success:
                        logger.error(f"Parsing failed: {error}")
                        return self._fallback_parse(file_path, ext)

                # Find generated markdown file
                parsed_text = ""
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith(".md"):
                            try:
                                p = Path(root) / file
                                raw_text = p.read_text(encoding="utf-8")
                                parsed_text = self._clean_text(raw_text)
                                break
                            except Exception as e:
                                logger.warning(f"Failed to read parsed file {file}: {e}")
                    if parsed_text:
                        break

                if not parsed_text:
                    logger.warning("No markdown output found in temp dir")
                    return self._fallback_parse(file_path, ext)

                # Create standard blocks from parsed text
                blocks = [
                    {
                        "type": "text",
                        "text": parsed_text,
                        "index": 0,
                        "source": file_path,
                        "metadata": {"parser": method},
                    }
                ]

            logger.info(
                "Document parsed",
                file=file_path,
                method=method,
                blocks=len(blocks),
            )

            return blocks

        except ImportError:
            # Fallback to simple text extraction
            logger.warning("RAG-Anything not available, using fallback parser")
            return self._fallback_parse(file_path, ext)

    def _convert_result(self, result: Any, file_path: str) -> list[dict[str, Any]]:
        """Convert parser result to standard content blocks."""
        blocks = []

        # Handle different result types
        if hasattr(result, "chunks"):
            for i, chunk in enumerate(result.chunks):
                blocks.append(
                    {
                        "type": chunk.get("type", "text"),
                        "text": chunk.get("text", ""),
                        "index": i,
                        "source": file_path,
                        "metadata": {
                            "parser": getattr(result, "parser_type", "unknown"),
                        },
                    }
                )
        elif isinstance(result, dict):
            # Raw dict result
            blocks.append(
                {
                    "type": "text",
                    "text": str(result),
                    "index": 0,
                    "source": file_path,
                    "metadata": {"parser": "unknown"},
                }
            )
        elif isinstance(result, (list, tuple)):
            for i, item in enumerate(result):
                blocks.append(
                    {
                        "type": "text",
                        "text": str(item),
                        "index": i,
                        "source": file_path,
                    }
                )
        else:
            blocks.append(
                {
                    "type": "text",
                    "text": str(result),
                    "index": 0,
                    "source": file_path,
                }
            )

        return blocks

    def _fallback_parse(self, file_path: str, ext: str) -> list[dict[str, Any]]:
        """Fallback parser for when RAG-Anything is unavailable."""
        path = Path(file_path)

        if ext in [".md", ".txt"]:
            content = path.read_text()
            return [
                {
                    "type": "text",
                    "text": content,
                    "index": 0,
                    "source": file_path,
                    "metadata": {"parser": "fallback"},
                }
            ]
        elif ext in [".png", ".jpg", ".jpeg"]:
            return [
                {
                    "type": "image",
                    "text": f"[Image: {file_path}]",
                    "index": 0,
                    "source": file_path,
                    "metadata": {"parser": "fallback"},
                }
            ]
        else:
            # gracefully handle missing dependencies instead of crashing
            logger.warning(f"No parser available for {ext}, returning placeholder.")
            return [
                {
                    "type": "text",
                    "text": f"[Content of {file_path} could not be parsed - missing dependencies]",
                    "index": 0,
                    "source": file_path,
                    "metadata": {"parser": "fallback", "error": "missing_dependencies"},
                }
            ]


async def parse_document(
    file_path: str,
    method: str | None = None,
    **kwargs,
) -> list[dict[str, Any]]:
    """
    Convenience function to parse a document.

    Args:
        file_path: Path to the document
        method: Parsing method
        **kwargs: Additional options

    Returns:
        List of content blocks
    """
    parser = DocumentParser(default_method=method or "auto")
    return await parser.parse(file_path, method, **kwargs)


async def parse_documents_batch(
    file_paths: list[str],
    method: str = "auto",
    max_workers: int = 4,
    show_progress: bool = True,
) -> dict[str, Any]:
    """
    Parse multiple documents in batch.

    Args:
        file_paths: List of file paths
        method: Parsing method
        max_workers: Maximum parallel workers
        show_progress: Show progress bar

    Returns:
        dict with successful and failed files
    """
    try:
        from raganything.batch_parser import BatchParser

        parser = BatchParser(
            parser_type=method if method != "auto" else "docling",
            max_workers=max_workers,
            show_progress=show_progress,
        )

        result = await asyncio.to_thread(
            parser.process_batch,
            file_paths,
            output_dir=None,
            parse_method=method,
        )

        return {
            "successful": result.successful_files,
            "failed": list(result.errors.keys()),
            "total": result.total_files,
            "success_rate": result.success_rate,
        }

    except ImportError:
        logger.error("RAG-Anything not installed")
        raise RuntimeError("RAG-Anything not installed")
