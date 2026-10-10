"""Оценка соответствия кандидата потребности работодателя с объяснением.

Двухэтапная схема:
  1. Отбор по категориям (recall): категория = специализация × грейд, присвоенные ТЕСТОМ, а не резюме.
     Целевые категории + смежные (соседний грейд, родственная специализация) с понижающим коэффициентом.
  2. Ранжирование (precision): интерпретируемая взвешенная сумма шести компонент, каждая в [0, 1]:
       L — подтверждённый уровень (θ внутри полосы грейда),
       S — покрытие навыков потребности с учётом СИЛЫ доказательства (тест > ФСП > задачи > резюме),
       F — достижения ФСП с учётом актуальности дисциплины для запроса (вес регулируется работодателем),
       A — актуальность профиля (регулярные задачи, свежесть),
       C — условия: зарплатные ожидания vs вилка, формат и город,
       D — контекст: отраслевой опыт и текстовая близость описаний.
     Каждая компонента возвращает человекочитаемые причины — это и есть «объяснимость выдачи».
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.catalog.data import (DISCIPLINE_FIT, DISCIPLINE_FIT_NAMES, DOMAINS, FSP_DISCIPLINES, GRADE_ORDER, GRADES, SPECIALIZATIONS,
                              WORK_FORMATS, discipline_fit, grade_name)
from app.catalog.skills import related, skill_competency
from app.fsp.scoring import aggregate
from app.matching.strength import activity_score, band_position

RELATED_SPECS = {
    "backend": ["devops", "qa"],
    "devops": ["backend", "infosec"],
    "ml": ["data_analyst", "backend"],
    "data_analyst": ["ml"],
    "frontend": ["mobile"],
    "mobile": ["frontend"],
    "qa": ["backend"],
    "infosec": ["devops"],
}

UNCONFIRMED_FACTOR = 0.6  # грейд не подтверждён тестом: ниже в выдаче, но не скрыт
EVIDENCE = {"test": 1.0, "fsp": 0.9, "task": 0.8, "declared": 0.5, "related": 0.3}
EVIDENCE_LABEL = {"test": "подтверждён тестом", "fsp": "подтверждён ФСП", "task": "подтверждён задачей", "declared": "заявлен в профиле",
                  "related": "есть смежный навык"}


@dataclass
class Achievement:
    event_name: str
    discipline: str
    level: str
    place: int | None
    result_title: str
    year: int
    stack: list[str] = field(default_factory=list)
    weight: float | None = None  # вклад результата без учёта актуальности: фактор результата × давность (fsp.scoring)
    prize: bool = True  # призовой/финальный результат, а не участие без результата


@dataclass
class CandView:
    id: int
    spec: str | None
    grade: str | None
    theta: float | None
    lang: str | None = None
    framework: str | None = None
    topic_scores: dict = field(default_factory=dict)
    verified_skills: list[str] = field(default_factory=list)
    declared_skills: list[str] = field(default_factory=list)
    task_skills: list[str] = field(default_factory=list)
    fsp_score: float = 0.0
    achievements: list[Achievement] = field(default_factory=list)
    salary_from: int | None = None
    salary_to: int | None = None
    work_formats: list[str] = field(default_factory=list)
    city: str | None = None
    relocation: bool = False
    domains: list[str] = field(default_factory=list)
    search_status: str = "open"
    tasks_done: int = 0
    task_score: float | None = None
    last_activity_at: datetime | None = None
    grade_confirmed: bool = True  # False — грейд заявлен в опросе, тестом не подтверждён (показывается ниже подтверждённых)
    strength: float = 0.0
    category_percentile: float | None = None
    pending_invites: int = 0
    text: str = ""


@dataclass
class NeedView:
    spec: str
    grades: list[str]
    must_skills: list[str] = field(default_factory=list)
    nice_skills: list[str] = field(default_factory=list)
    salary_from: int = 0
    salary_to: int = 0
    work_formats: list[str] = field(default_factory=list)
    city: str | None = None
    fsp_weight: float = 0.5
    domains: list[str] = field(default_factory=list)
    description: str = ""
    include_adjacent: bool = True


# Веса и множители формулы. Значения по умолчанию подобраны на ОТДЕЛЬНЫХ наборах потребностей
# (app/validation/tune_matching.py) и проверены на независимых наборах; экспертные исходные значения — EXPERT_PARAMS.
EXPERT_PARAMS = {"L": 0.30, "S": 0.30, "F_max": 0.20, "A": 0.08, "C": 0.15, "D": 0.07,
                 "salary_mult": 0.85, "format_mult": 0.85, "gate_floor": 0.5, "adjacent_mult": 0.92, "related_mult": 0.85}
_TUNED = Path(__file__).with_name("tuned_params.json")
PARAMS = {**EXPERT_PARAMS, **(json.loads(_TUNED.read_text())["params"] if _TUNED.exists() else {})}


def weights(fsp_weight: float, p: dict | None = None) -> dict[str, float]:
    p = p or PARAMS
    # вес ФСП регулирует работодатель: от 20% до 100% от F_max
    w = {"L": p["L"], "S": p["S"], "F": p["F_max"] * (0.2 + 0.8 * max(0.0, min(1.0, fsp_weight))), "A": p["A"], "C": p["C"], "D": p["D"]}
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


def combine(comps: dict[str, float], mods: dict, fsp_weight: float, p: dict | None = None) -> float:
    """Итоговая оценка 0–100 из компонент и модификаторов (одна формула для продакшена, валидации и подстройки весов)."""
    p = p or PARAMS
    w = weights(fsp_weight, p)
    total = sum(w[k] * comps[k] for k in comps)
    if mods["over_budget"]:
        total *= p["salary_mult"]  # кандидат заметно дороже бюджета
    if mods["format_mismatch"]:
        total *= p["format_mult"]
    if mods["must_cov"] is not None:
        # обязательные навыки — «гейт»: без них высокий уровень и хорошие условия не делают кандидата релевантным
        total *= p["gate_floor"] + (1 - p["gate_floor"]) * mods["must_cov"]
    if mods["relation"] == "adjacent_grade":
        total *= p["adjacent_mult"]
    elif mods["relation"] == "related_spec":
        total *= p["related_mult"]
    if not mods["grade_confirmed"]:
        total *= UNCONFIRMED_FACTOR
    return round(100 * total, 1)


# ---------------------------------------------------------------- 1. категория
def category_relation(c: CandView, n: NeedView) -> tuple[str, float] | None:
    """('target'|'adjacent_grade'|'related_spec', множитель) или None — кандидат вне подборки."""
    if not c.grade or not c.spec:
        return None
    gi = GRADE_ORDER.index(c.grade)
    need_idx = [GRADE_ORDER.index(g) for g in n.grades]
    if c.spec == n.spec:
        if c.grade in n.grades:
            return ("target", 1.0)
        if n.include_adjacent and min(abs(gi - x) for x in need_idx) == 1:
            return ("adjacent_grade", 0.75)
        return None
    if n.include_adjacent and c.spec in RELATED_SPECS.get(n.spec, []) and c.grade in n.grades:
        return ("related_spec", 0.6)
    return None


def level_component(c: CandView, n: NeedView, rel: str) -> tuple[float, list[str], list[str]]:
    pos = band_position(c.theta, c.grade)
    reasons, warns = [], []
    cat = f"{SPECIALIZATIONS[c.spec]['short']} · {grade_name(c.grade)}"
    pct = f", {int(round(c.category_percentile))}-й перцентиль в категории" if c.category_percentile is not None else ""
    if not c.grade_confirmed:
        # грейд заявлен, но не подтверждён тестом: уровень не засчитывается, кандидат показывается ниже подтверждённых
        warns.append(f"Грейд {grade_name(c.grade)} заявлен, тестом не подтверждён — показан ниже кандидатов с подтверждённым грейдом")
        return 0.0, reasons, warns
    if rel == "target":
        val = 0.55 + 0.45 * pos
        reasons.append(f"Категория {cat} подтверждена адаптивным тестом{pct}")
    elif rel == "adjacent_grade":
        gi, need_idx = GRADE_ORDER.index(c.grade), [GRADE_ORDER.index(g) for g in n.grades]
        if gi < min(need_idx):
            val = 0.2 + 0.35 * pos  # грейд ниже: чем ближе к следующему порогу, тем лучше
            warns.append(f"Смежная категория: {cat} — на ступень ниже запроса" + (", близок к повышению" if pos > 0.7 else ""))
        else:
            val = 0.5
            warns.append(f"Смежная категория: {cat} — выше запроса, возможны завышенные ожидания")
    else:
        val = 0.35 + 0.25 * pos
        warns.append(f"Смежная специализация: {cat}")
    return val, reasons, warns


# ---------------------------------------------------------------- 2. навыки
def skill_evidence(c: CandView, skill: str, need_grade: str) -> tuple[float, str]:
    """Сила доказательства навыка. Тест подтверждает навык, который кандидат заявил (или трек языка из опроса):
    сильный результат по соответствующей компетенции превращает «заявлено» в «подтверждено». Навык, который
    кандидат не заявлял, тест лишь косвенно поддерживает (смежная компетенция)."""
    best, kind = 0.0, ""
    declared = skill in c.declared_skills
    if skill in c.verified_skills and declared:
        best, kind = EVIDENCE["test"], "test"
    else:
        sc = skill_competency(skill, c.spec, c.lang, c.framework)
        if sc and sc[0] in c.topic_scores:
            ts = c.topic_scores[sc[0]]
            strong = ts.get("n", 0) >= 2 and ts.get("theta", -9) >= GRADES[need_grade]["cut"] - 0.4
            track = sc[0] in ("lang", "framework", "mobile_platform") and sc[1] >= 1.0  # язык/фреймворк из опроса
            if strong and (declared or track):
                best, kind = EVIDENCE["test"] * sc[1], "test"
            elif strong:
                best, kind = 0.35, "related"
    if best < EVIDENCE["fsp"] and any(skill in a.stack or skill in FSP_DISCIPLINES.get(a.discipline, {}).get("skills", []) for a in c.achievements):
        best, kind = EVIDENCE["fsp"], "fsp"
    if best < EVIDENCE["task"] and skill in c.task_skills:
        best, kind = EVIDENCE["task"], "task"
    if best < EVIDENCE["declared"] and declared:
        best, kind = EVIDENCE["declared"], "declared"
    if best < EVIDENCE["related"] and any(related(skill, s) > 0 for s in c.declared_skills + c.verified_skills):
        best, kind = EVIDENCE["related"], "related"
    return best, kind


def skills_component(c: CandView, n: NeedView) -> tuple[float, list[str], list[str], dict]:
    need_grade = min(n.grades, key=GRADE_ORDER.index) if n.grades else "middle"
    detail = {}
    for s in n.must_skills + n.nice_skills:
        v, k = skill_evidence(c, s, need_grade)
        detail[s] = {"value": round(v, 2), "evidence": k or "none", "must": s in n.must_skills}
    must = [detail[s]["value"] for s in n.must_skills]
    nice = [detail[s]["value"] for s in n.nice_skills]
    must_cov = sum(must) / len(must) if must else 0.7
    if nice:
        val = 0.8 * must_cov + 0.2 * (sum(nice) / len(nice))
    else:
        val = must_cov
    reasons, warns = [], []
    groups: dict[str, list[str]] = {}
    for s, d in detail.items():
        groups.setdefault(d["evidence"], []).append(s)
    if groups.get("test"):
        reasons.append("Подтверждены тестом: " + ", ".join(groups["test"]))
    if groups.get("fsp"):
        reasons.append("Подтверждены на соревнованиях ФСП: " + ", ".join(groups["fsp"]))
    if groups.get("task"):
        reasons.append("Подтверждены решёнными задачами: " + ", ".join(groups["task"]))
    if groups.get("declared"):
        reasons.append("Заявлены в профиле: " + ", ".join(groups["declared"]))
    missing = [s for s, d in detail.items() if d["evidence"] in ("none", "related") and d["must"]]
    if missing:
        warns.append("Нет подтверждения обязательных навыков: " + ", ".join(missing))
    detail["_must_coverage"] = round(must_cov, 3) if must else None
    return val, reasons, warns, detail


# ---------------------------------------------------------------- 3–6
def achievement_fit(a: Achievement, n: NeedView) -> str:
    """Актуальность результата для запроса: стек решения совпал с навыками запроса — профильный, иначе — по дисциплине."""
    if set(a.stack or []) & set(n.must_skills + n.nice_skills):
        return "profile"
    return discipline_fit(a.discipline, n.spec)


def fsp_component(c: CandView, n: NeedView | None = None) -> tuple[float, list[str], list[str]]:
    if not c.achievements:
        return 0.0, [], []
    # все соревнования ФСП равноценны: в объяснении — результативность и число соревнований, без «рейтинга» турниров;
    # вклад результата учитывает актуальность дисциплины для специализации и навыков запроса
    fits = [achievement_fit(a, n) if n else "profile" for a in c.achievements]
    value = c.fsp_score
    if n and all(a.weight is not None for a in c.achievements):
        value = aggregate([(a.weight * DISCIPLINE_FIT[f], a.prize) for a, f in zip(c.achievements, fits)])
    order = sorted(range(len(c.achievements)), key=lambda i: (c.achievements[i].place or 99, -c.achievements[i].year))
    order.sort(key=lambda i: fits[i] != "profile")  # в объяснение — лучший профильный результат, если он есть
    top, top_fit = c.achievements[order[0]], fits[order[0]]
    year = "" if str(top.year) in top.event_name else f" ({top.year})"
    n_all, prizes = len(c.achievements), sum(1 for a in c.achievements if a.result_title != "Участник")
    tally = f" · результативен в {prizes} из {n_all}" if n_all > 1 else ""
    fit_note = "" if n is None else f" · {DISCIPLINE_FIT_NAMES[top_fit]}"
    warns = []
    if n and fits and all(f == "other" for f in fits):
        warns.append(f"Результаты ФСП — в непрофильных для запроса дисциплинах (учтены с весом ×{DISCIPLINE_FIT['other']:.1f})")
    return value, [f"ФСП: {top.result_title} — {top.event_name}{year}{tally}{fit_note}"], warns


def activity_component(c: CandView, now: datetime) -> tuple[float, list[str], list[str]]:
    class _P:  # адаптер к функции activity_score
        pass

    p = _P()
    p.last_activity_at, p.task_score, p.tasks_done = c.last_activity_at, c.task_score, c.tasks_done
    val = activity_score(p, now)  # type: ignore[arg-type]
    reasons = []
    if c.tasks_done:
        reasons.append(f"Регулярные задачи: решено {c.tasks_done}" + (f", средняя оценка {c.task_score:.1f}/5" if c.task_score else ""))
    last = c.last_activity_at
    if last and (now - (last if last.tzinfo else last.replace(tzinfo=timezone.utc))).days <= 30:
        reasons.append("Профиль активен в последние 30 дней")
    return val, reasons, []


def salary_fit(c: CandView, n: NeedView) -> float:
    if not n.salary_to or c.salary_from is None:
        return 0.8
    if c.salary_from <= n.salary_to:
        if c.salary_from >= n.salary_from:
            return 1.0
        return 0.95  # ожидания ниже вилки — подходит, но возможна недооценка
    gap = (c.salary_from - n.salary_to) / max(1, n.salary_to)
    return max(0.0, 1.0 - 3.0 * gap)


def conditions_component(c: CandView, n: NeedView) -> tuple[float, list[str], list[str]]:
    reasons, warns = [], []
    sal = salary_fit(c, n)
    if c.salary_from is not None and n.salary_to:
        rng = f"{c.salary_from // 1000}–{(c.salary_to or c.salary_from) // 1000} тыс. ₽ gross"
        if sal >= 0.95:
            reasons.append(f"Ожидания {rng} укладываются в вашу вилку")
        else:
            warns.append(f"Ожидания {rng} выше вилки на {round((c.salary_from - n.salary_to) / n.salary_to * 100)}%")
    fmt = 1.0
    if n.work_formats and c.work_formats:
        if not set(n.work_formats) & set(c.work_formats):
            fmt = 0.3
            warns.append("Формат работы не совпадает: кандидат готов к " + ", ".join(WORK_FORMATS[f].lower() for f in c.work_formats))
        elif set(n.work_formats) <= {"office", "hybrid"} and n.city and c.city and c.city != n.city and not c.relocation:
            fmt = 0.55
            warns.append(f"Кандидат в г. {c.city}, к переезду не готов")
    return 0.7 * sal + 0.3 * fmt, reasons, warns


def context_component(c: CandView, n: NeedView, text_sim: float) -> tuple[float, list[str], list[str]]:
    reasons = []
    dom = 0.0
    if n.domains:
        common = set(n.domains) & set(c.domains)
        dom = 1.0 if common else 0.0
        if common:
            reasons.append("Опыт в отрасли: " + ", ".join(DOMAINS.get(d, d) for d in common))
    else:
        dom = 0.5
    sim = max(0.0, min(1.0, text_sim / 0.35))
    return 0.5 * dom + 0.5 * sim, reasons, []


def acceptance_likelihood(c: CandView, n: NeedView, now: datetime) -> tuple[float, str]:
    """Оценка вероятности, что кандидат примет приглашение (логистическая модель на правилах)."""
    z = {"active": 0.6, "open": -0.2, "not_looking": -2.5}.get(c.search_status, -0.2)
    z += 2.2 * (salary_fit(c, n) - 0.75)
    if n.work_formats and c.work_formats and not set(n.work_formats) & set(c.work_formats):
        z -= 1.0
    last = c.last_activity_at
    days = (now - (last if last and last.tzinfo else (last.replace(tzinfo=timezone.utc) if last else now))).days if last else 120
    z += 0.6 * math.exp(-days / 30) - 0.3
    z -= 0.25 * min(4, c.pending_invites)
    p = 1 / (1 + math.exp(-z))
    label = "высокая" if p >= 0.6 else ("средняя" if p >= 0.35 else "низкая")
    return round(p, 3), label


def score(c: CandView, n: NeedView, text_sim: float = 0.0, now: datetime | None = None, with_parts: bool = False,
          params: dict | None = None) -> dict | None:
    now = now or datetime.now(timezone.utc)
    rel = category_relation(c, n)
    if not rel:
        return None
    w = weights(n.fsp_weight, params)
    L, rl, wl = level_component(c, n, rel[0])
    S, rs, ws, sdetail = skills_component(c, n)
    F, rf, wf = fsp_component(c, n)
    A, ra, wa = activity_component(c, now)
    C, rc, wc = conditions_component(c, n)
    D, rd, wd = context_component(c, n, text_sim)
    comps = {"L": L, "S": S, "F": F, "A": A, "C": C, "D": D}
    mods = {"over_budget": bool(c.salary_from and n.salary_to and c.salary_from > 1.1 * n.salary_to),
            "format_mismatch": bool(n.work_formats and c.work_formats and not set(n.work_formats) & set(c.work_formats)),
            "must_cov": sdetail.pop("_must_coverage", None), "relation": rel[0], "grade_confirmed": c.grade_confirmed}
    total = combine(comps, mods, n.fsp_weight, params)
    p_accept, p_label = acceptance_likelihood(c, n, now)
    names = {"L": "Подтверждённый уровень", "S": "Навыки", "F": "Достижения ФСП", "A": "Актуальность", "C": "Условия", "D": "Контекст"}
    out = {
        "score": total,
        "relation": rel[0],
        "grade_status": "confirmed" if c.grade_confirmed else "unconfirmed",
        "fit": "strong" if total >= 72 else ("good" if total >= 58 else "partial"),
        "components": [{"key": k, "name": names[k], "value": round(comps[k], 3), "weight": round(w[k], 3),
                        "contribution": round(100 * w[k] * comps[k], 1)} for k in comps],
        "reasons": rl + rs + rf + ra + rc + rd,
        "warnings": wl + ws + wf + wa + wc + wd,
        "skills": sdetail,
        "acceptance": {"p": p_accept, "label": p_label},
    }
    if with_parts:  # для подстройки весов: компоненты и модификаторы без пересчёта
        out["_parts"] = {"comps": comps, "mods": mods, "fsp_weight": n.fsp_weight}
    return out
