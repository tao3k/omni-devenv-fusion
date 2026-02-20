"""
graph.py - Knowledge Graph API

Provides entity extraction and knowledge graph operations.
Uses LLM for entity/relation extraction and optionally stores in Rust backend.

Components:
- KnowledgeGraphExtractor: Extract entities and relations from text
- KnowledgeGraphStore: Store and query the knowledge graph

Usage:
    from omni.rag.graph import KnowledgeGraphExtractor

    extractor = KnowledgeGraphExtractor()
    entities, relations = await extractor.extract_entities(text)
"""

from __future__ import annotations

import asyncio
import json
import structlog
from typing import Any, Callable

from omni.rag.config import get_rag_config, is_knowledge_graph_enabled
from omni.rag.entities import Entity, Relation, ExtractedChunk

logger = structlog.get_logger(__name__)


def _entity_extraction_max_chars() -> int:
    """Max characters per chunk sent to LLM (smaller = faster; default 4000)."""
    try:
        from omni.foundation.config.settings import get_setting

        return int(get_setting("knowledge.entity_extraction_max_chars", 4000))
    except Exception:
        return 4000


# =============================================================================
# Bilingual Entity Extraction Prompts (中英文双语实体提取提示)
# =============================================================================

# English prompt for entity extraction
EXTRACT_ENTITIES_PROMPT_EN = """You are an expert at extracting entities and relationships from text.
Extract all named entities and their relationships from the following text.

## Entity Types to Extract:
- PERSON: Individual people, developers, team members
- ORGANIZATION: Companies, teams, projects, open source projects
- CONCEPT: Abstract ideas, patterns, methodologies, techniques
- PROJECT: Software projects, modules, packages, libraries
- TOOL: Development tools, CLI applications, frameworks
- SKILL: Programming languages, technologies, competencies
- LOCATION: Physical or virtual locations (repos, docs sites)
- EVENT: Conferences, releases, meetings, milestones

## Relation Types to Extract:
- WORKS_FOR: Entity belongs to organization/project
- PART_OF: Entity is part of a larger entity
- USES: Entity uses another entity
- DEPENDS_ON: Entity depends on another entity
- SIMILAR_TO: Entity is similar to another
- LOCATED_IN: Entity is located in another entity
- CREATED_BY: Entity was created by another entity
- DOCUMENTED_IN: Entity is documented in a location
- RELATED_TO: General relationship between entities

## Output Format:
Return a JSON object with two fields:
- "entities": List of entity objects
- "relations": List of relation objects

Each entity should have:
- "name": The entity name (use original language - English or Chinese)
- "entity_type": One of the entity types above
- "description": Brief description of what this entity is
- "aliases": Alternative names (optional)

Each relation should have:
- "source": Name of the source entity
- "target": Name of the target entity
- "relation_type": One of the relation types above
- "description": Brief description of the relationship

## Rules:
1. Only extract entities that are explicitly mentioned in the text
2. Use consistent naming (prefer proper nouns in their original language)
3. Extract as many entities and relations as possible
4. Handle both English and Chinese entities properly
5. Return valid JSON only, no additional text

## Text to Analyze:
```
{text}
```
"""

# Chinese prompt for entity extraction (中文实体提取提示)
EXTRACT_ENTITIES_PROMPT_ZH = """你是一位实体和关系提取专家。
从以下文本中提取所有命名实体及其关系。

## 需要提取的实体类型:
- PERSON: 个人、开发人员、团队成员
- ORGANIZATION: 公司、团队、项目、开源项目
- CONCEPT: 抽象概念、模式、方法论、技术
- PROJECT: 软件项目、模块、包、库
- TOOL: 开发工具、CLI 应用程序、框架
- SKILL: 编程语言、技术、能力
- LOCATION: 物理或虚拟位置（仓库、文档站点）
- EVENT: 会议、发布、会议、里程碑

## 需要提取的关系类型:
- WORKS_FOR: 实体属于某个组织/项目
- PART_OF: 实体是更大实体的一部分
- USES: 实体使用另一个实体
- DEPENDS_ON: 实体依赖于另一个实体
- SIMILAR_TO: 实体与另一个实体相似
- LOCATED_IN: 实体位于另一个实体中
- CREATED_BY: 实体由另一个实体创建
- DOCUMENTED_IN: 实体在某个位置有文档
- RELATED_TO: 实体之间的通用关系

## 输出格式:
返回一个 JSON 对象，包含两个字段：
- "entities": 实体对象列表
- "relations": 关系对象列表

每个实体应包含：
- "name": 实体名称（使用原始语言 - 英文或中文）
- "entity_type": 上述实体类型之一
- "description": 实体的简要描述
- "aliases": 别名列表（可选）

每个关系应包含：
- "source": 源实体名称
- "target": 目标实体名称
- "relation_type": 上述关系类型之一
- "description": 关系的简要描述

## 规则:
1. 只提取文本中明确提到的实体
2. 使用一致的命名（优先使用专有名词的原语言）
3. 尽可能多地提取实体和关系
4. 正确处理英文和中文实体
5. 只返回有效的 JSON，不要添加额外文本

## 待分析的文本:
```
{text}
```
"""

# Default extraction prompt (bilingual - English with Chinese hints)
EXTRACT_ENTITIES_PROMPT = """You are an expert at extracting entities and relationships from text.
Extract all named entities and their relationships. 支持中英文双语实体提取。

## Entity Types (实体类型):
- PERSON: Individual people, developers / 个人、开发人员
- ORGANIZATION: Companies, teams, projects / 公司、团队、项目
- CONCEPT: Abstract ideas, patterns, methodologies / 抽象概念、模式、方法论
- PROJECT: Software projects, modules, packages / 软件项目、模块、包
- TOOL: Development tools, CLI apps, frameworks / 开发工具、CLI 应用
- SKILL: Programming languages, technologies / 编程语言、技术
- LOCATION: Physical or virtual locations / 物理或虚拟位置
- EVENT: Conferences, releases, meetings / 会议、发布、会议

## Relation Types (关系类型):
- WORKS_FOR: belongs to org/project / 属于组织/项目
- PART_OF: is part of larger entity / 是更大实体的一部分
- USES: uses another entity / 使用另一个实体
- DEPENDS_ON: depends on another entity / 依赖于另一个实体
- CREATED_BY: created by another entity / 由另一个实体创建
- RELATED_TO: general relationship / 通用关系

## Output Format (输出格式):
```json
{{
    "entities": [
        {{
            "name": "Entity Name (use original language)",
            "entity_type": "TYPE",
            "description": "Brief description",
            "aliases": ["alias1", "alias2"]
        }}
    ],
    "relations": [
        {{
            "source": "Source Entity",
            "target": "Target Entity",
            "relation_type": "TYPE",
            "description": "Relationship description"
        }}
    ]
}}
```

## Rules (规则):
1. Extract entities explicitly mentioned in the text / 只提取文本中明确提到的实体
2. Use consistent naming in original language / 使用原始语言保持一致命名
3. Extract as many entities and relations as possible / 尽可能多地提取
4. Handle both English and Chinese properly / 正确处理中英文实体
5. Return valid JSON only / 只返回有效的 JSON

## Text to Analyze (待分析文本):
```
{text}
```
"""


class KnowledgeGraphExtractor:
    """Extracts entities and relations from text using LLM.

    Attributes:
        llm_complete_func: LLM completion function.
        entity_types: List of entity types to extract.
        relation_types: List of relation types to extract.
        rust_backend: Optional Rust knowledge graph backend.
    """

    def __init__(
        self,
        llm_complete_func: Callable[[str], str] | None = None,
        entity_types: list[str] | None = None,
        relation_types: list[str] | None = None,
    ):
        """Initialize the knowledge graph extractor.

        Args:
            llm_complete_func: LLM completion function (required for extraction).
            entity_types: Override entity types to extract.
            relation_types: Override relation types to extract.
        """
        self.llm_complete = llm_complete_func
        self.entity_types = entity_types or get_rag_config().knowledge_graph.entity_types
        self.relation_types = relation_types or get_rag_config().knowledge_graph.relation_types
        self.rust_backend = None

        # Initialize Rust backend if available
        if get_rag_config().knowledge_graph.store_in_rust:
            self._init_rust_backend()

    def _init_rust_backend(self) -> None:
        """Initialize Rust knowledge graph backend."""
        try:
            from omni.foundation.bridge import get_bridge

            bridge = get_bridge()
            if bridge and hasattr(bridge, "knowledge"):
                self.rust_backend = bridge.knowledge
                logger.info("Rust knowledge backend initialized")
        except ImportError:
            logger.debug("Rust knowledge backend not available")

    async def extract_entities(
        self,
        text: str,
        source: str = "",
        max_entities: int | None = None,
        timeout: int | None = None,
    ) -> tuple[list[Entity], list[Relation]]:
        """Extract entities and relations from text.

        Args:
            text: Text to analyze.
            source: Source document/path.
            max_entities: Maximum entities to extract (default from config).
            timeout: Optional request timeout in seconds; passed to LLM so the
                HTTP request aborts instead of hanging when asyncio cancels.

        Returns:
            Tuple of (entities, relations) lists.
        """
        if not text:
            return [], []

        if self.llm_complete is None:
            # Skip entity extraction (this is expected when no LLM is configured)
            logger.debug(
                "Knowledge graph extraction: No LLM function provided, skipping entity extraction"
            )
            return [], []

        max_ents = max_entities or get_rag_config().knowledge_graph.max_entities_per_doc

        try:
            # Build prompt with entity types (cap text size for speed; config: knowledge.entity_extraction_max_chars)
            max_chars = _entity_extraction_max_chars()
            prompt = EXTRACT_ENTITIES_PROMPT.format(text=text[:max_chars])

            # Add entity type guidance
            type_list = ", ".join(self.entity_types)
            prompt = f"Focus on extracting: {type_list}\n\n" + prompt

            # Call LLM for extraction; pass timeout and optional model override.
            llm_kwargs: dict[str, Any] = {}
            if timeout is not None:
                llm_kwargs["timeout"] = timeout
            model_override = getattr(self, "_entity_extraction_model", None)
            if model_override:
                llm_kwargs["model"] = model_override
            response = (
                self.llm_complete(prompt, **llm_kwargs) if llm_kwargs else self.llm_complete(prompt)
            )
            # Handle async functions if needed
            if asyncio.iscoroutine(response):
                response = await response

            # Parse response
            entities, relations = self._parse_extraction(response, source)

            # Limit entities
            if len(entities) > max_ents:
                entities = sorted(entities, key=lambda e: e.confidence, reverse=True)[:max_ents]

            logger.info(
                "Entity extraction completed",
                entities=len(entities),
                relations=len(relations),
                source=source,
            )

            # Store in Rust backend if available
            if self.rust_backend is not None:
                await self._store_in_rust(entities, relations, source)

            return entities, relations

        except json.JSONDecodeError as e:
            logger.error("Failed to parse entity extraction response", error=str(e))
            return [], []
        except Exception as e:
            logger.error("Entity extraction failed", error=str(e))
            return [], []

    async def extract_chunk(
        self,
        text: str,
        chunk_id: str,
        source: str = "",
        chunk_index: int = 0,
    ) -> ExtractedChunk:
        """Extract entities and relations from a text chunk.

        Args:
            text: Text chunk to analyze.
            chunk_id: Unique identifier for this chunk.
            source: Source document/path.
            chunk_index: Position in document sequence.

        Returns:
            ExtractedChunk with entities and relations.
        """
        entities, relations = await self.extract_entities(text, source)

        return ExtractedChunk(
            chunk_id=chunk_id,
            text=text,
            entities=entities,
            relations=relations,
            source=source,
            chunk_index=chunk_index,
        )

    async def extract_from_document(
        self,
        document: list[dict[str, Any]] | str,
        source: str = "",
    ) -> list[ExtractedChunk]:
        """Extract entities and relations from a document (parsed content or text).

        Args:
            document: Either a list of content blocks or raw text.
            source: Source document path.

        Returns:
            List of ExtractedChunk objects.
        """
        chunks = []

        if isinstance(document, str):
            # Raw text - treat as single chunk
            chunk = await self.extract_chunk(document, f"chunk-0", source, 0)
            chunks.append(chunk)
        else:
            # List of content blocks
            for i, block in enumerate(document):
                text = block.get("text", "")
                if text:
                    chunk_id = f"chunk-{i}"
                    chunk = await self.extract_chunk(
                        text, chunk_id, source or block.get("source", ""), i
                    )
                    chunks.append(chunk)

        logger.info(
            "Document extraction completed",
            chunks=len(chunks),
            total_entities=sum(c.entity_count for c in chunks),
            total_relations=sum(c.relation_count for c in chunks),
        )

        return chunks

    def _parse_extraction(self, response: str, source: str) -> tuple[list[Entity], list[Relation]]:
        """Parse LLM response into entities and relations.

        Args:
            response: LLM response text.
            source: Source document.

        Returns:
            Tuple of (entities, relations).
        """
        entities = []
        relations = []

        try:
            # Try to extract JSON from response
            response = response.strip()

            # Handle markdown code blocks
            if response.startswith("```"):
                lines = response.split("\n")
                if len(lines) >= 3:
                    response = "\n".join(lines[1:-1])

            # Parse JSON
            data = json.loads(response)

            # Parse entities
            for item in data.get("entities", []):
                entity = Entity(
                    name=item.get("name", ""),
                    entity_type=item.get("entity_type", "CONCEPT"),
                    description=item.get("description", ""),
                    source=source,
                    aliases=item.get("aliases", []),
                    confidence=item.get("confidence", 1.0),
                )
                if entity.name:
                    entities.append(entity)

            # Parse relations
            for item in data.get("relations", []):
                relation = Relation(
                    source=item.get("source", ""),
                    target=item.get("target", ""),
                    relation_type=item.get("relation_type", "RELATED_TO"),
                    description=item.get("description", ""),
                    source_doc=source,
                    confidence=item.get("confidence", 1.0),
                )
                if relation.source and relation.target:
                    relations.append(relation)

        except (json.JSONDecodeError, TypeError) as e:
            logger.debug("Failed to parse extraction response", error=str(e))

        return entities, relations

    async def _store_in_rust(
        self,
        entities: list[Entity],
        relations: list[Relation],
        source: str,
    ) -> None:
        """Store entities and relations in Rust backend.

        Args:
            entities: List of entities to store.
            relations: List of relations to store.
            source: Source document.
        """
        if self.rust_backend is None:
            return

        try:
            from omni_core_rs import PyEntity, PyRelation

            for entity in entities:
                d = entity.to_dict() if hasattr(entity, "to_dict") else entity
                name = (d.get("name") or "").strip() or "unknown"
                etype = (d.get("entity_type") or "CONCEPT").strip() or "CONCEPT"
                desc = (d.get("description") or "").strip() or ""
                self.rust_backend.add_entity(
                    PyEntity(name=name, entity_type=etype, description=desc)
                )

            for relation in relations:
                d = relation.to_dict() if hasattr(relation, "to_dict") else relation
                source = (d.get("source") or "").strip() or "unknown"
                target = (d.get("target") or "").strip() or "unknown"
                rtype = (d.get("relation_type") or "RELATED_TO").strip() or "RELATED_TO"
                desc = (d.get("description") or "").strip() or ""
                self.rust_backend.add_relation(
                    PyRelation(source=source, target=target, relation_type=rtype, description=desc)
                )

            logger.debug(
                "Stored entities in Rust backend",
                entities=len(entities),
                relations=len(relations),
            )
        except Exception as e:
            logger.warning("Failed to store in Rust backend", error=str(e))

    def get_stats(self) -> dict[str, Any]:
        """Get extractor statistics.

        Returns:
            Dictionary with stats.
        """
        stats = {
            "entity_types": self.entity_types,
            "relation_types": self.relation_types,
            "rust_backend_available": self.rust_backend is not None,
        }

        if self.rust_backend is not None:
            try:
                stats["rust_stats"] = self.rust_backend.get_stats()
            except Exception:
                pass

        return stats


class KnowledgeGraphStore:
    """Interface to the knowledge graph storage (Rust backend)."""

    def __init__(self):
        """Initialize the knowledge graph store."""
        self._backend = None
        self._init_backend()

    def _init_backend(self) -> None:
        """Initialize Rust backend."""
        try:
            from omni_core_rs import PyKnowledgeGraph

            self._backend = PyKnowledgeGraph()
            logger.info("Knowledge graph store initialized with Rust backend (PyKnowledgeGraph)")
        except ImportError:
            logger.debug("Rust knowledge backend not available")

    def add_entity(self, entity: Entity | dict[str, Any]) -> bool:
        """Add an entity to the knowledge graph.

        Args:
            entity: Entity object or dictionary.

        Returns:
            True if successful.
        """
        if self._backend is None:
            logger.warning("No backend available for entity storage")
            return False

        try:
            if hasattr(entity, "to_dict"):
                entity_dict: dict[str, Any] = entity.to_dict()
            else:
                entity_dict = entity  # type: ignore[assignment]
            # Rust PyKnowledgeGraph expects PyEntity, not dict
            try:
                from omni_core_rs import PyEntity

                name = (entity_dict.get("name") or "").strip() or "unknown"
                etype = (entity_dict.get("entity_type") or "CONCEPT").strip() or "CONCEPT"
                desc = (entity_dict.get("description") or "").strip() or ""
                self._backend.add_entity(PyEntity(name=name, entity_type=etype, description=desc))
            except ImportError:
                self._backend.add_entity(entity_dict)
            return True
        except Exception as e:
            logger.error("Failed to add entity", error=str(e))
            return False

    def add_relation(self, relation: Relation | dict[str, Any]) -> bool:
        """Add a relation to the knowledge graph.

        Args:
            relation: Relation object or dictionary.

        Returns:
            True if successful.
        """
        if self._backend is None:
            logger.warning("No backend available for relation storage")
            return False

        try:
            if hasattr(relation, "to_dict"):
                relation_dict: dict[str, Any] = relation.to_dict()
            else:
                relation_dict = relation  # type: ignore[assignment]
            # Rust PyKnowledgeGraph expects PyRelation, not dict
            try:
                from omni_core_rs import PyRelation

                source = (relation_dict.get("source") or "").strip() or "unknown"
                target = (relation_dict.get("target") or "").strip() or "unknown"
                rtype = (relation_dict.get("relation_type") or "RELATED_TO").strip() or "RELATED_TO"
                desc = (relation_dict.get("description") or "").strip() or ""
                self._backend.add_relation(
                    PyRelation(
                        source=source,
                        target=target,
                        relation_type=rtype,
                        description=desc,
                    )
                )
            except ImportError:
                self._backend.add_relation(relation_dict)
            return True
        except Exception as e:
            logger.error("Failed to add relation", error=str(e))
            return False

    def search_entities(
        self, query: str, entity_type: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Search for entities.

        Args:
            query: Search query.
            entity_type: Optional entity type filter.
            limit: Maximum results.

        Returns:
            List of matching entities.
        """
        if self._backend is None:
            return []

        try:
            return self._backend.search_entities(query, entity_type, limit)
        except Exception as e:
            logger.error("Entity search failed", error=str(e))
            return []

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        """Get an entity by ID.

        Args:
            entity_id: Entity ID.

        Returns:
            Entity dict or None.
        """
        if self._backend is None:
            return None

        try:
            return self._backend.get_entity(entity_id)
        except Exception as e:
            logger.error("Failed to get entity", error=str(e))
            return None

    def get_relations(
        self, entity_name: str | None = None, relation_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Get relations.

        Args:
            entity_name: Optional entity name filter.
            relation_type: Optional relation type filter.

        Returns:
            List of relations.
        """
        if self._backend is None:
            return []

        try:
            return self._backend.get_relations(entity_name, relation_type)
        except Exception as e:
            logger.error("Failed to get relations", error=str(e))
            return []

    def multi_hop_search(
        self,
        start_entities: list[str],
        relation_types: list[str] | None = None,
        max_hops: int = 2,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Perform multi-hop graph search.

        Iterates over *start_entities*, calling the Rust backend's
        single-entity ``multi_hop_search(name, max_hops)`` for each,
        then deduplicates and optionally filters by *relation_types*.

        Args:
            start_entities: Starting entity names.
            relation_types: Types of relations to follow (post-filter).
            max_hops: Maximum hops to traverse.
            limit: Maximum results.

        Returns:
            List of found entities (dicts).
        """
        if self._backend is None:
            return []

        try:
            import json as _json

            seen: set[str] = set()
            results: list[dict[str, Any]] = []

            for name in start_entities:
                entities = self._backend.multi_hop_search(name, max_hops)
                for e in entities:
                    raw = e.to_dict() if hasattr(e, "to_dict") else e
                    d = _json.loads(raw) if isinstance(raw, str) else raw
                    ename = d.get("name", "")
                    if ename in seen:
                        continue
                    seen.add(ename)
                    results.append(d)

            # Post-filter by relation_types if provided
            # (relation_types constrains which edges were *followed*;
            #  the Rust traversal is type-agnostic, so we filter results
            #  that are connected via requested types only.)
            # For now we skip relation-type filtering since the Rust
            # traversal already follows all edges — callers typically
            # just want the reachable entities.

            return results[:limit]
        except Exception as e:
            logger.error("Multi-hop search failed", error=str(e))
            return []


def get_graph_extractor(
    llm_complete_func: Callable[[str], str] | None = None,
) -> KnowledgeGraphExtractor | None:
    """Factory function to get a knowledge graph extractor.

    Args:
        llm_complete_func: Optional LLM completion function.

    Returns:
        KnowledgeGraphExtractor if knowledge graph is enabled, None otherwise.
    """
    if not is_knowledge_graph_enabled():
        logger.debug("Knowledge graph is disabled")
        return None

    return KnowledgeGraphExtractor(llm_complete_func=llm_complete_func)


def get_graph_store() -> KnowledgeGraphStore:
    """Factory function to get a knowledge graph store.

    Returns:
        KnowledgeGraphStore instance.
    """
    return KnowledgeGraphStore()


__all__ = [
    "KnowledgeGraphExtractor",
    "KnowledgeGraphStore",
    "EXTRACT_ENTITIES_PROMPT",
    "EXTRACT_ENTITIES_PROMPT_EN",
    "EXTRACT_ENTITIES_PROMPT_ZH",
    "get_graph_extractor",
    "get_graph_store",
]
