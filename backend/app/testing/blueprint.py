"""Формирование плана теста (blueprint): доли компетенций, трек языка/фреймворка.

* Для категоризации кандидата — по специализации и стеку из опроса.
* Для вакансии — базовый план специализации, смещённый в сторону компетенций, которые покрывают
  требуемые навыки вакансии (например, PostgreSQL + Kafka → больше заданий по БД и архитектуре).
"""
from __future__ import annotations

import random

from app.catalog.data import COMPETENCIES, GRADES, SPECIALIZATIONS
from app.catalog.skills import infer_framework, infer_lang, skill_competency
from app.testing.bank import REGISTRY, GenCtx, render


def base_blueprint(spec: str) -> dict[str, float]:
    return dict(SPECIALIZATIONS[spec]["blueprint"])


def vacancy_blueprint(spec: str, skills: list[str], lang: str | None = None, framework: str | None = None) -> dict:
    lang = lang or infer_lang(skills, spec)
    framework = framework or infer_framework(skills) or ("react" if spec == "frontend" else None)
    bp = base_blueprint(spec)
    hits: dict[str, list[str]] = {}
    for s in skills:
        sc = skill_competency(s, spec, lang, framework)
        if sc and sc[0] in bp:
            hits.setdefault(sc[0], []).append(s)
    total = max(1, sum(len(v) for v in hits.values()))
    boosted = {c: w * (1.0 + 1.2 * len(hits.get(c, [])) / total) for c, w in bp.items()}
    norm = sum(boosted.values())
    weights = {c: round(w / norm, 3) for c, w in boosted.items()}
    return {
        "spec": spec,
        "lang": lang,
        "framework": framework,
        "weights": weights,
        "coverage": {c: hits.get(c, []) for c in bp},
        "uncovered_skills": [s for s in skills if not any(s in v for v in hits.values())],
    }


def blueprint_view(bp: dict[str, float], ctx: GenCtx, spec: str, grade: str | None = None, n_items: int = 14) -> list[dict]:
    """Человекочитаемое описание плана: сколько заданий и каких семейств приходится на компетенцию."""
    out = []
    for comp, w in sorted(bp.items(), key=lambda kv: -kv[1]):
        pool = [t for t in REGISTRY.values() if t.competency == comp and t.applicable(spec, ctx)]
        out.append({
            "competency": comp,
            "name": COMPETENCIES[comp]["name"],
            "weight": w,
            "expected_items": round(w * n_items, 1),
            "families": len(pool),
            "levels": sorted({t.level for t in pool}),
            "examples": [t.title for t in sorted(pool, key=lambda t: abs(t.b - GRADES.get(grade or "middle")["center"]))[:3]],
        })
    return out


def sample_items(spec: str, ctx: GenCtx, bp: dict[str, float], grade: str, n: int = 4, seed: int | None = None) -> list[dict]:
    """Пример заданий для превью (без ключей ответов): по одному из самых весомых компетенций около уровня грейда."""
    rng = random.Random(seed)
    center = GRADES[grade]["center"]
    out = []
    for comp, _ in sorted(bp.items(), key=lambda kv: -kv[1])[:n]:
        pool = [t for t in REGISTRY.values() if t.competency == comp and t.applicable(spec, ctx)]
        if not pool:
            continue
        pool.sort(key=lambda t: abs(t.b - center))
        t = rng.choice(pool[:3])
        payload, _, h = render(t, rng.randint(1, 10**9), ctx)
        out.append({"template_id": t.id, "title": t.title, "competency": COMPETENCIES[comp]["name"], "level": t.level,
                    "payload": payload, "variant_hash": h})
    return out
