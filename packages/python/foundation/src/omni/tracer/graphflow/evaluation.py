"""Graphflow evaluation and XML helper utilities."""

from __future__ import annotations

import re

from omni.tracer.xml import escape_xml, extract_attr, extract_tag


def _escape_xml(text: str) -> str:
    return escape_xml(text)


def _extract_tag(xml: str, tag: str) -> str:
    return extract_tag(xml, tag)


def _parse_llm_payload(raw: str, default_thought: str) -> tuple[str, str]:
    """Parse LLM output with optional <thought>/<content> tags."""
    thought = _extract_tag(raw, "thought")
    content = _extract_tag(raw, "content")
    if content:
        return content, thought or default_thought
    # Fallback: if model returned plain text, treat whole output as content.
    return raw.strip(), thought or default_thought


def _jaccard_similarity(a: str, b: str) -> float:
    a_tokens = {t for t in re.findall(r"[a-z0-9]+", a.lower()) if len(t) > 2}
    b_tokens = {t for t in re.findall(r"[a-z0-9]+", b.lower()) if len(t) > 2}
    if not a_tokens and not b_tokens:
        return 1.0
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def _max_similarity(text: str, xml_labels: list[str]) -> float:
    if not text or not xml_labels:
        return 0.0
    prev_critiques = [
        _extract_tag(x, "issue") or _extract_tag(x, "new_critique") for x in xml_labels
    ]
    sims = [_jaccard_similarity(text, p) for p in prev_critiques if p]
    return max(sims) if sims else 0.0


def _summarize_critiques(xml_labels: list[str]) -> str:
    if not xml_labels:
        return ""
    lines: list[str] = []
    for idx, label in enumerate(xml_labels, start=1):
        critique = _extract_tag(label, "issue") or _extract_tag(label, "new_critique")
        if critique:
            lines.append(f"{idx}. {critique}")
    return "\n".join(lines)


def _build_critique_status_report(xml_labels: list[str], analysis: str) -> str:
    if not xml_labels:
        return "none"
    latest_quality_xml = ""
    # This function now prefers evaluator XML dimensions over plain keyword checks.
    # The caller can inject the latest quality snapshot by embedding it in analysis context.
    quality_match = re.search(r"<quality_evaluation[\s\S]*?</quality_evaluation>", analysis)
    if quality_match:
        latest_quality_xml = quality_match.group(0)

    def dim_score(name: str) -> float:
        if not latest_quality_xml:
            return -1.0
        m = re.search(rf'<dimension name="{name}" score="([0-9]+\.[0-9]+)"', latest_quality_xml)
        return float(m.group(1)) if m else -1.0

    evidence_score = dim_score("evidence")
    specificity_score = dim_score("specificity")
    tradeoffs_score = dim_score("tradeoffs")
    completeness_score = dim_score("completeness")

    report: list[str] = []
    for idx, label in enumerate(xml_labels, start=1):
        critique = _extract_tag(label, "issue") or _extract_tag(label, "new_critique")
        if not critique:
            continue
        duplicate_tag = _extract_tag(label, "duplicate").lower()
        is_duplicate = duplicate_tag == "true"
        if is_duplicate:
            report.append(f"- #{idx}: {critique} -> STATUS: REDUNDANT")
            continue
        c_lower = critique.lower()
        status = "PENDING"
        # Prefer evaluator-dimension mapping if available.
        if "example" in c_lower or "typescript" in c_lower or "rust" in c_lower:
            if specificity_score >= 0.60:
                status = "ADDRESSED"
            elif _contains_specific_examples(analysis):
                status = "ADDRESSED"
        elif "quantify" in c_lower or "productivity" in c_lower or "impact" in c_lower:
            if evidence_score >= 0.60:
                status = "ADDRESSED"
            elif _contains_evidence_signal(analysis):
                status = "ADDRESSED"
        elif (
            "trade-off" in c_lower
            or "tradeoff" in c_lower
            or "overhead" in c_lower
            or "cost" in c_lower
        ):
            if tradeoffs_score >= 0.60:
                status = "ADDRESSED"
            elif _contains_tradeoff_signal(analysis):
                status = "ADDRESSED"
        else:
            if completeness_score >= 0.60:
                status = "ADDRESSED"
        report.append(f"- #{idx}: {critique} -> STATUS: {status}")
    return "\n".join(report) if report else "none"


def _build_evaluation_xml(
    iteration: int,
    critique: str,
    issue_type: str,
    issue_severity: str,
    is_meta: bool,
    is_duplicate: bool,
    similarity: float,
    quality_score: float,
    quality_delta: float,
    decision_hint: str,
) -> str:
    return (
        f'<evaluation iteration="{iteration}">\n'
        f"  <meta_commentary>{str(is_meta).lower()}</meta_commentary>\n"
        f'  <duplicate similarity_to_prev_max="{similarity:.2f}">{str(is_duplicate).lower()}</duplicate>\n'
        f'  <quality score="{quality_score:.2f}" delta="{quality_delta:+.2f}"/>\n'
        f'  <issue type="{issue_type}" severity="{issue_severity}">{_escape_xml(critique)}</issue>\n'
        f"  <new_critique>{_escape_xml(critique)}</new_critique>\n"
        f"  <decision_hint>{decision_hint}</decision_hint>\n"
        f"</evaluation>"
    )


def _build_quality_xml(
    iteration: int,
    evidence: float,
    completeness: float,
    specificity: float,
    tradeoffs: float,
    overall: float,
    delta: float,
) -> str:
    return (
        f'<quality_evaluation iteration="{iteration}">\n'
        f"  <dimensions>\n"
        f'    <dimension name="evidence" score="{evidence:.2f}"/>\n'
        f'    <dimension name="completeness" score="{completeness:.2f}"/>\n'
        f'    <dimension name="specificity" score="{specificity:.2f}"/>\n'
        f'    <dimension name="tradeoffs" score="{tradeoffs:.2f}"/>\n'
        f"  </dimensions>\n"
        f'  <overall score="{overall:.2f}" delta="{delta:+.2f}"/>\n'
        f"</quality_evaluation>"
    )


def _contains_specific_examples(text: str) -> bool:
    anchors = [
        "for example",
        "for instance",
        "python",
        "rust",
        "typescript",
        "interface",
        "ownership",
        "generic",
    ]
    lower = text.lower()
    return any(a in lower for a in anchors)


def _contains_tradeoff_signal(text: str) -> bool:
    anchors = [
        "trade-off",
        "tradeoff",
        "cost",
        "overhead",
        "strict",
        "annotation burden",
        "complexity",
    ]
    lower = text.lower()
    return any(a in lower for a in anchors)


def _contains_evidence_signal(text: str) -> bool:
    anchors = [
        "bug",
        "defect",
        "%",
        "metric",
        "measured",
        "productivity",
        "reduction",
        "before runtime",
    ]
    lower = text.lower()
    return any(a in lower for a in anchors)


def _extract_attr(xml: str, tag: str, attr: str) -> str:
    return extract_attr(xml, tag, attr)


def _classify_issue(critique: str) -> tuple[str, str]:
    c = critique.lower()
    if any(k in c for k in ["example", "specific", "typescript", "rust", "python"]):
        return "specificity", "high"
    if any(k in c for k in ["evidence", "quantify", "metric", "productivity", "impact"]):
        return "evidence", "high"
    if any(k in c for k in ["trade-off", "tradeoff", "cost", "overhead"]):
        return "tradeoff", "medium"
    return "completeness", "medium"


def _novelty_ratio(previous_text: str, current_text: str) -> float:
    prev_tokens = [t for t in re.findall(r"[a-z0-9]+", previous_text.lower()) if len(t) > 2]
    curr_tokens = [t for t in re.findall(r"[a-z0-9]+", current_text.lower()) if len(t) > 2]
    if not curr_tokens:
        return 0.0
    if not prev_tokens:
        return 1.0
    prev_set = set(prev_tokens)
    novel = [t for t in curr_tokens if t not in prev_set]
    return len(novel) / len(curr_tokens)


def _parse_critique_coverage(status_report: str) -> float:
    lines = [line.strip() for line in status_report.splitlines() if line.strip().startswith("- #")]
    if not lines:
        return 1.0
    addressed = sum(1 for line in lines if "STATUS: ADDRESSED" in line)
    return addressed / len(lines)


def _extract_analysis_slot(text: str, slot: str) -> str:
    return _extract_tag(text, slot)


def _ensure_analysis_contract(text: str, previous_analysis: str = "") -> str:
    thesis = _extract_analysis_slot(text, "thesis")
    evidence = _extract_analysis_slot(text, "evidence")
    examples = _extract_analysis_slot(text, "examples")
    tradeoffs = _extract_analysis_slot(text, "tradeoffs")
    changes = _extract_analysis_slot(text, "changes_from_prev")

    if thesis and evidence and examples and tradeoffs and changes:
        return text

    normalized = " ".join(text.split())
    if not thesis:
        thesis = normalized
    if not evidence:
        evidence = (
            "Compile-time checks reduce runtime type defects and improve review confidence in interface contracts."
            if _contains_evidence_signal(normalized)
            else "Evidence is limited and should include measurable bug-rate or delivery metrics."
        )
    if not examples:
        examples = (
            "TypeScript catches interface mismatches; Rust ownership prevents use-after-free; Python typing improves editor diagnostics."
            if _contains_specific_examples(normalized)
            else "No concrete language-level examples were provided."
        )
    if not tradeoffs:
        tradeoffs = (
            "Trade-offs include annotation overhead, stricter refactor requirements, and migration cost."
            if _contains_tradeoff_signal(normalized)
            else "Trade-offs were not explicitly discussed."
        )
    if not changes:
        if previous_analysis:
            novelty = _novelty_ratio(previous_analysis, normalized)
            changes = f"Estimated novelty versus previous analysis: {novelty:.2f}."
        else:
            changes = "Initial analysis iteration."

    return (
        "<analysis_contract>\n"
        f"  <thesis>{_escape_xml(thesis)}</thesis>\n"
        f"  <evidence>{_escape_xml(evidence)}</evidence>\n"
        f"  <examples>{_escape_xml(examples)}</examples>\n"
        f"  <tradeoffs>{_escape_xml(tradeoffs)}</tradeoffs>\n"
        f"  <changes_from_prev>{_escape_xml(changes)}</changes_from_prev>\n"
        "</analysis_contract>"
    )


def _synthesize_novel_critique(topic: str, previous_critiques: list[str]) -> str:
    """Generate a deterministic non-duplicate critique when LLM repeats itself."""
    normalized = " ".join(c.lower() for c in previous_critiques)
    candidates = [
        f"The analysis for {topic} lacks quantified impact data (for example defect-reduction or delivery-speed metrics).",
        f"The analysis for {topic} does not cover trade-offs such as migration cost, onboarding overhead, and stricter refactor constraints.",
        f"The analysis for {topic} misses ecosystem/tooling contrasts across languages and concrete decision criteria.",
        f"The analysis for {topic} omits limitations and edge cases where static typing provides limited value.",
    ]
    for c in candidates:
        if _jaccard_similarity(c, normalized) < 0.45:
            return c
    return candidates[-1]


__all__ = [
    "_escape_xml",
    "_extract_tag",
    "_parse_llm_payload",
    "_jaccard_similarity",
    "_max_similarity",
    "_summarize_critiques",
    "_build_critique_status_report",
    "_build_evaluation_xml",
    "_build_quality_xml",
    "_contains_specific_examples",
    "_contains_tradeoff_signal",
    "_contains_evidence_signal",
    "_extract_attr",
    "_classify_issue",
    "_novelty_ratio",
    "_parse_critique_coverage",
    "_extract_analysis_slot",
    "_ensure_analysis_contract",
    "_synthesize_novel_critique",
]
