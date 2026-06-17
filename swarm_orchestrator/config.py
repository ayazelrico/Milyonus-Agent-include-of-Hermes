"""Configuration defaults for the swarm council orchestrator.

User-facing behavior should be configured in ``~/.hermes/config.yaml`` under
``swarm_council``; this module deliberately does not introduce new public env
variables for behavioral settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - yaml is optional in minimal tests
    yaml = None

from hermes_constants import get_hermes_home

PACKAGE_DIR = Path(__file__).resolve().parent
PERSONA_DIR = PACKAGE_DIR / "personas"

JUDGE_CONFIDENCE_THRESHOLD = 0.5
MAX_REVISION_CYCLES = 2
COMPLEXITY_THRESHOLD = 0.0
CHECKPOINT_TRIGGERS = ("subtask_complete", "external_write")

PERSONA_FILES = {
    "analytical": PERSONA_DIR / "persona_analytical.md",
    "logical": PERSONA_DIR / "persona_logical.md",
    "emotional": PERSONA_DIR / "persona_emotional.md",
    "ruthless": PERSONA_DIR / "persona_ruthless.md",
}

PERSONA_MODEL_OVERRIDES: dict[str, str | None] = {name: None for name in PERSONA_FILES}


@dataclass(frozen=True)
class SwarmCouncilConfig:
    enabled: bool = False
    judge_confidence_threshold: float = JUDGE_CONFIDENCE_THRESHOLD
    max_revision_cycles: int = MAX_REVISION_CYCLES
    complexity_threshold: float = COMPLEXITY_THRESHOLD
    checkpoint_triggers: tuple[str, ...] = CHECKPOINT_TRIGGERS
    persona_model_overrides: dict[str, str | None] | None = None


def _load_user_config() -> dict[str, Any]:
    if yaml is None:
        return {}
    path = get_hermes_home() / "config.yaml"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def load_swarm_council_config() -> SwarmCouncilConfig:
    section = _load_user_config().get("swarm_council", {})
    if not isinstance(section, dict):
        section = {}
    overrides = section.get("persona_model_overrides")
    if not isinstance(overrides, dict):
        overrides = PERSONA_MODEL_OVERRIDES
    triggers = section.get("checkpoint_triggers", CHECKPOINT_TRIGGERS)
    if not isinstance(triggers, (list, tuple)):
        triggers = CHECKPOINT_TRIGGERS
    return SwarmCouncilConfig(
        enabled=bool(section.get("enabled", False)),
        judge_confidence_threshold=float(section.get("judge_confidence_threshold", JUDGE_CONFIDENCE_THRESHOLD)),
        max_revision_cycles=int(section.get("max_revision_cycles", MAX_REVISION_CYCLES)),
        complexity_threshold=float(section.get("complexity_threshold", COMPLEXITY_THRESHOLD)),
        checkpoint_triggers=tuple(str(item) for item in triggers),
        persona_model_overrides={str(k): (str(v) if v else None) for k, v in overrides.items()},
    )
