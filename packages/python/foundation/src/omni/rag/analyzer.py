"""
Knowledge Graph Analyzer using PyArrow/Polars

Provides advanced analysis capabilities for the Rust knowledge graph:
- Entity type distribution
- Relation pattern analysis
- Graph connectivity metrics
- Entity centrality scoring
- Export to Arrow/Parquet formats

Usage:
    from omni.rag import KnowledgeGraphAnalyzer

    analyzer = KnowledgeGraphAnalyzer()
    stats = analyzer.get_stats()
    df = analyzer.get_entities_dataframe()
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GraphAnalysisResult:
    """Result of graph analysis."""

    total_entities: int = 0
    total_relations: int = 0
    entity_types: dict[str, int] = field(default_factory=dict)
    relation_types: dict[str, int] = field(default_factory=dict)
    isolated_entities: list[str] = field(default_factory=list)
    highly_connected: list[dict[str, Any]] = field(default_factory=list)
    most_common_sources: list[dict[str, Any]] = field(default_factory=list)
    most_common_targets: list[dict[str, Any]] = field(default_factory=list)


class KnowledgeGraphAnalyzer:
    """Analyzer for Rust knowledge graph using PyArrow/Polars patterns."""

    def __init__(self, graph_path: str | None = None):
        """Initialize analyzer.

        Args:
            graph_path: Optional path to graph JSON file.
        """
        self.graph_path = graph_path
        self._entities: list[dict[str, Any]] = []
        self._relations: list[dict[str, Any]] = []

    def load_from_json(self, json_path: str) -> "KnowledgeGraphAnalyzer":
        """Load graph data from JSON file.

        Args:
            json_path: Path to graph JSON file.

        Returns:
            Self for method chaining.
        """
        path = Path(json_path)
        if not path.exists():
            logger.warning(f"Graph file not found: {json_path}")
            return self

        try:
            with open(path) as f:
                data = json.load(f)
                self._entities = data.get("entities", [])
                self._relations = data.get("relations", [])
                logger.info(
                    f"Loaded {len(self._entities)} entities and {len(self._relations)} relations"
                )
        except Exception as e:
            logger.error(f"Failed to load graph: {e}")

        return self

    def load_from_rust_graph(self, rust_graph: Any) -> "KnowledgeGraphAnalyzer":
        """Load graph data from Rust PyKnowledgeGraph.

        Args:
            rust_graph: PyKnowledgeGraph instance from omni_core_rs.

        Returns:
            Self for method chaining.
        """
        try:
            # Get all entities and relations as JSON
            entities_json = rust_graph.get_all_entities_json()
            relations_json = rust_graph.get_all_relations_json()

            self._entities = json.loads(entities_json)
            self._relations = json.loads(relations_json)

            logger.info(
                f"Loaded {len(self._entities)} entities and {len(self._relations)} relations from Rust"
            )
        except Exception as e:
            logger.error(f"Failed to load from Rust graph: {e}")

        return self

    def analyze(self) -> GraphAnalysisResult:
        """Perform full graph analysis.

        Returns:
            GraphAnalysisResult with all metrics.
        """
        result = GraphAnalysisResult()

        # Basic counts
        result.total_entities = len(self._entities)
        result.total_relations = len(self._relations)

        # Entity type distribution
        entity_types: dict[str, int] = {}
        for entity in self._entities:
            etype = entity.get("entity_type", "Unknown")
            entity_types[etype] = entity_types.get(etype, 0) + 1
        result.entity_types = entity_types

        # Relation type distribution
        relation_types: dict[str, int] = {}
        for rel in self._relations:
            rtype = rel.get("relation_type", "Unknown")
            relation_types[rtype] = relation_types.get(rtype, 0) + 1
        result.relation_types = relation_types

        # Connectivity analysis
        entity_connections: dict[str, dict[str, int]] = {}
        for rel in self._relations:
            source = rel.get("source", "")
            target = rel.get("target", "")

            if source not in entity_connections:
                entity_connections[source] = {"out": 0, "in": 0}
            entity_connections[source]["out"] += 1

            if target not in entity_connections:
                entity_connections[target] = {"out": 0, "in": 0}
            entity_connections[target]["in"] += 1

        # Find isolated entities (no connections)
        entity_names = {e.get("name", "") for e in self._entities}
        result.isolated_entities = [
            name
            for name in entity_names
            if name in entity_connections
            and entity_connections[name]["out"] == 0
            and entity_connections[name]["in"] == 0
        ]

        # Find highly connected entities
        connected = [
            {
                "name": name,
                "total": data["out"] + data["in"],
                "outgoing": data["out"],
                "incoming": data["in"],
            }
            for name, data in entity_connections.items()
            if data["out"] + data["in"] > 0
        ]
        result.highly_connected = sorted(connected, key=lambda x: x["total"], reverse=True)[:10]

        # Most common sources/targets
        source_counts: dict[str, int] = {}
        target_counts: dict[str, int] = {}
        for rel in self._relations:
            source = rel.get("source", "")
            target = rel.get("target", "")
            source_counts[source] = source_counts.get(source, 0) + 1
            target_counts[target] = target_counts.get(target, 0) + 1

        result.most_common_sources = [
            {"name": k, "count": v}
            for k, v in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        result.most_common_targets = [
            {"name": k, "count": v}
            for k, v in sorted(target_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        return result

    def get_entities_dataframe(self) -> list[dict[str, Any]]:
        """Get entities as a list of dicts (Polars-compatible format).

        Returns:
            List of entity dicts ready for Polars DataFrame creation.
        """
        return self._entities

    def get_relations_dataframe(self) -> list[dict[str, Any]]:
        """Get relations as a list of dicts (Polars-compatible format).

        Returns:
            List of relation dicts ready for Polars DataFrame creation.
        """
        return self._relations

    def get_stats(self) -> dict[str, Any]:
        """Get quick statistics summary.

        Returns:
            Dict with summary statistics.
        """
        result = self.analyze()
        return {
            "total_entities": result.total_entities,
            "total_relations": result.total_relations,
            "entity_type_count": len(result.entity_types),
            "relation_type_count": len(result.relation_types),
            "isolated_count": len(result.isolated_entities),
            "top_entity_types": dict(
                sorted(result.entity_types.items(), key=lambda x: x[1], reverse=True)[:5]
            ),
            "top_relation_types": dict(
                sorted(result.relation_types.items(), key=lambda x: x[1], reverse=True)[:5]
            ),
            "connectivity_ratio": (
                (result.total_entities - len(result.isolated_entities)) / result.total_entities
                if result.total_entities > 0
                else 0
            ),
        }

    def export_to_arrow(self, output_path: str) -> dict[str, str | None]:
        """Export graph data to Arrow format.

        Args:
            output_path: Path for output directory.

        Returns:
            Dict with paths to exported files.
        """
        import pyarrow as pa
        import pyarrow.json as paj  # noqa: F401

        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        entities_path: str | None = None
        relations_path: str | None = None

        # Export entities
        if self._entities:
            entities_table = pa.Table.from_pylist(self._entities)
            entities_path = str(output_dir / "entities.arrow")
            with pa.OSFile(entities_path, "wb") as sink:
                with pa.RecordBatchFileWriter(sink, entities_table.schema) as writer:
                    writer.write_table(entities_table)

        # Export relations
        if self._relations:
            relations_table = pa.Table.from_pylist(self._relations)
            relations_path = str(output_dir / "relations.arrow")
            with pa.OSFile(relations_path, "wb") as sink:
                with pa.RecordBatchFileWriter(sink, relations_table.schema) as writer:
                    writer.write_table(relations_table)

        # Export stats
        stats = self.get_stats()
        stats_path = str(output_dir / "stats.json")
        with open(stats_path, "w") as f:
            json.dump(stats, f, indent=2)

        return {
            "entities": entities_path,
            "relations": relations_path,
            "stats": stats_path,
        }

    def export_to_parquet(self, output_path: str) -> dict[str, str | None]:
        """Export graph data to Parquet format.

        Args:
            output_path: Path for output directory.

        Returns:
            Dict with paths to exported files.
        """
        import pyarrow as pa
        import pyarrow.parquet as pq

        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        entities_path: str | None = None
        relations_path: str | None = None

        # Export entities
        if self._entities:
            entities_table = pa.Table.from_pylist(self._entities)
            entities_path = str(output_dir / "entities.parquet")
            pq.write_table(entities_table, entities_path)

        # Export relations
        if self._relations:
            relations_table = pa.Table.from_pylist(self._relations)
            relations_path = str(output_dir / "relations.parquet")
            pq.write_table(relations_table, relations_path)

        return {
            "entities": entities_path,
            "relations": relations_path,
        }

    def find_similar_entities(self, entity_name: str, limit: int = 5) -> list[dict[str, Any]]:
        """Find entities with similar names (fuzzy matching).

        Args:
            entity_name: Name to match.
            limit: Maximum results.

        Returns:
            List of similar entities with similarity scores.
        """
        from difflib import SequenceMatcher

        target = entity_name.lower().strip()
        results = []

        for entity in self._entities:
            name = entity.get("name", "").lower()
            similarity = SequenceMatcher(None, target, name).ratio()

            if similarity > 0.5 and name != target:
                results.append(
                    {
                        "name": entity.get("name"),
                        "entity_type": entity.get("entity_type"),
                        "similarity": round(similarity, 3),
                    }
                )

        return sorted(results, key=lambda x: x["similarity"], reverse=True)[:limit]


# ============================================================================
# Polars Integration (Optional - requires polars installed)
# ============================================================================

try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    pl = None  # type: ignore
    POLARS_AVAILABLE = False


def create_entities_dataframe(entities: list[dict[str, Any]]) -> "pl.DataFrame":
    """Create Polars DataFrame from entities.

    Args:
        entities: List of entity dicts.

    Returns:
        Polars DataFrame.
    """
    if not entities:
        if pl is not None:
            return pl.DataFrame()
        return []  # type: ignore

    if pl is not None:
        return pl.DataFrame(entities)
    return entities  # type: ignore


def create_relations_dataframe(relations: list[dict[str, Any]]) -> "pl.DataFrame":
    """Create Polars DataFrame from relations.

    Args:
        relations: List of relation dicts.

    Returns:
        Polars DataFrame.
    """
    if not relations:
        if pl is not None:
            return pl.DataFrame()
        return []  # type: ignore

    if pl is not None:
        return pl.DataFrame(relations)
    return relations  # type: ignore


def analyze_entity_types(df: "pl.DataFrame") -> "pl.DataFrame":
    """Analyze entity type distribution.

    Args:
        df: Entities DataFrame.

    Returns:
        DataFrame with type counts.
    """
    if pl is None or df.is_empty():
        if pl is not None:
            return pl.DataFrame()
        return df

    return (
        df.group_by("entity_type")
        .agg(
            pl.count().alias("count"),
        )
        .sort("count", descending=True)
    )


def analyze_connections(df: "pl.DataFrame") -> "pl.DataFrame":
    """Analyze entity connections.

    Args:
        df: Relations DataFrame.

    Returns:
        DataFrame with connection counts.
    """
    if pl is None or df.is_empty():
        if pl is not None:
            return pl.DataFrame()
        return df

    sources = df.select(["source", "relation_type"]).with_columns(pl.lit("out").alias("direction"))
    targets = (
        df.select(["target", "relation_type"])
        .with_columns(pl.lit("in").alias("direction"))
        .rename({"target": "entity"})
    )

    sources = sources.rename({"source": "entity"})

    combined = (
        pl.concat([sources, targets])
        .group_by("entity")
        .agg(
            pl.count().alias("total_connections"),
            pl.list("direction").alias("directions"),
        )
        .sort("total_connections", descending=True)
    )

    return combined


# ============================================================================
# Convenience Functions
# ============================================================================


def load_and_analyze(
    graph_path: str | None = None,
    rust_graph: Any | None = None,
) -> tuple[KnowledgeGraphAnalyzer, GraphAnalysisResult]:
    """Load graph and perform analysis.

    Args:
        graph_path: Path to graph JSON file.
        rust_graph: Rust PyKnowledgeGraph instance.

    Returns:
        Tuple of (analyzer, result).
    """
    analyzer = KnowledgeGraphAnalyzer()

    if rust_graph is not None:
        analyzer.load_from_rust_graph(rust_graph)
    elif graph_path is not None:
        analyzer.load_from_json(graph_path)

    return analyzer, analyzer.analyze()


__all__ = [
    "KnowledgeGraphAnalyzer",
    "GraphAnalysisResult",
    "load_and_analyze",
    "create_entities_dataframe",
    "create_relations_dataframe",
    "analyze_entity_types",
    "analyze_connections",
    "POLARS_AVAILABLE",
]
