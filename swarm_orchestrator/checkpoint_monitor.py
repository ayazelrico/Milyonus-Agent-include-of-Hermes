"""Lightweight peer-checks for completed swarm subtasks."""

from __future__ import annotations

import json
from typing import Any

from .llm import LLMCaller, extract_json_object
from .schemas import CheckpointResult, SubtaskExecutionResult, SubtaskPlan


def _pick_peer(agent_roster: Any, assigned_agent: str) -> str:
    if isinstance(agent_roster, dict):
        candidates = [str(name) for name in agent_roster.keys() if str(name) != assigned_agent]
    elif isinstance(agent_roster, list):
        candidates = [str(item.get("name", item)) if isinstance(item, dict) else str(item) for item in agent_roster]
        candidates = [name for name in candidates if name != assigned_agent]
    else:
        candidates = []
    return candidates[0] if candidates else "peer-reviewer"


def check_subtask(result: SubtaskExecutionResult, original_plan: SubtaskPlan, agent_roster: Any, llm: LLMCaller) -> CheckpointResult:
    peer = _pick_peer(agent_roster, result.assigned_agent)
    messages = [
        {"role": "system", "content": "Kısa ve hafif bir akran doğrulayıcısın. Sadece JSON döndür."},
        {"role": "user", "content": f"""Alt-görev: {original_plan.subtask}
Görevi yapan agent: {result.assigned_agent}
Kontrol eden peer: {peer}
Çıktı: {result.output}

Bu çıktı, istenen alt-göreve uygun mu? JSON döndür:
{{"verdict": "ok" veya "flagged", "note": "tek satır gerekçe"}}"""},
    ]
    data = extract_json_object(llm(messages))
    verdict = str(data.get("verdict", "flagged")).strip().lower()
    if verdict not in {"ok", "flagged"}:
        verdict = "flagged"
    return CheckpointResult(
        subtask=result.subtask,
        agent_checked=peer,
        verdict=verdict,  # type: ignore[arg-type]
        note=str(data.get("note", "")).strip(),
    )


def check_results(results: list[SubtaskExecutionResult], plan: list[SubtaskPlan], agent_roster: Any, llm: LLMCaller) -> list[CheckpointResult]:
    by_name = {item.subtask: item for item in plan}
    checks: list[CheckpointResult] = []
    for result in results:
        original = by_name.get(result.subtask)
        if original is None:
            continue
        checks.append(check_subtask(result, original, agent_roster, llm))
    return checks
