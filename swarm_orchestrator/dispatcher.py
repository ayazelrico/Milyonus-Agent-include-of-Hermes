"""Dispatch a selected swarm plan through Hermes' existing delegation tool."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from .schemas import PersonaPlan, SubtaskExecutionResult, SubtaskPlan

logger = logging.getLogger(__name__)


def _dependency_ready(subtask: SubtaskPlan, completed: set[str]) -> bool:
    return all(dep in completed for dep in subtask.dependencies)


def _group_ready(plan: PersonaPlan, completed: set[str], dispatched: set[str]) -> list[SubtaskPlan]:
    ready = [item for item in plan.task_breakdown if item.subtask not in dispatched and _dependency_ready(item, completed)]
    return sorted(ready, key=lambda item: item.priority)


def _parse_delegate_results(raw: str, tasks: list[SubtaskPlan]) -> list[SubtaskExecutionResult]:
    try:
        data = json.loads(raw)
    except Exception:
        return [SubtaskExecutionResult(item.subtask, item.assigned_agent, raw, success=False) for item in tasks]
    if not isinstance(data, dict):
        return [SubtaskExecutionResult(item.subtask, item.assigned_agent, str(data), success=False) for item in tasks]
    results = data.get("results") if isinstance(data.get("results"), list) else []
    mapped: list[SubtaskExecutionResult] = []
    for idx, item in enumerate(tasks):
        result = results[idx] if idx < len(results) and isinstance(results[idx], dict) else {}
        output = result.get("final_response") or result.get("result") or result.get("output") or json.dumps(result, ensure_ascii=False)
        mapped.append(SubtaskExecutionResult(item.subtask, item.assigned_agent, str(output), success="error" not in result))
    return mapped


def dispatch_plan(plan: PersonaPlan, parent_agent: Any, *, context: str = "") -> list[SubtaskExecutionResult]:
    """Execute subtasks respecting dependency layers.

    Independent ready subtasks are sent as one `delegate_task` batch so Hermes'
    existing subagent executor owns child creation, limits, tool restrictions,
    and result aggregation.
    """
    from tools.delegate_tool import delegate_task

    completed: set[str] = set()
    dispatched: set[str] = set()
    outputs: list[SubtaskExecutionResult] = []
    by_name = {item.subtask: item for item in plan.task_breakdown}
    dependents: dict[str, list[str]] = defaultdict(list)
    for item in plan.task_breakdown:
        for dep in item.dependencies:
            dependents[dep].append(item.subtask)
            if dep not in by_name:
                raise ValueError(f"Unknown dependency {dep!r} for subtask {item.subtask!r}")

    while len(completed) < len(plan.task_breakdown):
        ready = _group_ready(plan, completed, dispatched)
        if not ready:
            blocked = [item.subtask for item in plan.task_breakdown if item.subtask not in completed]
            raise ValueError(f"Plan has unsatisfied or cyclic dependencies: {blocked}")
        batch = [
            {
                "goal": item.subtask,
                "context": f"Persona plan: {plan.persona}\nAssigned agent label: {item.assigned_agent}\n{context}".strip(),
                "role": "leaf",
            }
            for item in ready
        ]
        logger.info("Dispatching %d swarm subtask(s) from persona=%s", len(ready), plan.persona)
        raw = delegate_task(tasks=batch, parent_agent=parent_agent)
        layer_results = _parse_delegate_results(raw, ready)
        outputs.extend(layer_results)
        for item in ready:
            dispatched.add(item.subtask)
            completed.add(item.subtask)
    return outputs
