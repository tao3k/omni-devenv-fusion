"""Typed records for backend-agnostic link-graph retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, cast

from omni.foundation.api.link_graph_schema import build_record
from omni.foundation.api.link_graph_search_options_schema import (
    SCHEMA_VERSION,
    build_options_record,
)


class LinkGraphDirection(str, Enum):
    """Edge direction relative to the queried stem."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"
    BOTH = "both"


LinkGraphMatchStrategy = Literal["fts", "path_fuzzy", "exact", "re"]
LinkGraphSortField = Literal[
    "score", "path", "title", "stem", "created", "modified", "random", "word_count"
]
LinkGraphSortOrder = Literal["asc", "desc"]
LinkGraphScope = Literal["doc_only", "section_only", "mixed"]
LinkGraphEdgeType = Literal["structural", "semantic", "provisional", "verified"]
LinkGraphPprSubgraphMode = Literal["auto", "disabled", "force"]


def _clean_string_list(items: list[Any] | tuple[Any, ...] | None) -> list[str]:
    if not items:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


@dataclass(frozen=True)
class LinkGraphSortTerm:
    """Single sort term used by schema-first search options."""

    field: LinkGraphSortField = "score"
    order: LinkGraphSortOrder = "desc"

    def to_record(self) -> dict[str, str]:
        return {"field": str(self.field), "order": str(self.order)}


@dataclass(frozen=True)
class LinkGraphTagFilter:
    """Boolean tag filter with all/any/not sets."""

    all: list[str] = field(default_factory=list)
    any: list[str] = field(default_factory=list)
    not_tags: list[str] = field(default_factory=list)

    def to_record(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        if self.all:
            out["all"] = _clean_string_list(self.all)
        if self.any:
            out["any"] = _clean_string_list(self.any)
        if self.not_tags:
            out["not"] = _clean_string_list(self.not_tags)
        return out


@dataclass(frozen=True)
class LinkGraphLinkFilter:
    """Directional link filter for link_to/linked_by."""

    seeds: list[str] = field(default_factory=list)
    negate: bool = False
    recursive: bool = False
    max_distance: int | None = None

    def to_record(self) -> dict[str, Any]:
        out: dict[str, Any] = {"seeds": _clean_string_list(self.seeds)}
        if self.negate:
            out["negate"] = True
        if self.recursive:
            out["recursive"] = True
        if self.max_distance is not None:
            out["max_distance"] = int(self.max_distance)
        return out


@dataclass(frozen=True)
class LinkGraphRelatedPprOptions:
    """PPR tuning options for related-notes retrieval."""

    alpha: float | None = None
    max_iter: int | None = None
    tol: float | None = None
    subgraph_mode: LinkGraphPprSubgraphMode | None = None

    def to_record(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.alpha is not None:
            out["alpha"] = float(self.alpha)
        if self.max_iter is not None:
            out["max_iter"] = int(self.max_iter)
        if self.tol is not None:
            out["tol"] = float(self.tol)
        if self.subgraph_mode is not None:
            out["subgraph_mode"] = str(self.subgraph_mode).strip().lower()
        return out


@dataclass(frozen=True)
class LinkGraphRelatedFilter:
    """Related-notes filter."""

    seeds: list[str] = field(default_factory=list)
    max_distance: int | None = None
    ppr: LinkGraphRelatedPprOptions | None = None

    def to_record(self) -> dict[str, Any]:
        out: dict[str, Any] = {"seeds": _clean_string_list(self.seeds)}
        if self.max_distance is not None:
            out["max_distance"] = int(self.max_distance)
        if self.ppr is not None:
            ppr_record = self.ppr.to_record()
            if ppr_record:
                out["ppr"] = ppr_record
        return out


@dataclass(frozen=True)
class LinkGraphSearchFilters:
    """Structured filters used by schema-first search options."""

    include_paths: list[str] = field(default_factory=list)
    exclude_paths: list[str] = field(default_factory=list)
    tags: LinkGraphTagFilter | None = None
    link_to: LinkGraphLinkFilter | None = None
    linked_by: LinkGraphLinkFilter | None = None
    related: LinkGraphRelatedFilter | None = None
    mentions_of: list[str] = field(default_factory=list)
    mentioned_by_notes: list[str] = field(default_factory=list)
    orphan: bool = False
    tagless: bool = False
    missing_backlink: bool = False
    scope: LinkGraphScope | None = None
    max_heading_level: int | None = None
    max_tree_hops: int | None = None
    collapse_to_doc: bool | None = None
    edge_types: list[LinkGraphEdgeType] = field(default_factory=list)
    per_doc_section_cap: int | None = None
    min_section_words: int | None = None

    def to_record(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        include_paths = _clean_string_list(self.include_paths)
        if include_paths:
            out["include_paths"] = include_paths
        exclude_paths = _clean_string_list(self.exclude_paths)
        if exclude_paths:
            out["exclude_paths"] = exclude_paths
        if self.tags is not None:
            tags_record = self.tags.to_record()
            if tags_record:
                out["tags"] = tags_record
        if self.link_to is not None:
            row = self.link_to.to_record()
            if row.get("seeds"):
                out["link_to"] = row
        if self.linked_by is not None:
            row = self.linked_by.to_record()
            if row.get("seeds"):
                out["linked_by"] = row
        if self.related is not None:
            row = self.related.to_record()
            if row.get("seeds"):
                out["related"] = row
        mentions_of = _clean_string_list(self.mentions_of)
        if mentions_of:
            out["mentions_of"] = mentions_of
        mentioned_by_notes = _clean_string_list(self.mentioned_by_notes)
        if mentioned_by_notes:
            out["mentioned_by_notes"] = mentioned_by_notes
        if self.orphan:
            out["orphan"] = True
        if self.tagless:
            out["tagless"] = True
        if self.missing_backlink:
            out["missing_backlink"] = True
        if self.scope is not None:
            out["scope"] = str(self.scope).strip().lower()
        if self.max_heading_level is not None:
            out["max_heading_level"] = int(self.max_heading_level)
        if self.max_tree_hops is not None:
            out["max_tree_hops"] = int(self.max_tree_hops)
        if self.collapse_to_doc is not None:
            out["collapse_to_doc"] = bool(self.collapse_to_doc)
        edge_types = _clean_string_list(cast("list[Any] | tuple[Any, ...] | None", self.edge_types))
        if edge_types:
            out["edge_types"] = [edge_type.strip().lower() for edge_type in edge_types]
        if self.per_doc_section_cap is not None:
            out["per_doc_section_cap"] = int(self.per_doc_section_cap)
        if self.min_section_words is not None:
            out["min_section_words"] = int(self.min_section_words)
        return out


@dataclass(frozen=True)
class LinkGraphHit:
    """Search hit from link-graph backend."""

    stem: str
    score: float
    title: str = ""
    path: str = ""
    best_section: str = ""
    match_reason: str = ""

    def to_record(self) -> dict[str, Any]:
        """Convert to canonical shared-schema record."""
        return build_record(
            kind="hit",
            stem=self.stem,
            title=self.title,
            path=self.path,
            score=float(self.score),
            best_section=self.best_section or None,
            match_reason=self.match_reason or None,
        )


@dataclass(frozen=True)
class LinkGraphNeighbor:
    """Neighbor stem connected to a query stem."""

    stem: str
    direction: LinkGraphDirection
    distance: int = 1
    title: str = ""
    path: str = ""

    def to_record(self) -> dict[str, Any]:
        """Convert to canonical shared-schema record."""
        return build_record(
            kind="neighbor",
            stem=self.stem,
            title=self.title,
            path=self.path,
            direction=self.direction.value,
            distance=int(self.distance),
        )


@dataclass(frozen=True)
class LinkGraphMetadata:
    """Per-stem metadata used for reranking and graph fusion."""

    stem: str
    tags: list[str] = field(default_factory=list)
    title: str = ""
    path: str = ""

    def to_record(self) -> dict[str, Any]:
        """Convert to canonical shared-schema record."""
        return build_record(
            kind="metadata",
            stem=self.stem,
            title=self.title,
            path=self.path,
            tags=[str(t) for t in self.tags],
        )


@dataclass(frozen=True)
class LinkGraphSearchOptions:
    """Canonical search options shared by LinkGraph backend adapters."""

    match_strategy: LinkGraphMatchStrategy = "fts"
    case_sensitive: bool = False
    sort_terms: list[LinkGraphSortTerm] = field(default_factory=lambda: [LinkGraphSortTerm()])
    filters: LinkGraphSearchFilters = field(default_factory=LinkGraphSearchFilters)
    created_after: int | None = None
    created_before: int | None = None
    modified_after: int | None = None
    modified_before: int | None = None

    def to_record(self) -> dict[str, Any]:
        """Convert to canonical shared-schema options payload."""
        sort_terms = [term.to_record() for term in self.sort_terms] if self.sort_terms else []
        if not sort_terms:
            sort_terms = [LinkGraphSortTerm().to_record()]
        filters_row = self.filters.to_record()
        tag_row = (
            (filters_row.get("tags") or {}) if isinstance(filters_row.get("tags"), dict) else {}
        )
        link_to_row = (
            (filters_row.get("link_to") or {})
            if isinstance(filters_row.get("link_to"), dict)
            else {}
        )
        linked_by_row = (
            (filters_row.get("linked_by") or {})
            if isinstance(filters_row.get("linked_by"), dict)
            else {}
        )
        related_row = (
            (filters_row.get("related") or {})
            if isinstance(filters_row.get("related"), dict)
            else {}
        )
        related_ppr_row = (
            (related_row.get("ppr") or {}) if isinstance(related_row.get("ppr"), dict) else {}
        )
        return build_options_record(
            match_strategy=self.match_strategy,
            case_sensitive=self.case_sensitive,
            sort_terms=sort_terms,
            include_paths=cast("list[str]", filters_row.get("include_paths") or []),
            exclude_paths=cast("list[str]", filters_row.get("exclude_paths") or []),
            tags_all=cast("list[str]", tag_row.get("all") or []),
            tags_any=cast("list[str]", tag_row.get("any") or []),
            tags_not=cast("list[str]", tag_row.get("not") or []),
            link_to=cast("list[str]", link_to_row.get("seeds") or []),
            link_to_negate=bool(link_to_row.get("negate", False)),
            link_to_recursive=bool(link_to_row.get("recursive", False)),
            link_to_max_distance=(
                int(link_to_row["max_distance"])
                if link_to_row.get("max_distance") is not None
                else None
            ),
            linked_by=cast("list[str]", linked_by_row.get("seeds") or []),
            linked_by_negate=bool(linked_by_row.get("negate", False)),
            linked_by_recursive=bool(linked_by_row.get("recursive", False)),
            linked_by_max_distance=(
                int(linked_by_row["max_distance"])
                if linked_by_row.get("max_distance") is not None
                else None
            ),
            related=cast("list[str]", related_row.get("seeds") or []),
            max_distance=(
                int(related_row["max_distance"])
                if related_row.get("max_distance") is not None
                else None
            ),
            related_ppr=cast("dict[str, Any] | None", related_ppr_row or None),
            mentions_of=cast("list[str]", filters_row.get("mentions_of") or []),
            mentioned_by_notes=cast("list[str]", filters_row.get("mentioned_by_notes") or []),
            orphan=bool(filters_row.get("orphan", False)),
            tagless=bool(filters_row.get("tagless", False)),
            missing_backlink=bool(filters_row.get("missing_backlink", False)),
            scope=(
                cast("LinkGraphScope", str(filters_row["scope"]).strip().lower())
                if filters_row.get("scope") is not None
                else None
            ),
            max_heading_level=(
                int(filters_row["max_heading_level"])
                if filters_row.get("max_heading_level") is not None
                else None
            ),
            max_tree_hops=(
                int(filters_row["max_tree_hops"])
                if filters_row.get("max_tree_hops") is not None
                else None
            ),
            collapse_to_doc=(
                bool(filters_row["collapse_to_doc"]) if "collapse_to_doc" in filters_row else None
            ),
            edge_types=cast("list[LinkGraphEdgeType]", filters_row.get("edge_types") or []),
            per_doc_section_cap=(
                int(filters_row["per_doc_section_cap"])
                if filters_row.get("per_doc_section_cap") is not None
                else None
            ),
            min_section_words=(
                int(filters_row["min_section_words"])
                if filters_row.get("min_section_words") is not None
                else None
            ),
            created_after=self.created_after,
            created_before=self.created_before,
            modified_after=self.modified_after,
            modified_before=self.modified_before,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None = None) -> LinkGraphSearchOptions:
        """Build validated options from a dictionary payload."""
        row = payload if isinstance(payload, dict) else {}
        schema_value = str(row.get("schema", SCHEMA_VERSION)).strip()
        if schema_value and schema_value != SCHEMA_VERSION:
            raise ValueError(
                "link_graph search options schema violation at schema: "
                f"expected '{SCHEMA_VERSION}', got '{schema_value}'"
            )
        allowed_top_level = {
            "schema",
            "match_strategy",
            "case_sensitive",
            "sort_terms",
            "filters",
            "created_after",
            "created_before",
            "modified_after",
            "modified_before",
        }
        unknown_top_level = sorted(set(row.keys()) - allowed_top_level)
        if unknown_top_level:
            raise ValueError(
                "link_graph search options schema violation at <root>: "
                f"unknown fields: {', '.join(unknown_top_level)}"
            )
        match_strategy = str(row.get("match_strategy", "fts")).strip().lower()

        raw_sort_terms = row.get("sort_terms")
        sort_terms: list[dict[str, str]] = []
        if isinstance(raw_sort_terms, list):
            sort_terms = [
                {
                    "field": str((term or {}).get("field", "score")).strip().lower(),
                    "order": str((term or {}).get("order", "desc")).strip().lower(),
                }
                for term in raw_sort_terms
                if isinstance(term, dict)
            ]

        raw_filters = row.get("filters")
        filters_row = raw_filters if isinstance(raw_filters, dict) else {}
        allowed_filter_keys = {
            "include_paths",
            "exclude_paths",
            "tags",
            "link_to",
            "linked_by",
            "related",
            "mentions_of",
            "mentioned_by_notes",
            "orphan",
            "tagless",
            "missing_backlink",
            "scope",
            "max_heading_level",
            "max_tree_hops",
            "collapse_to_doc",
            "edge_types",
            "per_doc_section_cap",
            "min_section_words",
        }
        unknown_filter_keys = sorted(set(filters_row.keys()) - allowed_filter_keys)
        if unknown_filter_keys:
            raise ValueError(
                "link_graph search options schema violation at filters: "
                f"unknown fields: {', '.join(unknown_filter_keys)}"
            )

        include_paths = _clean_string_list(filters_row.get("include_paths") or [])
        exclude_paths = _clean_string_list(filters_row.get("exclude_paths") or [])

        tags_row_raw = filters_row.get("tags") if isinstance(filters_row.get("tags"), dict) else {}
        tags_row = cast("dict[str, Any]", tags_row_raw)
        allowed_tag_keys = {"all", "any", "not"}
        unknown_tag_keys = sorted(set(tags_row.keys()) - allowed_tag_keys)
        if unknown_tag_keys:
            raise ValueError(
                "link_graph search options schema violation at filters.tags: "
                f"unknown fields: {', '.join(unknown_tag_keys)}"
            )
        tags = LinkGraphTagFilter(
            all=_clean_string_list(tags_row.get("all") or []),
            any=_clean_string_list(tags_row.get("any") or []),
            not_tags=_clean_string_list(tags_row.get("not") or []),
        )

        link_to_row_raw = (
            filters_row.get("link_to") if isinstance(filters_row.get("link_to"), dict) else {}
        )
        link_to_row = cast("dict[str, Any]", link_to_row_raw)
        allowed_link_filter_keys = {"seeds", "negate", "recursive", "max_distance"}
        unknown_link_to_keys = sorted(set(link_to_row.keys()) - allowed_link_filter_keys)
        if unknown_link_to_keys:
            raise ValueError(
                "link_graph search options schema violation at filters.link_to: "
                f"unknown fields: {', '.join(unknown_link_to_keys)}"
            )
        linked_by_row_raw = (
            filters_row.get("linked_by") if isinstance(filters_row.get("linked_by"), dict) else {}
        )
        linked_by_row = cast("dict[str, Any]", linked_by_row_raw)
        unknown_linked_by_keys = sorted(set(linked_by_row.keys()) - allowed_link_filter_keys)
        if unknown_linked_by_keys:
            raise ValueError(
                "link_graph search options schema violation at filters.linked_by: "
                f"unknown fields: {', '.join(unknown_linked_by_keys)}"
            )
        related_row_raw = (
            filters_row.get("related") if isinstance(filters_row.get("related"), dict) else {}
        )
        related_row = cast("dict[str, Any]", related_row_raw)
        allowed_related_keys = {"seeds", "max_distance", "ppr"}
        unknown_related_keys = sorted(set(related_row.keys()) - allowed_related_keys)
        if unknown_related_keys:
            raise ValueError(
                "link_graph search options schema violation at filters.related: "
                f"unknown fields: {', '.join(unknown_related_keys)}"
            )
        related_ppr_row_raw = (
            related_row.get("ppr") if isinstance(related_row.get("ppr"), dict) else {}
        )
        related_ppr_row = cast("dict[str, Any]", related_ppr_row_raw)
        allowed_related_ppr_keys = {"alpha", "max_iter", "tol", "subgraph_mode"}
        unknown_related_ppr_keys = sorted(set(related_ppr_row.keys()) - allowed_related_ppr_keys)
        if unknown_related_ppr_keys:
            raise ValueError(
                "link_graph search options schema violation at filters.related.ppr: "
                f"unknown fields: {', '.join(unknown_related_ppr_keys)}"
            )

        created_after = int(row["created_after"]) if row.get("created_after") is not None else None
        created_before = (
            int(row["created_before"]) if row.get("created_before") is not None else None
        )
        modified_after = (
            int(row["modified_after"]) if row.get("modified_after") is not None else None
        )
        modified_before = (
            int(row["modified_before"]) if row.get("modified_before") is not None else None
        )
        record = build_options_record(
            match_strategy=cast("LinkGraphMatchStrategy", match_strategy),
            case_sensitive=bool(row.get("case_sensitive", False)),
            sort_terms=sort_terms,
            include_paths=include_paths,
            exclude_paths=exclude_paths,
            tags_all=tags.all,
            tags_any=tags.any,
            tags_not=tags.not_tags,
            link_to=_clean_string_list(link_to_row.get("seeds") or []),
            link_to_negate=bool(link_to_row.get("negate", False)),
            link_to_recursive=bool(link_to_row.get("recursive", False)),
            link_to_max_distance=(
                int(link_to_row["max_distance"])
                if link_to_row.get("max_distance") is not None
                else None
            ),
            linked_by=_clean_string_list(linked_by_row.get("seeds") or []),
            linked_by_negate=bool(linked_by_row.get("negate", False)),
            linked_by_recursive=bool(linked_by_row.get("recursive", False)),
            linked_by_max_distance=(
                int(linked_by_row["max_distance"])
                if linked_by_row.get("max_distance") is not None
                else None
            ),
            related=_clean_string_list(related_row.get("seeds") or []),
            max_distance=(
                int(related_row["max_distance"])
                if related_row.get("max_distance") is not None
                else None
            ),
            related_ppr=cast("dict[str, Any] | None", related_ppr_row or None),
            mentions_of=_clean_string_list(filters_row.get("mentions_of") or []),
            mentioned_by_notes=_clean_string_list(filters_row.get("mentioned_by_notes") or []),
            orphan=bool(filters_row.get("orphan", False)),
            tagless=bool(filters_row.get("tagless", False)),
            missing_backlink=bool(filters_row.get("missing_backlink", False)),
            scope=(
                cast("LinkGraphScope", str(filters_row["scope"]).strip().lower())
                if filters_row.get("scope") is not None
                else None
            ),
            max_heading_level=(
                int(filters_row["max_heading_level"])
                if filters_row.get("max_heading_level") is not None
                else None
            ),
            max_tree_hops=(
                int(filters_row["max_tree_hops"])
                if filters_row.get("max_tree_hops") is not None
                else None
            ),
            collapse_to_doc=(
                bool(filters_row["collapse_to_doc"]) if "collapse_to_doc" in filters_row else None
            ),
            edge_types=cast(
                "list[LinkGraphEdgeType]",
                _clean_string_list(filters_row.get("edge_types") or []),
            ),
            per_doc_section_cap=(
                int(filters_row["per_doc_section_cap"])
                if filters_row.get("per_doc_section_cap") is not None
                else None
            ),
            min_section_words=(
                int(filters_row["min_section_words"])
                if filters_row.get("min_section_words") is not None
                else None
            ),
            created_after=created_after,
            created_before=created_before,
            modified_after=modified_after,
            modified_before=modified_before,
        )
        normalized_filters = cast("dict[str, Any]", record.get("filters") or {})
        normalized_tags = cast(
            "dict[str, Any]",
            normalized_filters.get("tags")
            if isinstance(normalized_filters.get("tags"), dict)
            else {},
        )
        normalized_link_to = cast(
            "dict[str, Any]",
            normalized_filters.get("link_to")
            if isinstance(normalized_filters.get("link_to"), dict)
            else {},
        )
        normalized_linked_by = cast(
            "dict[str, Any]",
            normalized_filters.get("linked_by")
            if isinstance(normalized_filters.get("linked_by"), dict)
            else {},
        )
        normalized_related = cast(
            "dict[str, Any]",
            normalized_filters.get("related")
            if isinstance(normalized_filters.get("related"), dict)
            else {},
        )
        normalized_related_ppr = cast(
            "dict[str, Any]",
            normalized_related.get("ppr")
            if isinstance(normalized_related.get("ppr"), dict)
            else {},
        )
        normalized_sort_terms_raw = cast("list[dict[str, Any]]", record.get("sort_terms") or [])
        normalized_sort_terms = [
            LinkGraphSortTerm(
                field=cast("LinkGraphSortField", str(term.get("field", "score")).strip().lower()),
                order=cast("LinkGraphSortOrder", str(term.get("order", "desc")).strip().lower()),
            )
            for term in normalized_sort_terms_raw
        ]
        if not normalized_sort_terms:
            normalized_sort_terms = [LinkGraphSortTerm()]
        return cls(
            match_strategy=cast("LinkGraphMatchStrategy", record["match_strategy"]),
            case_sensitive=bool(record["case_sensitive"]),
            sort_terms=normalized_sort_terms,
            filters=LinkGraphSearchFilters(
                include_paths=_clean_string_list(normalized_filters.get("include_paths") or []),
                exclude_paths=_clean_string_list(normalized_filters.get("exclude_paths") or []),
                tags=LinkGraphTagFilter(
                    all=_clean_string_list(normalized_tags.get("all") or []),
                    any=_clean_string_list(normalized_tags.get("any") or []),
                    not_tags=_clean_string_list(normalized_tags.get("not") or []),
                ),
                link_to=LinkGraphLinkFilter(
                    seeds=_clean_string_list(normalized_link_to.get("seeds") or []),
                    negate=bool(normalized_link_to.get("negate", False)),
                    recursive=bool(normalized_link_to.get("recursive", False)),
                    max_distance=(
                        int(normalized_link_to["max_distance"])
                        if normalized_link_to.get("max_distance") is not None
                        else None
                    ),
                ),
                linked_by=LinkGraphLinkFilter(
                    seeds=_clean_string_list(normalized_linked_by.get("seeds") or []),
                    negate=bool(normalized_linked_by.get("negate", False)),
                    recursive=bool(normalized_linked_by.get("recursive", False)),
                    max_distance=(
                        int(normalized_linked_by["max_distance"])
                        if normalized_linked_by.get("max_distance") is not None
                        else None
                    ),
                ),
                related=LinkGraphRelatedFilter(
                    seeds=_clean_string_list(normalized_related.get("seeds") or []),
                    max_distance=(
                        int(normalized_related["max_distance"])
                        if normalized_related.get("max_distance") is not None
                        else None
                    ),
                    ppr=(
                        LinkGraphRelatedPprOptions(
                            alpha=(
                                float(normalized_related_ppr["alpha"])
                                if normalized_related_ppr.get("alpha") is not None
                                else None
                            ),
                            max_iter=(
                                int(normalized_related_ppr["max_iter"])
                                if normalized_related_ppr.get("max_iter") is not None
                                else None
                            ),
                            tol=(
                                float(normalized_related_ppr["tol"])
                                if normalized_related_ppr.get("tol") is not None
                                else None
                            ),
                            subgraph_mode=(
                                cast(
                                    "LinkGraphPprSubgraphMode",
                                    str(normalized_related_ppr["subgraph_mode"]).strip().lower(),
                                )
                                if normalized_related_ppr.get("subgraph_mode") is not None
                                else None
                            ),
                        )
                        if normalized_related_ppr
                        else None
                    ),
                ),
                mentions_of=_clean_string_list(normalized_filters.get("mentions_of") or []),
                mentioned_by_notes=_clean_string_list(
                    normalized_filters.get("mentioned_by_notes") or []
                ),
                orphan=bool(normalized_filters.get("orphan", False)),
                tagless=bool(normalized_filters.get("tagless", False)),
                missing_backlink=bool(normalized_filters.get("missing_backlink", False)),
                scope=(
                    cast("LinkGraphScope", str(normalized_filters["scope"]).strip().lower())
                    if normalized_filters.get("scope") is not None
                    else None
                ),
                max_heading_level=(
                    int(normalized_filters["max_heading_level"])
                    if normalized_filters.get("max_heading_level") is not None
                    else None
                ),
                max_tree_hops=(
                    int(normalized_filters["max_tree_hops"])
                    if normalized_filters.get("max_tree_hops") is not None
                    else None
                ),
                collapse_to_doc=(
                    bool(normalized_filters["collapse_to_doc"])
                    if "collapse_to_doc" in normalized_filters
                    else None
                ),
                edge_types=cast(
                    "list[LinkGraphEdgeType]",
                    _clean_string_list(filters_row.get("edge_types") or []),
                ),
                per_doc_section_cap=(
                    int(normalized_filters["per_doc_section_cap"])
                    if normalized_filters.get("per_doc_section_cap") is not None
                    else None
                ),
                min_section_words=(
                    int(normalized_filters["min_section_words"])
                    if normalized_filters.get("min_section_words") is not None
                    else None
                ),
            ),
            created_after=(
                int(record["created_after"]) if record.get("created_after") is not None else None
            ),
            created_before=(
                int(record["created_before"]) if record.get("created_before") is not None else None
            ),
            modified_after=(
                int(record["modified_after"]) if record.get("modified_after") is not None else None
            ),
            modified_before=(
                int(record["modified_before"])
                if record.get("modified_before") is not None
                else None
            ),
        )


@dataclass
class LinkGraphNote:
    """Canonical note record used across link-graph adapters and enhancers."""

    path: str
    abs_path: str
    title: str
    raw_content: str | None = None
    tags: list[str] = field(default_factory=list)
    link: str = ""
    lead: str | None = None
    filename_stem: str | None = None
    created: str | None = None
    modified: str | None = None
    word_count: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LinkGraphNote:
        """Build from CLI/backend JSON row."""
        return cls(
            path=str(data.get("path", "")),
            abs_path=str(data.get("absPath", "")),
            title=str(data.get("title", "Untitled")),
            raw_content=data.get("body"),
            tags=list(data.get("tags", []) or []),
            link=str(data.get("link", "")),
            lead=data.get("lead"),
            filename_stem=data.get("filenameStem"),
            created=data.get("created"),
            modified=data.get("modified"),
            word_count=data.get("wordCount"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the canonical backend-compatible dictionary shape."""
        return {
            "path": self.path,
            "absPath": self.abs_path,
            "title": self.title,
            "body": self.raw_content,
            "tags": self.tags,
            "link": self.link,
            "lead": self.lead,
            "filenameStem": self.filename_stem,
            "created": self.created,
            "modified": self.modified,
            "wordCount": self.word_count,
        }


__all__ = [
    "LinkGraphDirection",
    "LinkGraphEdgeType",
    "LinkGraphHit",
    "LinkGraphLinkFilter",
    "LinkGraphMatchStrategy",
    "LinkGraphMetadata",
    "LinkGraphNeighbor",
    "LinkGraphNote",
    "LinkGraphPprSubgraphMode",
    "LinkGraphRelatedFilter",
    "LinkGraphRelatedPprOptions",
    "LinkGraphScope",
    "LinkGraphSearchFilters",
    "LinkGraphSearchOptions",
    "LinkGraphSortField",
    "LinkGraphSortOrder",
    "LinkGraphSortTerm",
    "LinkGraphTagFilter",
]
