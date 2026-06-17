"""Top-level opt-in council → judge → dispatch → review chain."""

from __future__ import annotations

import json
from typing import Any

from .checkpoint_monitor import check_results
from .council import generate_persona_plans_sync
from .dispatcher import dispatch_plan
from .final_review import review_with_revisions
from .judge import choose_plan, selected_plan
from .llm import make_agent_llm_caller


def default_agent_roster() -> list[dict[str, Any]]:
    """Describe available Hermes delegation workers without creating new tools."""
    try:
        from tools.delegate_tool import _SUBAGENT_TOOLSETS  # type: ignore[attr-defined]
    except Exception:
        toolsets: list[str] = []
    else:
        toolsets = list(_SUBAGENT_TOOLSETS)
    return [
        {
            "name": "hermes-subagent",
            "capabilities": "Fresh child AIAgent with isolated context; selectable toolsets via existing delegate_task.",
            "available_toolsets": toolsets,
        }
    ]


def run_swarm_council(
    agent: Any,
    task_input: str,
    *,
    agent_roster: Any | None = None,
    constraints: Any | None = None,
) -> dict[str, Any]:
    llm = make_agent_llm_caller(agent)
    roster = agent_roster if agent_roster is not None else default_agent_roster()
    plans = generate_persona_plans_sync(task_input, roster, constraints or {}, llm)
    decision = choose_plan(task_input, plans, llm)
    plan = selected_plan(plans, decision)
    results = dispatch_plan(plan, agent, context=f"Original user task: {task_input}")
    checkpoints = check_results(results, plan.task_breakdown, roster, llm)
    review, revised_results = review_with_revisions(task_input, plan, agent, results, checkpoints, llm)
    return {
        "final_response": json.dumps(
            {
                "selected_persona": decision.selected_persona,
                "judge_reasoning": decision.reasoning,
                "merge_suggestions": decision.merge_suggestions,
                "review": review.__dict__,
                "subtask_results": [result.__dict__ for result in revised_results],
            },
            ensure_ascii=False,
            indent=2,
        ),
        "swarm_council": {
            "plans": [plan_item.to_dict() for plan_item in plans],
            "decision": decision.__dict__,
            "selected_plan": plan.to_dict(),
            "checkpoints": [check.__dict__ for check in checkpoints],
            "review": review.__dict__,
        },
    }
