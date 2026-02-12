"""
adapter.py - RAG-Anything ↔ Omni Integration Adapter

Bridges RAG-Anything's multimodal processing with Omni's existing services:
- EmbeddingService for vector generation
- LLM Client for text/vision completion
- LanceDB vector store for storage
"""

from __future__ import annotations

import json
import structlog
from pathlib import Path
from typing import Any

from raganything import RAGAnything, RAGAnythingConfig
from raganything.modalprocessors import (
    ImageModalProcessor,
    TableModalProcessor,
    EquationModalProcessor,
)

logger = structlog.get_logger(__name__)


class OmniRAGAdapter:
    """
    Omni-Dev Fusion adapter for RAG-Anything.

    Reuses Omni's existing services while gaining RAG-Anything's:
    - Multimodal processing (images, tables, equations)
    - Document parsing (PDF via Docling/MinerU)
    - Batch processing with progress tracking
    - Robust JSON parsing for LLM outputs
    """

    def __init__(
        self,
        llm_complete_func: callable,
        llm_vision_func: callable | None = None,
        embed_func: callable | None = None,
        working_dir: str | None = None,
        enable_image_processing: bool = True,
        enable_table_processing: bool = True,
        enable_equation_processing: bool = True,
    ):
        """
        Initialize the RAG adapter.

        Args:
            llm_complete_func: LLM completion function (text)
            llm_vision_func: Optional VLM function for image analysis
            embed_func: Optional embedding function (uses Omni's if not provided)
            working_dir: Working directory for RAG-Anything storage
            enable_image_processing: Enable image content extraction
            enable_table_processing: Enable table structure recognition
            enable_equation_processing: Enable mathematical notation extraction
        """
        self.llm_complete = llm_complete_func
        self.llm_vision = llm_vision_func
        self.embed = embed_func

        # Configure RAG-Anything
        self.config = RAGAnythingConfig(
            working_dir=working_dir or str(Path("~/.omni/rag").expanduser()),
            enable_image_processing=enable_image_processing,
            enable_table_processing=enable_table_processing,
            enable_equation_processing=enable_equation_processing,
        )

        # Initialize RAG-Anything (but don't start yet)
        self._rag: RAGAnything | None = None

        logger.info(
            "OmniRAGAdapter initialized",
            working_dir=self.config.working_dir,
            image_proc=enable_image_processing,
            table_proc=enable_table_processing,
            equation_proc=enable_equation_processing,
        )

    def _ensure_rag(self) -> RAGAnything:
        """Ensure RAG-Anything is initialized."""
        if self._rag is None:
            self._rag = RAGAnything(
                config=self.config,
                llm_model_func=self.llm_complete,
                vision_model_func=self.llm_vision,
                embed_func=self.embed,
            )
        return self._rag

    async def process_document(
        self,
        file_path: str,
        multimodal: bool = True,
        scheme_name: str = "auto",
    ) -> dict[str, Any]:
        """
        Process a document with RAG-Anything.

        Args:
            file_path: Path to the document (PDF, Markdown, etc.)
            multimodal: Enable multimodal content extraction
            scheme_name: Processing scheme (auto, parallel, sequential)

        Returns:
            dict with processing results
        """
        try:
            rag = self._ensure_rag()

            # Import InsertionScheme
            from raganything import InsertionScheme

            # Map string to enum
            scheme_map = {
                "auto": InsertionScheme.AUTO,
                "parallel": InsertionScheme.PARALLEL,
                "sequential": InsertionScheme.SEQUENTIAL,
            }
            scheme = scheme_map.get(scheme_name.lower(), InsertionScheme.AUTO)

            # Process document
            result = await rag.ainsert(
                input=file_path,
                scheme_name=scheme,
            )

            logger.info(
                "Document processed",
                file=file_path,
                result_type=type(result).__name__,
            )

            return result if isinstance(result, dict) else {"result": result}

        except ImportError as e:
            logger.error("RAG-Anything not available", error=str(e))
            raise RuntimeError("RAG-Anything not installed. Run: pip install raganything") from e
        except Exception as e:
            logger.error("Failed to process document", file=file_path, error=str(e))
            raise

    async def process_text(
        self,
        content: str,
        doc_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Process text content directly.

        Args:
            content: Text content to process
            doc_id: Optional document ID
            metadata: Optional metadata

        Returns:
            dict with processing results
        """
        try:
            rag = self._ensure_rag()

            result = await rag.ainsert(
                input=content,
                ids=doc_id,
            )

            return result if isinstance(result, dict) else {"result": result}

        except Exception as e:
            logger.error("Failed to process text", error=str(e))
            raise

    async def aquery(
        self,
        query: str,
        mode: str = "hybrid",
        system_prompt: str | None = None,
    ) -> str:
        """
        Query the knowledge base.

        Args:
            query: Query string
            mode: Retrieval mode (hybrid, local, global)
            system_prompt: Optional system prompt override

        Returns:
            Query response string
        """
        try:
            rag = self._ensure_rag()

            result = await rag.aquery(
                query=query,
                mode=mode,
                system_prompt=system_prompt,
            )

            return result

        except Exception as e:
            logger.error("Query failed", query=query, error=str(e))
            raise

    async def aquery_with_multimodal(
        self,
        query: str,
        multimodal_content: list[dict[str, Any]],
        mode: str = "hybrid",
    ) -> str:
        """
        Query with multimodal content attachments.

        Args:
            query: Query string
            multimodal_content: List of multimodal items (images, tables, etc.)
            mode: Retrieval mode

        Returns:
            Query response string
        """
        try:
            rag = self._ensure_rag()

            result = await rag.aquery_with_multimodal(
                query=query,
                multimodal_content=multimodal_content,
                mode=mode,
            )

            return result

        except Exception as e:
            logger.error(
                "Multimodal query failed",
                query=query,
                error=str(e),
            )
            raise

    def get_status(self) -> dict[str, Any]:
        """Get adapter status and configuration."""
        return {
            "initialized": self._rag is not None,
            "config": {
                "working_dir": self.config.working_dir,
                "image_processing": self.config.enable_image_processing,
                "table_processing": self.config.enable_table_processing,
                "equation_processing": self.config.enable_equation_processing,
            },
            "has_vision_model": self.llm_vision is not None,
            "has_embed_func": self.embed is not None,
        }


def create_rag_adapter(
    llm_complete_func: callable,
    llm_vision_func: callable | None = None,
    embed_func: callable | None = None,
    **kwargs,
) -> OmniRAGAdapter:
    """
    Factory function to create a RAG adapter with common defaults.

    Args:
        llm_complete_func: LLM completion function (required)
        llm_vision_func: Optional VLM function for images
        embed_func: Optional embedding function
        **kwargs: Additional OmniRAGAdapter kwargs

    Returns:
        Configured OmniRAGAdapter instance
    """
    return OmniRAGAdapter(
        llm_complete_func=llm_complete_func,
        llm_vision_func=llm_vision_func,
        embed_func=embed_func,
        **kwargs,
    )
