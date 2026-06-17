"""Judge and select the best persona plan."""

from __future__ import annotations

import json
import logging
from typing import Any

from .config import load_swarm_council_config
from .llm import LLMCaller, extract_json_object
from .schemas import JudgeDecision, PersonaPlan

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Sen tarafsız bir görev-dağılımı değerlendiricisisin. Sana 4 farklı plan verilecek.
Görevin: input'a EN UYGUN olanı seçmek. Kendi görüşünü dayatma, sadece verilen
kriterlere göre objektif kıyasla. Çıktın SADECE JSON olsun.

Kriterler: asıl talebe uygunluk, alt-agent çakışma riski, bağımlılık zincirinin
mantıklılığı/deadlock riski, kapsamın tam karşılanması.
"""


def _fallback_decision(plans: list[PersonaPlan], reason: str) -> JudgeDecision:
    selected = max(plans, key=lambda plan: plan.confidence)
    rejected = {plan.persona: "Fallback en yüksek persona confidence değerini seçti." for plan in plans if plan.persona != selected.persona}
    return JudgeDecision(
        selected_persona=selected.persona,
        reasoning=reason,
        rejected_reasons=rejected,
        merge_suggestions=None,
        confidence=selected.confidence,
        used_fallback=True,
    )


def choose_plan(task_input: str, plans: list[PersonaPlan], llm: LLMCaller) -> JudgeDecision:
    cfg = load_swarm_council_config()
    payload = [plan.to_dict() for plan in plans]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""Orijinal görev: {task_input}
Planlar: {json.dumps(payload, ensure_ascii=False, indent=2)}

Çıktı şeması:
{{
  "selected_persona": "<hangi persona seçildi>",
  "reasoning": "<neden bu plan seçildi, 2-3 cümle>",
  "rejected_reasons": {{"persona_x": "..."}},
  "merge_suggestions": "<varsa>",
  "confidence": 0.0
}}"""},
    ]
    try:
        decision = JudgeDecision.from_dict(extract_json_object(llm(messages)))
    except Exception as exc:
        logger.warning("Swarm judge failed; using persona-confidence fallback: %s", exc)
        return _fallback_decision(plans, f"Judge response could not be parsed: {exc}")
    known = {plan.persona for plan in plans}
    if decision.selected_persona not in known:
        return _fallback_decision(plans, "Judge selected an unknown persona; fell back to highest persona confidence.")
    if decision.confidence < cfg.judge_confidence_threshold:
        return _fallback_decision(plans, "Judge confidence was below threshold; fell back to highest persona confidence.")
    return decision


def selected_plan(plans: list[PersonaPlan], decision: JudgeDecision) -> PersonaPlan:
    for plan in plans:
        if plan.persona == decision.selected_persona:
            return plan
    return max(plans, key=lambda plan: plan.confidence)
