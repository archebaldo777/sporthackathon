"""Компьютерное адаптивное тестирование (CAT).

Алгоритм одной попытки:
1. Старт: θ̂₀ = центр заявленного грейда (априорное N(center, 1)).
2. Выбор задания:
   a) контентная балансировка — берём компетенцию с наибольшим «дефицитом» относительно blueprint;
   b) среди подходящих шаблонов считаем информацию Фишера: в точке θ̂, а если θ̂ ближе 0.4 к порогу грейда —
      в точке порога (тест решает задачу классификации, и информативнее всего задания «на границе»);
   c) randomesque-контроль экспозиции: случайный выбор из top-k по информации с поправкой на частоту
      показа шаблона (Sympson–Hetter-подобный множитель) — разные кандидаты получают разные наборы семейств;
   d) из шаблона генерируется уникальный вариант (seed попытки + позиция).
3. После ответа θ̂ пересчитывается (EAP). Остановка — классификационная: тест завершается, как только по каждому
   порогу грейда апостериорная вероятность «выше/ниже» достигла 85% (не раньше 8 заданий и после охвата всех компетенций
   плана); пограничным кандидатам задания добавляются до 22. Так очевидные случаи проходят тест быстрее,
   а точность нужна там, где решение спорное (по Монте-Карло: короче в среднем и точнее, чем остановка по SE).
4. Итоговая θ оценивается с популяционным априорным N(0, 1.2), чтобы заявленный грейд не влиял на решение.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np

from app.catalog.data import COMPETENCIES, GRADE_ORDER, GRADES
from app.testing import irt
from app.testing.bank import REGISTRY, GenCtx, Template

POPULATION_PRIOR = (0.0, 1.2)
EXPOSURE_TARGET = 0.25  # желаемая максимальная доля попыток, в которых показывается шаблон
TOP_K = 4


@dataclass
class Answered:
    template_id: str
    competency: str
    a: float
    b: float
    c: float
    correct: bool

    @property
    def params(self) -> irt.ItemParams:
        return irt.ItemParams(self.a, self.b, self.c)


@dataclass
class CatConfig:
    # совпадает с настройками по умолчанию (TEST_MIN_ITEMS / TEST_MAX_ITEMS / TEST_COVERAGE_ITEMS / TEST_DECISION_CONFIDENCE)
    min_items: int = 8                 # раньше решение не принимается
    max_items: int = 22                # жёсткий предел — достигают только пограничные кандидаты
    coverage_items: int = 14           # до этой длины тест не завершается, пока не затронуты все компетенции плана
    decision_confidence: float = 0.85  # P(θ выше/ниже каждого порога), при которой решение считается надёжным
    cut_window: float = 0.4            # ближе к порогу — задания подбираются по информации в точке порога
    se_target: float | None = None     # необязательное дополнительное требование к точности θ̂
    stop_rule: str = "classification"  # "precision" — прежнее правило (SE ≤ se_target), оставлено для сравнения в валидации


@dataclass
class CatState:
    spec: str
    ctx: GenCtx
    target_grade: str
    blueprint: dict[str, float]
    answered: list[Answered] = field(default_factory=list)
    used: set[str] = field(default_factory=set)
    seen_before: set[str] = field(default_factory=set)  # шаблоны из прошлых попыток кандидата

    @property
    def prior(self) -> tuple[float, float]:
        return GRADES[self.target_grade]["center"], 1.0

    def estimate(self) -> tuple[float, float]:
        mu, sd = self.prior
        th, se, _ = irt.eap([(x.params, x.correct) for x in self.answered], mu, sd)
        return th, se


def item_params(t: Template, overrides: dict[str, tuple[float, float]] | None) -> tuple[float, float, float]:
    if overrides and t.id in overrides:
        a, b = overrides[t.id]
        return a, b, t.c
    return t.a, t.b, t.c


def pool_for(spec: str, ctx: GenCtx, competency: str, retired: set[str]) -> list[Template]:
    return [t for t in REGISTRY.values() if t.competency == competency and t.id not in retired and t.applicable(spec, ctx)]


CUTS = [GRADES[g]["cut"] for g in GRADE_ORDER[1:]]


def info_point(theta: float, window: float) -> float:
    """Точка, в которой максимизируется информация: ближайший порог грейда, если оценка рядом с ним."""
    cut = min(CUTS, key=lambda c: abs(c - theta))
    return cut if abs(cut - theta) < window else theta


def select_next(
    state: CatState,
    rng: random.Random,
    overrides: dict[str, tuple[float, float]] | None = None,
    exposure: dict[str, float] | None = None,
    retired: set[str] | None = None,
    cut_window: float = CatConfig.cut_window,
) -> Template | None:
    retired = retired or set()
    exposure = exposure or {}
    theta = info_point(state.estimate()[0], cut_window)
    n_next = len(state.answered) + 1
    counts: dict[str, int] = {c: 0 for c in state.blueprint}
    for x in state.answered:
        if x.competency in counts:
            counts[x.competency] += 1
    # компетенции по убыванию дефицита (с небольшим случайным разбиением ничьих)
    deficits = sorted(state.blueprint, key=lambda c: (-(state.blueprint[c] * n_next - counts[c]), rng.random()))
    for comp in deficits:
        cands = [t for t in pool_for(state.spec, state.ctx, comp, retired) if t.id not in state.used]
        if not cands:
            continue
        fresh = [t for t in cands if t.id not in state.seen_before]
        if len(fresh) >= 2:
            cands = fresh
        scored = []
        for t in cands:
            a, b, c = item_params(t, overrides)
            info = float(irt.information(theta, a, b, c))
            rate = exposure.get(t.id, 0.0)
            factor = 1.0 if rate <= EXPOSURE_TARGET else EXPOSURE_TARGET / rate
            scored.append((info * factor, t))
        scored.sort(key=lambda p: -p[0])
        top = scored[:TOP_K]
        weights = [max(w, 1e-6) for w, _ in top]
        return rng.choices([t for _, t in top], weights=weights, k=1)[0]
    return None


def decision_probs(state: CatState) -> tuple[float, float, dict[str, float]]:
    """θ̂, SE и P(θ ≥ порога) для каждого грейда — с популяционным априорным, как в итоговом решении."""
    theta, se, post = irt.eap([(x.params, x.correct) for x in state.answered], *POPULATION_PRIOR)
    return theta, se, {g: irt.prob_above(post, GRADES[g]["cut"]) for g in GRADE_ORDER}


def should_stop(state: CatState, cfg: CatConfig) -> bool:
    n = len(state.answered)
    if n >= cfg.max_items:
        return True
    if n < cfg.min_items:
        return False
    covered = {x.competency for x in state.answered}
    if any(c not in covered for c in state.blueprint) and n < cfg.coverage_items:
        return False
    if cfg.stop_rule == "precision":
        return state.estimate()[1] <= (cfg.se_target or 0.35)
    _, se, probs = decision_probs(state)
    lo = 1 - cfg.decision_confidence
    decided = all(not (lo < probs[g] < cfg.decision_confidence) for g in GRADE_ORDER[1:])
    return decided and (cfg.se_target is None or se <= cfg.se_target)


@dataclass
class CatResult:
    theta: float
    se: float
    p_target: float
    passed: bool
    upgrade_grade: str | None
    suggested_grade: str | None
    probs: dict[str, float]
    topic_scores: dict[str, dict]
    person_fit: float | None


def finalize(state: CatState) -> CatResult:
    resp = [(x.params, x.correct) for x in state.answered]
    theta, se, post = irt.eap(resp, *POPULATION_PRIOR)
    probs = {g: irt.prob_above(post, GRADES[g]["cut"]) for g in GRADE_ORDER}
    target = state.target_grade
    p_target = probs[target]
    passed = p_target >= 0.5
    upgrade = None
    idx = GRADE_ORDER.index(target)
    if passed and idx + 1 < len(GRADE_ORDER):
        nxt = GRADE_ORDER[idx + 1]
        if probs[nxt] >= 0.8:  # «уверенно справился» — предлагаем повышение
            upgrade = nxt
    suggested = None
    if not passed:
        for g in reversed(GRADE_ORDER[:idx]):
            if probs[g] >= 0.5:
                suggested = g
                break
    topics: dict[str, dict] = {}
    by_comp: dict[str, list[Answered]] = {}
    for x in state.answered:
        by_comp.setdefault(x.competency, []).append(x)
    for comp, xs in by_comp.items():
        # байесовское сжатие к общему уровню: при 2–3 заданиях оценка темы не «скачет»
        th_c, se_c, _ = irt.eap([(x.params, x.correct) for x in xs], theta, 0.8)
        topics[comp] = {
            "name": COMPETENCIES.get(comp, {}).get("name", comp),
            "theta": round(th_c, 3),
            "score": round(irt.normal_cdf(th_c), 3),
            "n": len(xs),
            "correct": sum(1 for x in xs if x.correct),
        }
    lz = irt.person_fit_lz(resp, theta)
    return CatResult(theta=theta, se=se, p_target=p_target, passed=passed, upgrade_grade=upgrade, suggested_grade=suggested,
                     probs=probs, topic_scores=topics, person_fit=lz)


def simulate(
    true_theta: float,
    spec: str,
    ctx: GenCtx,
    target_grade: str,
    blueprint: dict[str, float],
    rng: random.Random,
    cfg: CatConfig | None = None,
    true_params: dict[str, tuple[float, float, float]] | None = None,
    leaked: set[str] | None = None,
    seen_before: set[str] | None = None,
    exposure: dict[str, float] | None = None,
) -> tuple[CatResult, CatState]:
    """Симуляция прохождения теста «виртуальным кандидатом» с истинной способностью true_theta.

    true_params — «истинные» параметры заданий (могут отличаться от калибровочных, чтобы моделировать ошибку калибровки);
    leaked — шаблоны, ответы на которые кандидат знает заранее (моделирование утечки банка).
    """
    cfg = cfg or CatConfig()
    state = CatState(spec=spec, ctx=ctx, target_grade=target_grade, blueprint=blueprint, seen_before=seen_before or set())
    while not should_stop(state, cfg):
        t = select_next(state, rng, exposure=exposure, cut_window=cfg.cut_window)
        if t is None:
            break
        state.used.add(t.id)
        a, b, c = (true_params or {}).get(t.id, (t.a, t.b, t.c))
        if leaked and t.id in leaked:
            correct = True
        else:
            correct = rng.random() < float(irt.p_correct(true_theta, a, b, c))
        state.answered.append(Answered(t.id, t.competency, t.a, t.b, t.c, correct))
    return finalize(state), state


def grade_from_theta(theta: float) -> str | None:
    g = None
    for code in GRADE_ORDER:
        if theta >= GRADES[code]["cut"]:
            g = code
    return g


def information_curve(t: Template, overrides=None) -> list[list[float]]:
    a, b, c = item_params(t, overrides)
    xs = np.linspace(-3, 3, 25)
    return [[round(float(x), 2), round(float(irt.information(x, a, b, c)), 4)] for x in xs]
