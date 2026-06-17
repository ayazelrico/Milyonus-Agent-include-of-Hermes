"""Run the four task-distribution personas concurrently."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from .config import PERSONA_FILES, load_swarm_council_config
from .llm import LLMCaller, extract_json_object
from .schemas import PersonaPlan


def _persona_prompt(persona: str, persona_md: str, task_input: str, agent_roster: Any, constraints: Any) -> list[dict[str, str]]:
    roster_json = json.dumps(agent_roster, ensure_ascii=False, indent=2, default=str)
    constraints_json = json.dumps(constraints or {}, ensure_ascii=False, indent=2, default=str)
    return [
        {"role": "system", "content": persona_md},
        {"role": "user", "content": f"""Görev: {task_input}
Mevcut alt-agent'lar ve yetenekleri: {roster_json}
Kısıtlar: {constraints_json}

Bu göreve göre bir görev dağılım planı üret. Çıktın SADECE şu JSON şemasına uysun:
{{
  "persona": "{persona}",
  "plan_summary": "<1-2 cümlelik özet>",
  "task_breakdown": [
    {{"subtask": "...", "assigned_agent": "...", "priority": 1, "dependencies": []}}
  ],
  "risk_notes": "<bu plandaki olası riskler>",
  "confidence": 0.0
}}"""},
    ]


async def _run_persona(persona: str, path: Path, llm: LLMCaller, task_input: str, agent_roster: Any, constraints: Any) -> PersonaPlan:
    cfg = load_swarm_council_config()
    persona_md = path.read_text(encoding="utf-8")
    messages = _persona_prompt(persona, persona_md, task_input, agent_roster, constraints)
    model_override = (cfg.persona_model_overrides or {}).get(persona)
    response = await asyncio.to_thread(llm, messages, model=model_override)
    data = extract_json_object(response)
    data.setdefault("persona", persona)
    return PersonaPlan.from_dict(data)


async def generate_persona_plans(
    task_input: str,
    agent_roster: Any,
    constraints: Any,
    llm: LLMCaller,
) -> list[PersonaPlan]:
    tasks = [
        _run_persona(persona, path, llm, task_input, agent_roster, constraints)
        for persona, path in PERSONA_FILES.items()
    ]
    return list(await asyncio.gather(*tasks))


def generate_persona_plans_sync(task_input: str, agent_roster: Any, constraints: Any, llm: LLMCaller) -> list[PersonaPlan]:
    return asyncio.run(generate_persona_plans(task_input, agent_roster, constraints, llm))
