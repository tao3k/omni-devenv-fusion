"""
Hybrid (vector + keyword) search.

Rust-backed hybrid search with canonical payload validation and cache.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog
from pydantic import ValidationError

from omni.foundation.services.embedding import EmbeddingUnavailableError, get_embedding_service
from omni.foundation.services.vector_schema import parse_hybrid_payload

from .constants import (
    ERROR_HYBRID_PAYLOAD_VALIDATION,
    ERROR_HYBRID_RUNTIME,
    ERROR_HYBRID_TABLE_NOT_FOUND,
)
from .models import SearchResult
from .search import search_embed_timeout

if TYPE_CHECKING:
    from .store import VectorStoreClient

logger = structlog.get_logger(__name__)


async def run_hybrid_search(
    client: VectorStoreClient,
    query: str,
    n_results: int,
    collection: str,
    keywords: list[str] | None,
    use_cache: bool,
) -> list[SearchResult]:
    """Run hybrid search: embed query, then Rust search_hybrid. Uses client cache and store."""
    store = client._get_store_for_collection(collection)
    if not store:
        logger.warning("VectorStore not available, returning empty hybrid results")
        return []

    kw = sorted(keywords) if keywords else [query]
    kw_key = ",".join(kw)
    cache_key = f"hybrid:{collection}:{query}:{kw_key}:{n_results}"
    if use_cache:
        cached = client._search_cache.get(cache_key)
        if cached is not None:
            logger.debug("Hybrid cache hit for query: %s...", query[:50])
            return cached

    try:
        embed_timeout = search_embed_timeout()
        service = get_embedding_service()
        try:
            embed_result = await asyncio.wait_for(
                asyncio.to_thread(service.embed, query),
                timeout=embed_timeout,
            )
            vector = embed_result[0]
        except asyncio.TimeoutError:
            raise EmbeddingUnavailableError(
                f"Embedding timed out after {embed_timeout}s for hybrid search. "
                "Ensure MCP embedding service is running and responsive."
            )
        except EmbeddingUnavailableError:
            raise
        except Exception as e:
            raise EmbeddingUnavailableError(f"Embedding failed for hybrid search: {e}") from e
        results_json = store.search_hybrid(collection, vector, kw, n_results)

        parsed: list[SearchResult] = []
        for raw in results_json:
            payload = parse_hybrid_payload(raw)
            result_id, content, metadata, score = payload.to_search_result_fields()
            parsed.append(
                SearchResult(
                    content=content,
                    metadata=metadata,
                    distance=max(0.0, 1.0 - score),
                    score=score,
                    id=result_id,
                )
            )
        if use_cache:
            client._search_cache.set(cache_key, parsed)
        return parsed
    except EmbeddingUnavailableError:
        raise
    except (ValidationError, ValueError) as e:
        client._log_error(
            "Hybrid search failed",
            error_code=ERROR_HYBRID_PAYLOAD_VALIDATION,
            cause="payload_validation",
            error=str(e),
            collection=collection,
        )
        return []
    except Exception as e:
        if client._is_table_not_found(e):
            logger.debug(
                "VectorStore hybrid collection not found",
                collection=collection,
                error_code=ERROR_HYBRID_TABLE_NOT_FOUND,
            )
            return []
        client._log_error(
            "Hybrid search failed",
            error_code=ERROR_HYBRID_RUNTIME,
            cause="runtime",
            error=str(e),
            collection=collection,
        )
        return []
