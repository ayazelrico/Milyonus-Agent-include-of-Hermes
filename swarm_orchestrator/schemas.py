"""Shared data structures for the swarm task-distribution council."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass
class SubtaskPlan:
    subtask: str
    assigned_agent: str
    priority: int
    dependencies: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubtaskPlan":
        return cls(
            subtask=str(data.get("subtask", "")).strip(),
            assigned_agent=str(data.get("assigned_agent", "")).strip(),
            priority=int(data.get("priority", 0) or 0),
            dependencies=[str(dep).strip() for dep in data.get("dependencies", []) if str(dep).strip()],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PersonaPlan:
    persona: str
    plan_summary: str
    task_breakdown: list[SubtaskPlan]
    risk_notes: str
    confidence: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonaPlan":
        return cls(
            persona=str(data.get("persona", "")).strip(),
            plan_summary=str(data.get("plan_summary", "")).strip(),
            task_breakdown=[SubtaskPlan.from_dict(item) for item in data.get("task_breakdown", [])],
            risk_notes=str(data.get("risk_notes", "")).strip(),
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.0) or 0.0))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "task_breakdown": [item.to_dict() for item in self.task_breakdown]}


@dataclass
class JudgeDecision:
    selected_persona: str
    reasoning: str
    rejected_reasons: dict[str, str]
    merge_suggestions: str | None
    confidence: float
    used_fallback: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JudgeDecision":
        suggestions = data.get("merge_suggestions")
        return cls(
            selected_persona=str(data.get("selected_persona", "")).strip(),
            reasoning=str(data.get("reasoning", "")).strip(),
            rejected_reasons={str(k): str(v) for k, v in (data.get("rejected_reasons") or {}).items()},
            merge_suggestions=str(suggestions).strip() if suggestions is not None else None,
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.0) or 0.0))),
            used_fallback=bool(data.get("used_fallback", False)),
        )


@dataclass
class CheckpointResult:
    subtask: str
    agent_checked: str
    verdict: Literal["ok", "flagged"]
    note: str


@dataclass
class SubtaskExecutionResult:
    subtask: str
    assigned_agent: str
    output: str
    success: bool = True


@dataclass
class FinalReviewResult:
    status: Literal["approved", "needs_revision"]
    issues: list[str]
    summary: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FinalReviewResult":
        status = str(data.get("status", "needs_revision")).strip()
        if status not in {"approved", "needs_revision"}:
            status = "needs_revision"
        return cls(
            status=status,  # type: ignore[arg-type]
            issues=[str(issue) for issue in data.get("issues", [])],
            summary=str(data.get("summary", "")).strip(),
        )
