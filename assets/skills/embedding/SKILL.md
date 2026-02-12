# Embedding Skill

Provides text embedding generation via the unified embedding service.

## Commands

### embed_texts

Generate embeddings for multiple texts.

**Input:**

```json
{
  "texts": ["text1", "text2"]
}
```

**Output:**

```json
{
  "success": true,
  "vectors": [[0.1, 0.2, ...], [0.3, 0.4, ...]],
  "count": 2,
  "dimension": 2560
}
```

### embed_single

Generate embedding for a single text.

**Input:**

```json
{
  "text": "hello world"
}
```

**Output:**

```json
{
  "success": true,
  "vector": [0.1, 0.2, ...],
  "dimension": 2560
}
```

## Usage

```bash
# Via MCP client
@omni("embedding.embed_texts", {"texts": ["query text"]})

# Via Python
from omni.foundation.services.embedding import embed_batch
vectors = embed_batch(["text1", "text2"])
```

## Notes

- Uses Qwen/Qwen3-Embedding-4B model (2560 dimensions)
- Model is preloaded when MCP server starts
- Supports both batch and single text embedding
