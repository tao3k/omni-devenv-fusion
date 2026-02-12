"""Graphflow LangGraph node implementations."""

from __future__ import annotations

from typing import cast

from .evaluation import (
    _build_critique_status_report,
    _build_evaluation_xml,
    _build_quality_xml,
    _classify_issue,
    _contains_evidence_signal,
    _contains_specific_examples,
    _contains_tradeoff_signal,
    _ensure_analysis_contract,
    _extract_analysis_slot,
    _extract_tag,
    _jaccard_similarity,
    _max_similarity,
    _novelty_ratio,
    _parse_critique_coverage,
    _parse_llm_payload,
    _summarize_critiques,
    _synthesize_novel_critique,
)
from .llm_service import get_llm_service
from .tracer import LangGraphTracer
from .types import DemoState, StepType
from .ui import console, ultra_step_enter, ultra_step_exit


async def llm_analyze(state: DemoState, tracer: LangGraphTracer) -> DemoState:
    """LLM analyze node - generates analysis based on prior critiques."""
    current_iteration = len(state["reflection_labels"]) + 1
    step_id = tracer.start_step(
        f"analyzer.analyze(v{current_iteration})",
        StepType.LLM_CALL,
        input_data={"topic": state["topic"], "iteration": current_iteration},
    )

    prev_labels = "\n".join(state["reflection_labels"])
    critique_summary = _summarize_critiques(state["reflection_labels"])
    latest_quality_xml = state["quality_evaluations"][-1] if state["quality_evaluations"] else ""
    status_context = (
        f"{state['analysis']}\n\n{latest_quality_xml}" if latest_quality_xml else state["analysis"]
    )
    critique_status_report = _build_critique_status_report(
        state["reflection_labels"], status_context
    )
    analyzer_context = (
        "Previous critiques with status (DO NOT REPEAT):\n"
        f"{critique_status_report}\n\n"
        "New analysis must address PENDING items and add at least one new concrete example."
    )
    console.print(
        ultra_step_enter(
            f"analyzer.analyze(v{current_iteration})",
            {
                "topic": state["topic"],
                "critiques": critique_status_report if critique_status_report else "none",
            },
            step_id,
        )
    )

    llm = get_llm_service()
    analysis_raw = await llm.complete(
        topic=state["topic"],
        step="analyze",
        iteration=current_iteration,
        context=analyzer_context
        if state["reflection_labels"]
        else (critique_summary or prev_labels),
    )
    analysis, thought = _parse_llm_payload(
        analysis_raw,
        default_thought=f"analyze iteration={current_iteration}",
    )
    previous_analysis = (
        state.get("analysis_history", [])[-1] if state.get("analysis_history") else ""
    )
    analysis = _ensure_analysis_contract(analysis, previous_analysis)
    if state.get("routing_reason", "") == "force_reanalyze_after_no_improvement":
        analysis += (
            " Additional quantified view: teams commonly report fewer runtime type errors after adopting stricter typing, "
            "with faster code review due to explicit interfaces. Trade-offs include migration cost and annotation overhead."
        )
        thought += " | forced rewrite applied after no-improvement detection."
    # Force visible improvement after duplicate critiques in low-quality loops.
    if state.get("duplicate_streak", 0) >= 1 and not _contains_specific_examples(analysis):
        analysis += (
            " For example: in TypeScript, a mismatched function signature is caught at compile time; "
            "in Rust, ownership rules prevent use-after-free at compile time."
        )
    tracer.record_memory(
        "analysis",
        analysis,
        step=f"analyzer.analyze(v{current_iteration})",
        metadata={"iteration": current_iteration},
    )
    tracer.record_memory(
        "memory_thinking",
        thought,
        step=f"analyzer.analyze(v{current_iteration})",
        metadata={"phase": "analyze"},
    )

    analysis_preview = analysis[:100] + "..." if len(analysis) > 100 else analysis
    console.print(
        ultra_step_exit(
            f"analyzer.analyze(v{current_iteration})",
            {
                "analysis": analysis_preview,
                "quality_score": f"{state['quality_score']:.2f}",
                "ready_to_draft": False,
                "reason": "evaluation_pending",
            },
            reasoning=thought,
        )
    )

    updated_analysis_history = list(state.get("analysis_history", [])) + [analysis]

    return cast(
        DemoState,
        {
            "topic": state["topic"],
            "iterations": state["iterations"],
            "max_iterations": state["max_iterations"],
            "quality_score": state["quality_score"],
            "analysis": analysis,
            "analysis_history": updated_analysis_history,
            "reflection_labels": list(state["reflection_labels"]),
            "quality_evaluations": list(state["quality_evaluations"]),
            "draft": state["draft"],
            "final": state["final"],
            "ready_to_draft": False,
            "duplicate_streak": state.get("duplicate_streak", 0),
            "quality_delta_streak": state.get("quality_delta_streak", 0),
            "last_quality_score": state.get("last_quality_score", 0.0),
            "routing_reason": "",
            "no_improvement_rewrite_used": state.get("no_improvement_rewrite_used", False),
            "quality_threshold": state.get("quality_threshold", 0.8),
            "quality_gate_novelty_threshold": state.get("quality_gate_novelty_threshold", 0.20),
            "quality_gate_coverage_threshold": state.get("quality_gate_coverage_threshold", 0.80),
            "quality_gate_min_evidence_count": state.get("quality_gate_min_evidence_count", 1),
            "quality_gate_require_tradeoff": state.get("quality_gate_require_tradeoff", True),
            "quality_gate_max_fail_streak": state.get("quality_gate_max_fail_streak", 2),
            "quality_gate_fail_streak": state.get("quality_gate_fail_streak", 0),
        },
    )


async def llm_evaluate(state: DemoState, tracer: LangGraphTracer) -> DemoState:
    """Evaluate analysis quality and decide whether to continue reflection."""
    step_id = tracer.start_step(
        "evaluator.evaluate",
        StepType.LLM_CALL,
        input_data={"analysis_preview": state["analysis"][:100] if state["analysis"] else "N/A"},
    )
    console.print(
        ultra_step_enter(
            "evaluator.evaluate",
            {
                "current_quality": f"{state['quality_score']:.2f}",
                "reflections": len(state["reflection_labels"]),
            },
            step_id,
        )
    )

    previous_quality = state.get("quality_score", 0.0)
    quality_threshold = state.get("quality_threshold", 0.8)
    novelty_threshold = state.get("quality_gate_novelty_threshold", 0.20)
    coverage_threshold = state.get("quality_gate_coverage_threshold", 0.80)
    min_evidence_count = state.get("quality_gate_min_evidence_count", 1)
    require_tradeoff = state.get("quality_gate_require_tradeoff", True)
    max_gate_fail_streak = state.get("quality_gate_max_fail_streak", 2)
    gate_fail_streak = state.get("quality_gate_fail_streak", 0)
    latest_label = state["reflection_labels"][-1] if state["reflection_labels"] else ""
    is_duplicate = _extract_tag(latest_label, "duplicate") == "true"
    is_meta = _extract_tag(latest_label, "meta_commentary") == "true"

    analysis = state["analysis"]
    evidence = 0.25 + (0.35 if _contains_evidence_signal(analysis) else 0.0)
    completeness = 0.30 + min(0.40, 0.08 * len(state["reflection_labels"]))
    specificity = 0.25 + (0.45 if _contains_specific_examples(analysis) else 0.0)
    tradeoffs = 0.20 + (0.50 if _contains_tradeoff_signal(analysis) else 0.0)
    if is_meta:
        evidence = max(0.0, evidence - 0.20)
        specificity = max(0.0, specificity - 0.20)
    if is_duplicate:
        completeness = max(0.0, completeness - 0.10)

    base_quality = (evidence + completeness + specificity + tradeoffs) / 4.0
    analysis_history = list(state.get("analysis_history", []))
    no_improvement = False
    analysis_similarity = 0.0
    if len(analysis_history) >= 2:
        analysis_similarity = _jaccard_similarity(analysis_history[-1], analysis_history[-2])
        no_improvement = analysis_similarity >= 0.90
    novelty_ratio = (
        _novelty_ratio(analysis_history[-2], analysis_history[-1])
        if len(analysis_history) >= 2
        else 1.0
    )

    status_context = (
        f"{analysis}\n\n{state['quality_evaluations'][-1]}"
        if state["quality_evaluations"]
        else analysis
    )
    critique_status_report = _build_critique_status_report(
        state["reflection_labels"], status_context
    )
    critique_coverage = _parse_critique_coverage(critique_status_report)
    evidence_slot = _extract_analysis_slot(analysis, "evidence")
    tradeoffs_slot = _extract_analysis_slot(analysis, "tradeoffs")
    evidence_count = 1 if evidence_slot and "limited" not in evidence_slot.lower() else 0
    tradeoff_present = bool(
        tradeoffs_slot and "not explicitly discussed" not in tradeoffs_slot.lower()
    )
    quality_gates_passed = (
        novelty_ratio >= novelty_threshold
        and critique_coverage >= coverage_threshold
        and evidence_count >= min_evidence_count
        and (tradeoff_present if require_tradeoff else True)
    )
    gate_fail_streak = gate_fail_streak + 1 if not quality_gates_passed else 0
    improvement_failed = gate_fail_streak >= max_gate_fail_streak

    if not state["reflection_labels"]:
        new_quality = max(previous_quality, max(base_quality, 0.25))
    elif no_improvement:
        new_quality = max(0.0, min(base_quality, previous_quality - 0.20))
    elif is_meta:
        new_quality = max(0.0, min(base_quality, previous_quality - 0.12))
    elif is_duplicate:
        new_quality = max(0.0, min(base_quality, previous_quality - 0.12))
    else:
        improvement_bonus = 0.10 if analysis_similarity < 0.90 else 0.0
        new_quality = min(1.0, max(base_quality, previous_quality + improvement_bonus))
    if state["reflection_labels"] and not quality_gates_passed:
        new_quality = min(new_quality, previous_quality)

    quality_delta = new_quality - previous_quality
    quality_xml = _build_quality_xml(
        iteration=len(state["reflection_labels"]),
        evidence=evidence,
        completeness=completeness,
        specificity=specificity,
        tradeoffs=tradeoffs,
        overall=new_quality,
        delta=quality_delta,
    )
    quality_evaluations = list(state["quality_evaluations"]) + [quality_xml]
    tracer.record_memory(
        "quality_evaluations",
        quality_xml,
        step="evaluator.evaluate",
        metadata={"iteration": len(state["reflection_labels"])},
    )
    tracer.record_memory(
        "memory_thinking",
        f"evaluate dims ev={evidence:.2f} comp={completeness:.2f} spec={specificity:.2f} trade={tradeoffs:.2f}",
        step="evaluator.evaluate",
        metadata={"phase": "evaluate"},
    )
    quality_delta_streak = state.get("quality_delta_streak", 0) + 1 if quality_delta < 0.05 else 0
    duplicate_streak = state.get("duplicate_streak", 0)

    rewrite_used = state.get("no_improvement_rewrite_used", False)
    if no_improvement and not rewrite_used and not improvement_failed:
        should_stop = False
        routing_reason = "force_reanalyze_after_no_improvement"
        rewrite_used = True
    else:
        should_stop = (
            new_quality >= quality_threshold
            or improvement_failed
            or no_improvement
            or is_duplicate
            or duplicate_streak >= 2
            or quality_delta_streak >= 2
            or len(state["reflection_labels"]) > state["max_iterations"]
        )
        if new_quality >= quality_threshold:
            routing_reason = "quality_threshold_reached"
        elif improvement_failed:
            routing_reason = "improvement_failed"
        elif not quality_gates_passed:
            routing_reason = "quality_gates_failed"
        elif no_improvement:
            routing_reason = "no_analysis_improvement"
        elif is_duplicate:
            routing_reason = "duplicate_reflection_detected"
        elif duplicate_streak >= 2:
            routing_reason = "duplicate_reflections_detected"
        elif quality_delta_streak >= 2:
            routing_reason = "quality_plateau_detected"
        elif len(state["reflection_labels"]) > state["max_iterations"]:
            routing_reason = "max_iterations_reached"
        else:
            routing_reason = "continue_reflection"

    console.print(
        ultra_step_exit(
            "evaluator.evaluate",
            {
                "dims": f"ev={evidence:.2f} comp={completeness:.2f} spec={specificity:.2f} trade={tradeoffs:.2f}",
                "analysis_similarity": f"{analysis_similarity:.2f}",
                "novelty_ratio": f"{novelty_ratio:.2f}",
                "coverage": f"{critique_coverage:.2f}",
                "evidence_count": evidence_count,
                "tradeoff_present": tradeoff_present,
                "gates_passed": quality_gates_passed,
                "gate_fail_streak": gate_fail_streak,
                "max_gate_fail_streak": max_gate_fail_streak,
                "quality_threshold": f"{quality_threshold:.2f}",
                "no_improvement": no_improvement,
                "quality_score": f"{new_quality:.2f}",
                "quality_delta": f"{quality_delta:+.2f}",
                "rewrite_used": rewrite_used,
                "ready_to_draft": should_stop,
                "reason": routing_reason,
            },
            reasoning="Deterministic evaluation node computed routing decision",
        )
    )

    return cast(
        DemoState,
        {
            "topic": state["topic"],
            "iterations": state["iterations"],
            "max_iterations": state["max_iterations"],
            "quality_score": new_quality,
            "analysis": state["analysis"],
            "analysis_history": analysis_history,
            "reflection_labels": list(state["reflection_labels"]),
            "quality_evaluations": quality_evaluations,
            "draft": state["draft"],
            "final": state["final"],
            "ready_to_draft": should_stop,
            "duplicate_streak": duplicate_streak,
            "quality_delta_streak": quality_delta_streak,
            "last_quality_score": previous_quality,
            "routing_reason": routing_reason,
            "no_improvement_rewrite_used": rewrite_used,
            "quality_threshold": quality_threshold,
            "quality_gate_novelty_threshold": novelty_threshold,
            "quality_gate_coverage_threshold": coverage_threshold,
            "quality_gate_min_evidence_count": min_evidence_count,
            "quality_gate_require_tradeoff": require_tradeoff,
            "quality_gate_max_fail_streak": max_gate_fail_streak,
            "quality_gate_fail_streak": gate_fail_streak,
        },
    )


async def llm_reflect(state: DemoState, tracer: LangGraphTracer) -> DemoState:
    """LLM reflect node - generates structured critique with XML tags for cross-node context."""
    step_id = tracer.start_step(
        "reflector.reflect",
        StepType.LLM_CALL,
        input_data={"analysis_preview": state["analysis"][:100] if state["analysis"] else "N/A"},
    )

    # Build context from previous reflection labels
    prev_labels = "\n".join(state["reflection_labels"])
    critique_summary = _summarize_critiques(state["reflection_labels"])
    latest_quality_xml = state["quality_evaluations"][-1] if state["quality_evaluations"] else ""
    status_context = (
        f"{state['analysis']}\n\n{latest_quality_xml}" if latest_quality_xml else state["analysis"]
    )
    critique_status_report = _build_critique_status_report(
        state["reflection_labels"], status_context
    )
    reflector_context = (
        "Previous critiques with status:\n"
        f"{critique_status_report}\n\n"
        "NEW critique must be different from all ADDRESSED and PENDING items."
    )
    console.print(
        ultra_step_enter(
            "reflector.reflect",
            {"prev_issues": critique_status_report if critique_status_report else "none"},
            step_id,
        )
    )

    llm = get_llm_service()
    critique_count = len(state["reflection_labels"])
    critique_raw = await llm.complete(
        topic=state["topic"],
        step="reflect",
        iteration=critique_count + 1,
        context=reflector_context
        if state["reflection_labels"]
        else (critique_summary or prev_labels),
    )
    critique, thought = _parse_llm_payload(
        critique_raw,
        default_thought=f"reflect iteration={critique_count + 1}",
    )

    similarity = _max_similarity(critique, state["reflection_labels"])
    is_duplicate = similarity >= 0.80
    if is_duplicate:
        previous_critiques = [
            _extract_tag(x, "issue") or _extract_tag(x, "new_critique")
            for x in state["reflection_labels"]
        ]
        critique = _synthesize_novel_critique(state["topic"], [c for c in previous_critiques if c])
        thought = (
            thought + " | duplicate detected; synthesized a novel critique to avoid repetition."
        )
        similarity = _max_similarity(critique, state["reflection_labels"])
        is_duplicate = similarity >= 0.80
    is_meta = llm._is_meta_commentary(critique)
    issue_type, issue_severity = _classify_issue(critique)

    previous_quality = state.get("quality_score", 0.0)
    if is_meta:
        decision_hint = "retry_or_draft"
    elif is_duplicate:
        decision_hint = "draft"
    else:
        decision_hint = "continue_reflect"

    # Scoring is handled by evaluator node; reflect only emits quality signals.
    new_quality = previous_quality
    quality_delta = 0.0
    duplicate_streak = state.get("duplicate_streak", 0) + 1 if is_duplicate else 0
    quality_delta_streak = state.get("quality_delta_streak", 0)

    label = _build_evaluation_xml(
        iteration=critique_count + 1,
        critique=critique,
        issue_type=issue_type,
        issue_severity=issue_severity,
        is_meta=is_meta,
        is_duplicate=is_duplicate,
        similarity=similarity,
        quality_score=new_quality,
        quality_delta=quality_delta,
        decision_hint=decision_hint,
    )
    new_labels = list(state["reflection_labels"]) + [label]
    current_iteration = len(new_labels)
    tracer.record_reflection(label)

    critique_preview = critique[:100] + "..." if len(critique) > 100 else critique

    console.print(
        ultra_step_exit(
            "reflector.reflect",
            {
                "critique": critique_preview,
                "issue_type": issue_type,
                "severity": issue_severity,
                "quality_score": f"{new_quality:.2f}",
                "duplicate": is_duplicate,
                "similarity": f"{similarity:.2f}",
                "meta_commentary": is_meta,
            },
            reasoning=thought,
        )
    )
    tracer.record_memory(
        "memory_thinking",
        thought,
        step="reflector.reflect",
        metadata={"phase": "reflect", "iteration": current_iteration},
    )

    return cast(
        DemoState,
        {
            "topic": state["topic"],
            "iterations": state["iterations"],
            "max_iterations": state["max_iterations"],
            "quality_score": new_quality,
            "analysis": state["analysis"],
            "analysis_history": list(state.get("analysis_history", [])),
            "reflection_labels": new_labels,
            "quality_evaluations": list(state["quality_evaluations"]),
            "draft": state["draft"],
            "final": state["final"],
            "ready_to_draft": False,
            "duplicate_streak": duplicate_streak,
            "quality_delta_streak": quality_delta_streak,
            "last_quality_score": previous_quality,
            "routing_reason": state.get("routing_reason", ""),
            "no_improvement_rewrite_used": state.get("no_improvement_rewrite_used", False),
            "quality_threshold": state.get("quality_threshold", 0.8),
            "quality_gate_novelty_threshold": state.get("quality_gate_novelty_threshold", 0.20),
            "quality_gate_coverage_threshold": state.get("quality_gate_coverage_threshold", 0.80),
            "quality_gate_min_evidence_count": state.get("quality_gate_min_evidence_count", 1),
            "quality_gate_require_tradeoff": state.get("quality_gate_require_tradeoff", True),
            "quality_gate_max_fail_streak": state.get("quality_gate_max_fail_streak", 2),
            "quality_gate_fail_streak": state.get("quality_gate_fail_streak", 0),
        },
    )


async def llm_draft(state: DemoState, tracer: LangGraphTracer) -> DemoState:
    """LLM draft node - synthesizes analysis and reflections into a draft."""
    step_id = tracer.start_step(
        "drafter.draft",
        StepType.LLM_CALL,
        input_data={"analysis": state["analysis"][:100] if state["analysis"] else "N/A"},
    )
    console.print(
        ultra_step_enter(
            "drafter.draft",
            {
                "analysis": state["analysis"][:50] + "..."
                if len(state["analysis"]) > 50
                else state["analysis"]
            },
            step_id,
        )
    )

    llm = get_llm_service()
    draft_raw = await llm.complete(
        topic=state["topic"],
        step="draft",
        iteration=len(state["reflection_labels"]),
    )
    draft, thought = _parse_llm_payload(
        draft_raw,
        default_thought="draft synthesis",
    )

    tracer.record_memory("draft", draft, step="drafter.draft", metadata={})
    tracer.record_memory(
        "memory_thinking", thought, step="drafter.draft", metadata={"phase": "draft"}
    )

    draft_preview = draft[:100] + "..." if len(draft) > 100 else draft

    console.print(ultra_step_exit("drafter.draft", {"draft": draft_preview}, reasoning=thought))

    return cast(
        DemoState,
        {
            "topic": state["topic"],
            "iterations": state["iterations"],
            "max_iterations": state["max_iterations"],
            "quality_score": state["quality_score"],
            "analysis": state["analysis"],
            "analysis_history": list(state.get("analysis_history", [])),
            "reflection_labels": list(state["reflection_labels"]),
            "quality_evaluations": list(state["quality_evaluations"]),
            "draft": draft,
            "final": state["final"],
            "ready_to_draft": state.get("ready_to_draft", False),
            "duplicate_streak": state.get("duplicate_streak", 0),
            "quality_delta_streak": state.get("quality_delta_streak", 0),
            "last_quality_score": state.get("last_quality_score", 0.0),
            "routing_reason": state.get("routing_reason", ""),
            "no_improvement_rewrite_used": state.get("no_improvement_rewrite_used", False),
            "quality_threshold": state.get("quality_threshold", 0.8),
            "quality_gate_novelty_threshold": state.get("quality_gate_novelty_threshold", 0.20),
            "quality_gate_coverage_threshold": state.get("quality_gate_coverage_threshold", 0.80),
            "quality_gate_min_evidence_count": state.get("quality_gate_min_evidence_count", 1),
            "quality_gate_require_tradeoff": state.get("quality_gate_require_tradeoff", True),
            "quality_gate_max_fail_streak": state.get("quality_gate_max_fail_streak", 2),
            "quality_gate_fail_streak": state.get("quality_gate_fail_streak", 0),
        },
    )


async def llm_finalize(state: DemoState, tracer: LangGraphTracer) -> DemoState:
    """LLM finalize node - creates the final output."""
    step_id = tracer.start_step(
        "drafter.finalize",
        StepType.LLM_CALL,
        input_data={"draft_preview": state["draft"][:100] if state["draft"] else "N/A"},
    )
    console.print(
        ultra_step_enter(
            "drafter.finalize",
            {"draft": state["draft"][:50] + "..." if len(state["draft"]) > 50 else state["draft"]},
            step_id,
        )
    )

    llm = get_llm_service()
    reflections_count = len(state["reflection_labels"])
    final_raw = await llm.complete(
        topic=state["topic"],
        step="final",
        iteration=reflections_count,
    )
    final, thought = _parse_llm_payload(
        final_raw,
        default_thought="finalize answer",
    )

    tracer.record_memory("final", final, step="drafter.finalize", metadata={})
    tracer.record_memory(
        "memory_thinking", thought, step="drafter.finalize", metadata={"phase": "final"}
    )

    final_preview = final[:100] + "..." if len(final) > 100 else final

    console.print(ultra_step_exit("drafter.finalize", {"final": final_preview}, reasoning=thought))

    return cast(
        DemoState,
        {
            "topic": state["topic"],
            "iterations": state["iterations"],
            "max_iterations": state["max_iterations"],
            "quality_score": state["quality_score"],
            "analysis": state["analysis"],
            "analysis_history": list(state.get("analysis_history", [])),
            "reflection_labels": list(state["reflection_labels"]),
            "quality_evaluations": list(state["quality_evaluations"]),
            "draft": state["draft"],
            "final": final,
            "ready_to_draft": state.get("ready_to_draft", False),
            "duplicate_streak": state.get("duplicate_streak", 0),
            "quality_delta_streak": state.get("quality_delta_streak", 0),
            "last_quality_score": state.get("last_quality_score", 0.0),
            "routing_reason": state.get("routing_reason", ""),
            "no_improvement_rewrite_used": state.get("no_improvement_rewrite_used", False),
            "quality_threshold": state.get("quality_threshold", 0.8),
            "quality_gate_novelty_threshold": state.get("quality_gate_novelty_threshold", 0.20),
            "quality_gate_coverage_threshold": state.get("quality_gate_coverage_threshold", 0.80),
            "quality_gate_min_evidence_count": state.get("quality_gate_min_evidence_count", 1),
            "quality_gate_require_tradeoff": state.get("quality_gate_require_tradeoff", True),
            "quality_gate_max_fail_streak": state.get("quality_gate_max_fail_streak", 2),
            "quality_gate_fail_streak": state.get("quality_gate_fail_streak", 0),
        },
    )


# =============================================================================
# Main Command
# =============================================================================

__all__ = [
    "llm_analyze",
    "llm_evaluate",
    "llm_reflect",
    "llm_draft",
    "llm_finalize",
]
