"""Final review and bounded revision loop for swarm results."""

from __future__ import annotations

import json
from typing import Any

from .config import load_swarm_council_config
from .dispatcher import dispatch_plan
from .llm import LLMCaller, extract_json_object
from .schemas import CheckpointResult, FinalReviewResult, PersonaPlan, SubtaskExecutionResult


def review_final_result(task_input: str, results: list[SubtaskExecutionResult], checkpoints: list[CheckpointResult], llm: LLMCaller) -> FinalReviewResult:
    payload = {
        "original_task": task_input,
        "subtask_outputs": [result.__dict__ for result in results],
        "checkpoint_flags": [check.__dict__ for check in checkpoints if check.verdict == "flagged"],
    }
    messages = [
        {"role": "system", "content": "Kapsamlı görev-sonu review agent'ısın. Sadece JSON döndür."},
        {"role": "user", "content": f"""{json.dumps(payload, ensure_ascii=False, indent=2)}

Bu görev bütün olarak orijinal talebi karşılıyor mu? Çakışan/tekrar eden işler var mı? Flag'lenen noktalar gerçek problem mi?
Çıktı: {{"status": "approved" veya "needs_revision", "issues": ["..."], "summary": "..."}}"""},
    ]
    return FinalReviewResult.from_dict(extract_json_object(llm(messages)))


def review_with_revisions(
    task_input: str,
    plan: PersonaPlan,
    parent_agent: Any,
    results: list[SubtaskExecutionResult],
    checkpoints: list[CheckpointResult],
    llm: LLMCaller,
) -> tuple[FinalReviewResult, list[SubtaskExecutionResult]]:
    cfg = load_swarm_council_config()
    current_results = list(results)
    review = review_final_result(task_input, current_results, checkpoints, llm)
    cycles = 0
    while review.status == "needs_revision" and cycles < cfg.max_revision_cycles:
        issue_text = "\n".join(review.issues)
        flagged_names = {check.subtask for check in checkpoints if check.verdict == "flagged"}
        revision_subtasks = [item for item in plan.task_breakdown if item.subtask in flagged_names or item.subtask in issue_text]
        if not revision_subtasks:
            break
        revision_plan = PersonaPlan(
            persona=plan.persona,
            plan_summary=f"Revision cycle {cycles + 1}: {review.summary}",
            task_breakdown=revision_subtasks,
            risk_notes=plan.risk_notes,
            confidence=plan.confidence,
        )
        current_results.extend(dispatch_plan(revision_plan, parent_agent, context="Revision requested by final review."))
        cycles += 1
        review = review_final_result(task_input, current_results, checkpoints, llm)
    return review, current_results
