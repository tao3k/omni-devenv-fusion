"""
example.py - RAG-Anything Integration Usage Examples

Quick examples for using the RAG integration in Omni skills.
"""

import asyncio
from pathlib import Path

from omni.rag import create_rag_adapter


# Example 1: Basic document processing
async def example_basic_processing():
    """Process a PDF document with multimodal capabilities."""
    rag = create_rag_adapter(
        llm_complete_func=my_llm_complete,
        llm_vision_func=my_vision_complete,
    )

    # Process a PDF with images, tables, and equations
    result = await rag.process_document(
        file_path="docs/technical_report.pdf",
        multimodal=True,
    )

    print(f"Processed: {result}")


# Example 2: Query the knowledge base
async def example_query():
    """Query the processed documents."""
    rag = create_rag_adapter(
        llm_complete_func=my_llm_complete,
    )

    # Text query
    response = await rag.aquery(
        query="What are the key findings in the report?",
        mode="hybrid",
    )

    print(f"Response: {response}")


# Example 3: Query with image attachment
async def example_multimodal_query():
    """Query with an image attachment."""
    rag = create_rag_adapter(
        llm_complete_func=my_llm_complete,
        llm_vision_func=my_vision_complete,
    )

    response = await rag.aquery_with_multimodal(
        query="Describe this chart and explain its significance",
        multimodal_content=[
            {
                "type": "image",
                "img_path": "charts/revenue_growth.png",
                "image_caption": ["Quarterly revenue growth 2024"],
            }
        ],
    )

    print(f"Multimodal response: {response}")


# Example 4: Direct text processing
async def example_text_processing():
    """Process text content directly."""
    rag = create_rag_adapter(
        llm_complete_func=my_llm_complete,
    )

    result = await rag.process_text(
        content="""
        The company achieved significant milestones in Q4 2023.
        - Revenue increased by 45% year-over-year
        - Customer base grew to 2M+ users
        - Launched 3 new products
        """,
        doc_id="company_update_2024",
        metadata={"source": "internal_report"},
    )

    print(f"Text processed: {result}")


# Example 5: Integration with Omni services
async def example_with_omni_services():
    """Use with existing Omni embedding and LLM services."""
    from omni.foundation import get_embedding_service, get_llm_client

    embedding_service = get_embedding_service()
    llm_client = get_llm_client()

    def embed_func(texts):
        """Wrapper using Omni's embedding service."""
        return embedding_service.embed_batch(texts)

    def llm_complete(prompt, **kwargs):
        """Wrapper using Omni's LLM client."""
        return asyncio.run(llm_client.complete(prompt, **kwargs))

    rag = create_rag_adapter(
        llm_complete_func=llm_complete,
        embed_func=embed_func,
        enable_image_processing=True,
        enable_table_processing=True,
    )

    result = await rag.process_document("paper.pdf")
    print(f"Processed with Omni services: {result}")


# Helper functions (replace with actual implementations)
def my_llm_complete(prompt, **kwargs):
    """Your LLM completion function."""
    # Implementation depends on your LLM setup
    return {"content": "LLM response here"}


def my_vision_complete(image_b64, **kwargs):
    """Your vision model function for image analysis."""
    # Implementation depends on your VLM setup
    return {"description": "Image analysis here"}


if __name__ == "__main__":
    print("RAG-Anything Integration Examples")
    print("=" * 40)

    # Run examples
    asyncio.run(example_basic_processing())
    asyncio.run(example_query())
    asyncio.run(example_text_processing())
