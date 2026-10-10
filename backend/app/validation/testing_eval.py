"""Валидация механики тестирования методом Монте-Карло.

Популяция «виртуальных кандидатов» с известной истинной способностью θ проходит тест тем же CAT-движком,
что и реальные пользователи. Ответ на задание моделируется 3PL-моделью с «истинными» параметрами, которые
специально отличаются от калибровочных (шум ±0.3 по b, ±15% по a) — чтобы не оценивать систему в идеальном мире.

Метрики:
  1. Точность категоризации: доля совпадений присвоенного грейда с истинным, κ Коэна, матрица ошибок.
  2. Согласованность (test–retest): два независимых прохождения (разные формы) — корреляция θ̂, совпадение грейда и решения.
  3. Дискриминативность: точечно-бисериальные корреляции заданий, AUC разделения соседних грейдов.
  4. Устойчивость к утечке: атака «кандидат знает ответы на варианты, показанные предыдущим кандидатам»
     для статичного банка и для параметрической генерации.
  5. Экспозиция: доля попыток, в которых показывается самое популярное семейство (с randomesque и без).
  6. Сравнение с фиксированной формой той же длины.
  7. Восстановление трудности онлайн-калибровкой и детекция дрейфа (имитация утечки способа решения).
"""
from __future__ import annotations

import math
import random
import statistics
from collections import Counter, defaultdict

import numpy as np

from app.catalog.data import GRADE_ORDER, GRADES, SPECIALIZATIONS
from app.testing import irt
from app.testing.bank import REGISTRY, GenCtx, render
from app.testing.cat import CatConfig, CatState, Answered, finalize, grade_from_theta, select_next, should_stop
from app.validation.calibration import recalibrate

SPECS = list(SPECIALIZATIONS)


def true_params(seed: int = 7) -> dict[str, tuple[float, float, float]]:
    rng = random.Random(seed)
    return {tid: (t.a * rng.uniform(0.85, 1.15), t.b + rng.gauss(0, 0.3), t.c) for tid, t in REGISTRY.items()}


def population(n: int, rng: random.Random) -> list[tuple[float, str, str]]:
    """(истинная θ, специализация, заявленный грейд). Грейды заявляют с типичным шумом: 25% завышают на ступень."""
    out = []
    weights = {"intern": 0.12, "junior": 0.28, "middle": 0.35, "senior": 0.25}
    for _ in range(n):
        g = rng.choices(list(weights), list(weights.values()))[0]
        lo = GRADES[g]["cut"]
        hi = GRADES[GRADE_ORDER[GRADE_ORDER.index(g) + 1]]["cut"] if g != "senior" else 2.4
        th = rng.uniform(lo - (0.4 if g == "intern" else 0), hi)
        gi = GRADE_ORDER.index(grade_from_theta(th) or "intern")
        r = rng.random()
        declared = GRADE_ORDER[min(3, gi + 1)] if r < 0.25 else (GRADE_ORDER[max(0, gi - 1)] if r < 0.33 else GRADE_ORDER[gi])
        out.append((th, rng.choice(SPECS), declared))
    return out


LZ_CONFIRM = -2.5  # порог person-fit, при котором сервер требует контрольную форму (service._flags)


def ctx_for(spec: str, rng: random.Random) -> GenCtx:
    langs = SPECIALIZATIONS[spec]["langs"]
    return GenCtx(lang=rng.choice(langs), framework=rng.choice(["react", "vue", "angular"]) if spec == "frontend" else None, spec=spec)


def run_test(theta: float, spec: str, ctx: GenCtx, target: str, rng: random.Random, cfg: CatConfig, tp: dict, randomesque: bool = True,
             leak: dict | None = None, exposure: dict | None = None, help_rate: float = 0.0):
    st = CatState(spec=spec, ctx=ctx, target_grade=target, blueprint=SPECIALIZATIONS[spec]["blueprint"])
    responses = []
    leaked_hits = 0
    while not should_stop(st, cfg):
        if randomesque:
            t = select_next(st, rng, exposure=exposure, cut_window=cfg.cut_window)
        else:
            t = _max_info(st)
        if t is None:
            break
        st.used.add(t.id)
        a, b, c = tp[t.id]
        known = False
        if leak is not None:
            if leak["mode"] == "static":
                known = t.id in leak["templates"]
            else:  # параметрический банк: ответ известен только при точном совпадении варианта
                exposed = leak["hashes"].get(t.id, set())
                _, _, h = render(t, rng.randint(1, 2**31), ctx)
                # как на сервере (service.fresh_variant): уже показанный вариант не выдаётся повторно
                tries = 1
                while leak.get("fresh") and h in exposed and tries < 25:
                    _, _, h = render(t, rng.randint(1, 2**31), ctx)
                    tries += 1
                known = h in exposed
        helped = help_rate > 0 and rng.random() < help_rate  # «помощь извне»: верный ответ независимо от трудности
        correct = True if (known or helped) else (rng.random() < float(irt.p_correct(theta, a, b, c)))
        leaked_hits += known
        st.answered.append(Answered(t.id, t.competency, t.a, t.b, t.c, correct))
        responses.append((t.id, correct))
    return finalize(st), st, responses, leaked_hits


def _max_info(st: CatState):
    from app.testing.cat import pool_for

    theta, _ = st.estimate()
    n_next = len(st.answered) + 1
    counts = Counter(x.competency for x in st.answered)
    for comp in sorted(st.blueprint, key=lambda c: -(st.blueprint[c] * n_next - counts[c])):
        cands = [t for t in pool_for(st.spec, st.ctx, comp, set()) if t.id not in st.used]
        if cands:
            return max(cands, key=lambda t: float(irt.information(theta, t.a, t.b, t.c)))
    return None


def assigned_grade(res) -> str | None:
    """Итоговый грейд: самый высокий уровень, который тест подтверждает с вероятностью ≥ 0.5."""
    g = None
    for code in GRADE_ORDER:
        if res.probs[code] >= 0.5:
            g = code
    return g


def kappa(a: list, b: list, labels: list, weighted: bool = False) -> float:
    idx = {l: i for i, l in enumerate(labels)}
    k = len(labels)
    m = np.zeros((k, k))
    for x, y in zip(a, b):
        m[idx[x], idx[y]] += 1
    n = m.sum()
    w = np.array([[((i - j) ** 2) / ((k - 1) ** 2) if weighted else float(i != j) for j in range(k)] for i in range(k)])
    exp = np.outer(m.sum(1), m.sum(0)) / n
    return float(1 - (w * m).sum() / max(1e-9, (w * exp).sum()))


def auc(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return float("nan")
    s = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return s / (len(pos) * len(neg))


def pointbiserial(xs: list[float], ys: list[int]) -> float | None:
    if len(set(ys)) < 2 or len(xs) < 20:
        return None
    x = np.array(xs)
    y = np.array(ys)
    m1, m0 = x[y == 1].mean(), x[y == 0].mean()
    p = y.mean()
    sd = x.std()
    return float((m1 - m0) / sd * math.sqrt(p * (1 - p))) if sd > 0 else None


def variant_uniqueness(n_seeds: int = 150, seed: int = 3) -> dict:
    rng = random.Random(seed)
    per_template = {}
    for tid, t in REGISTRY.items():
        lang = (t.langs or (None,))[0]
        fw = (t.frameworks or ("react",))[0]
        ctx = GenCtx(lang=lang, framework=fw, spec=t.specs[0])
        hashes = [render(t, rng.randint(1, 2**31), ctx)[2] for _ in range(n_seeds)]
        uniq = len(set(hashes))
        # вероятность совпадения двух случайных вариантов (оценка по частотам)
        cnt = Counter(hashes)
        collision = sum(v * (v - 1) for v in cnt.values()) / (n_seeds * (n_seeds - 1))
        per_template[tid] = {"unique_share": uniq / n_seeds, "collision": collision, "method": t.method}
    us = [v["unique_share"] for v in per_template.values()]
    cols = [v["collision"] for v in per_template.values()]
    by_method = defaultdict(list)
    for v in per_template.values():
        by_method[v["method"]].append(v["unique_share"])
    return {
        "seeds_per_template": n_seeds,
        "median_unique_share": round(statistics.median(us), 3),
        "share_templates_fully_unique": round(sum(1 for u in us if u >= 0.99) / len(us), 3),
        "mean_pairwise_collision": round(statistics.mean(cols), 4),
        "by_method": {m: {"templates": len(v), "median_unique_share": round(statistics.median(v), 3)} for m, v in by_method.items()},
        "worst": sorted(({"template": k, **v} for k, v in per_template.items()), key=lambda x: x["unique_share"])[:5],
    }


def evaluate(n: int = 1200, seed: int = 2026) -> dict:
    rng = random.Random(seed)
    tp = true_params()
    cfg = CatConfig()
    pop = population(n, rng)
    rows = []
    item_obs: dict[str, list[tuple[float, int]]] = defaultdict(list)
    exposure_count: Counter = Counter()
    for th, spec, declared in pop:
        ctx = ctx_for(spec, rng)
        r1, s1, resp1, _ = run_test(th, spec, ctx, declared, random.Random(rng.random()), cfg, tp)
        r2, s2, _, _ = run_test(th, spec, ctx, declared, random.Random(rng.random()), cfg, tp)
        for tid, ok in resp1:
            item_obs[tid].append((r1.theta, int(ok)))  # в реальности истинная θ неизвестна — используем оценку
        for tid in {t for t, _ in resp1}:
            exposure_count[tid] += 1
        true_g = grade_from_theta(th) or "intern"
        rows.append({"theta": th, "spec": spec, "declared": declared, "true": true_g, "t1": r1.theta, "t2": r2.theta, "se1": r1.se,
                     "g1": assigned_grade(r1) or "intern", "g2": assigned_grade(r2) or "intern", "p1": r1.passed, "p2": r2.passed,
                     "n1": len(s1.answered), "templates1": {x.template_id for x in s1.answered}, "templates2": {x.template_id for x in s2.answered}})
    true_ = [r["true"] for r in rows]
    g1 = [r["g1"] for r in rows]
    g2 = [r["g2"] for r in rows]
    decl = [r["declared"] for r in rows]
    t1 = np.array([r["t1"] for r in rows])
    t2 = np.array([r["t2"] for r in rows])
    th = np.array([r["theta"] for r in rows])
    conf = {a: {b: 0 for b in GRADE_ORDER} for a in GRADE_ORDER}
    for a, b in zip(true_, g1):
        conf[a][b] += 1
    # точность решения «подтверждён/не подтверждён» относительно истинного уровня
    sens = [r["p1"] for r in rows if r["theta"] >= GRADES[r["declared"]]["cut"]]
    spec_ = [not r["p1"] for r in rows if r["theta"] < GRADES[r["declared"]]["cut"]]
    far = [r for r in rows if min(abs(r["theta"] - GRADES[g]["cut"]) for g in GRADE_ORDER[1:]) > 0.25]
    # точность в зависимости от расстояния до ближайшего порога: показывает, что ошибки сосредоточены у границ грейдов
    dist_bins = [(0.0, 0.1), (0.1, 0.25), (0.25, 0.5), (0.5, 9.9)]
    by_dist = []
    for lo, hi in dist_bins:
        grp = [r for r in rows if lo <= min(abs(r["theta"] - GRADES[g]["cut"]) for g in GRADE_ORDER[1:]) < hi]
        by_dist.append({"range": f"{lo:g}–{hi:g}" if hi < 9 else f"> {lo:g}", "share": round(len(grp) / n, 3),
                        "accuracy": round(sum(r["g1"] == r["true"] for r in grp) / max(1, len(grp)), 3)})
    # завысившие грейд в анкете: насколько тест не даёт им «заявленное», а возвращает к истинному
    inflated = [r for r in rows if GRADE_ORDER.index(r["declared"]) > GRADE_ORDER.index(r["true"])]
    honest = [r for r in rows if r["declared"] == r["true"]]
    # дискриминативность
    rpb = [v for v in (pointbiserial([x for x, _ in obs], [y for _, y in obs]) for obs in item_obs.values()) if v is not None]
    by_true = defaultdict(list)
    for r in rows:
        by_true[r["true"]].append(r["t1"])
    aucs = {f"{GRADE_ORDER[i]}→{GRADE_ORDER[i + 1]}": round(auc(by_true[GRADE_ORDER[i + 1]], by_true[GRADE_ORDER[i]]), 3) for i in range(3)}
    # пересечение форм у разных кандидатов одной специализации
    overlaps = []
    by_spec = defaultdict(list)
    for r in rows:
        by_spec[r["spec"]].append(r["templates1"])
    for sets in by_spec.values():
        for _ in range(60):
            if len(sets) < 2:
                break
            a, b = random.sample(sets, 2)
            overlaps.append(len(a & b) / max(1, len(a | b)))
    retest_overlap = statistics.mean(len(r["templates1"] & r["templates2"]) / max(1, len(r["templates1"] | r["templates2"])) for r in rows)
    total_tests = len(rows)
    exp_rates = sorted((c / total_tests for c in exposure_count.values()), reverse=True)
    result = {
        "population": n,
        "config": {"min_items": cfg.min_items, "max_items": cfg.max_items, "coverage_items": cfg.coverage_items,
                   "decision_confidence": cfg.decision_confidence, "stop_rule": cfg.stop_rule},
        "accuracy": {
            "exact_grade_agreement": round(sum(a == b for a, b in zip(true_, g1)) / n, 3),
            "within_one_grade": round(sum(abs(GRADE_ORDER.index(a) - GRADE_ORDER.index(b)) <= 1 for a, b in zip(true_, g1)) / n, 3),
            "self_declared_agreement": round(sum(a == b for a, b in zip(true_, decl)) / n, 3),
            "kappa": round(kappa(true_, g1, GRADE_ORDER), 3),
            "kappa_weighted": round(kappa(true_, g1, GRADE_ORDER, weighted=True), 3),
            "theta_corr_true": round(float(np.corrcoef(th, t1)[0, 1]), 3),
            "theta_rmse": round(float(np.sqrt(((t1 - th) ** 2).mean())), 3),
            "theta_bias": round(float((t1 - th).mean()), 3),
            "mean_se": round(statistics.mean(r["se1"] for r in rows), 3),
            "mean_items": round(statistics.mean(r["n1"] for r in rows), 2),
            "decision_sensitivity": round(sum(sens) / max(1, len(sens)), 3),
            "decision_specificity": round(sum(spec_) / max(1, len(spec_)), 3),
            "exact_agreement_far_from_cuts": round(sum(r["g1"] == r["true"] for r in far) / max(1, len(far)), 3),
            "by_distance_to_cut": by_dist,
            "inflated_share": round(len(inflated) / n, 3),
            "inflated_rejected": round(sum(GRADE_ORDER.index(r["g1"]) < GRADE_ORDER.index(r["declared"]) for r in inflated) / max(1, len(inflated)), 3),
            "inflated_exact": round(sum(r["g1"] == r["true"] for r in inflated) / max(1, len(inflated)), 3),
            "honest_confirmed": round(sum(r["g1"] == r["declared"] for r in honest) / max(1, len(honest)), 3),
            "items_distribution": {"p10": sorted(r["n1"] for r in rows)[n // 10], "median": sorted(r["n1"] for r in rows)[n // 2],
                                   "p90": sorted(r["n1"] for r in rows)[9 * n // 10],
                                   "share_extended": round(sum(r["n1"] > cfg.coverage_items for r in rows) / n, 3)},
            "confusion": conf,
        },
        "consistency": {
            "theta_test_retest_r": round(float(np.corrcoef(t1, t2)[0, 1]), 3),
            "grade_agreement": round(sum(a == b for a, b in zip(g1, g2)) / n, 3),
            "grade_kappa": round(kappa(g1, g2, GRADE_ORDER), 3),
            "grade_kappa_weighted": round(kappa(g1, g2, GRADE_ORDER, weighted=True), 3),
            "decision_agreement": round(sum(r["p1"] == r["p2"] for r in rows) / n, 3),
            "within_one_grade": round(sum(abs(GRADE_ORDER.index(a) - GRADE_ORDER.index(b)) <= 1 for a, b in zip(g1, g2)) / n, 3),
            "form_overlap_same_candidate": round(retest_overlap, 3),
        },
        "discrimination": {
            "items_evaluated": len(rpb),
            "median_point_biserial": round(statistics.median(rpb), 3) if rpb else None,
            "share_rpb_above_0_2": round(sum(1 for v in rpb if v > 0.2) / len(rpb), 3) if rpb else None,
            "adjacent_grade_auc": aucs,
            "mean_theta_by_true_grade": {g: round(statistics.mean(by_true[g]), 3) for g in GRADE_ORDER if by_true[g]},
        },
        "exposure": {
            "max_exposure_rate": round(exp_rates[0], 3) if exp_rates else None,
            "share_templates_above_target": round(sum(1 for e in exp_rates if e > 0.25) / max(1, len(exp_rates)), 3),
            "templates_used": len(exposure_count),
            "mean_form_overlap_between_candidates": round(statistics.mean(overlaps), 3) if overlaps else None,
        },
        "item_observations": {k: v for k, v in item_obs.items()},
    }
    return result


def leak_attack(n_attackers: int = 150, seed: int = 11) -> dict:
    """Атака утечкой: кандидат уровня Junior (θ = −0.5) знает ответы, собранные у предыдущих кандидатов.

    static — банк с фиксированными заданиями (как у «единого набора заданий»): известно 60% ответов банка.
    parametric_reuse — параметрический банк без проверки свежести: известны варианты 40 предыдущих кандидатов по каждому
    семейству, и совпадение возможно, если генератор случайно повторит вариант.
    parametric — «Драфт»: то же, но сервер не выдаёт уже показанный кому-либо вариант (service.fresh_variant).
    """
    rng = random.Random(seed)
    tp = true_params()
    cfg = CatConfig()
    spec = "backend"
    ctx = GenCtx(lang="python", spec=spec)
    templates = [t for t in REGISTRY.values() if spec in t.specs and t.applicable(spec, ctx)]
    leaked_static = {t.id for t in rng.sample(templates, int(0.6 * len(templates)))}
    leaked_hashes = {t.id: {render(t, rng.randint(1, 2**31), ctx)[2] for _ in range(40)} for t in templates}
    out = {}
    for mode in ("none", "static", "parametric_reuse", "parametric"):
        passes, thetas, hits = [], [], []
        for _ in range(n_attackers):
            leak = None if mode == "none" else ({"mode": "static", "templates": leaked_static} if mode == "static" else
                                                 {"mode": "parametric", "hashes": leaked_hashes, "fresh": mode == "parametric"})
            res, st, _, h = run_test(-0.5, spec, ctx, "middle", random.Random(rng.random()), cfg, tp, leak=leak)
            passes.append(res.passed)
            thetas.append(res.theta)
            hits.append(h / max(1, len(st.answered)))
        out[mode] = {"pass_rate_middle": round(sum(passes) / n_attackers, 3), "mean_theta": round(statistics.mean(thetas), 3),
                     "share_items_answered_from_leak": round(statistics.mean(hits), 3)}
    out["theta_inflation_static"] = round(out["static"]["mean_theta"] - out["none"]["mean_theta"], 3)
    out["theta_inflation_parametric"] = round(out["parametric"]["mean_theta"] - out["none"]["mean_theta"], 3)
    out["theta_inflation_parametric_reuse"] = round(out["parametric_reuse"]["mean_theta"] - out["none"]["mean_theta"], 3)
    out["pass_gain_parametric_pp"] = round(100 * (out["parametric"]["pass_rate_middle"] - out["none"]["pass_rate_middle"]), 1)
    return out


def exposure_ablation(n: int = 400, seed: int = 5) -> dict:
    rng = random.Random(seed)
    tp = true_params()
    cfg = CatConfig()
    res = {}
    for mode in ("randomesque", "max_info"):
        cnt: Counter = Counter()
        overlaps = []
        prev = []
        for i in range(n):
            th = rng.gauss(0.2, 1.0)
            spec = "backend"
            ctx = GenCtx(lang="python", spec=spec)
            _, st, _, _ = run_test(th, spec, ctx, "middle", random.Random(rng.random()), cfg, tp, randomesque=mode == "randomesque")
            ids = {x.template_id for x in st.answered}
            cnt.update(ids)
            if prev:
                other = rng.choice(prev)
                overlaps.append(len(ids & other) / max(1, len(ids | other)))
            prev.append(ids)
        rates = sorted((c / n for c in cnt.values()), reverse=True)
        res[mode] = {"max_exposure": round(rates[0], 3), "top5_mean_exposure": round(statistics.mean(rates[:5]), 3),
                     "templates_used": len(cnt), "mean_overlap_between_candidates": round(statistics.mean(overlaps), 3)}
    return res


def fixed_form_comparison(n: int = 500, seed: int = 9) -> dict:
    """Сравнение CAT с фиксированной формой той же СРЕДНЕЙ длины (одинаковые задания для всех)."""
    rng = random.Random(seed)
    tp = true_params()
    cfg = CatConfig()
    spec = "backend"
    ctx = GenCtx(lang="python", spec=spec)
    people = [(rng.uniform(-2.2, 2.4), rng.random(), random.Random(rng.random())) for _ in range(n)]
    acc = {"cat": [], "fixed": []}
    se = {"cat": [], "fixed": []}
    lengths = []
    for th, _, r in people:
        res, st, _, _ = run_test(th, spec, ctx, "middle", r, cfg, tp)
        acc["cat"].append((assigned_grade(res) or "intern") == (grade_from_theta(th) or "intern"))
        se["cat"].append(res.se)
        lengths.append(len(st.answered))
    length = round(statistics.mean(lengths))
    st0 = CatState(spec=spec, ctx=ctx, target_grade="middle", blueprint=SPECIALIZATIONS[spec]["blueprint"])
    fixed = []
    r0 = random.Random(1)
    while len(fixed) < length:
        t = select_next(st0, r0, cut_window=0.0)
        if not t:
            break
        st0.used.add(t.id)
        st0.answered.append(Answered(t.id, t.competency, t.a, t.b, t.c, True))
        fixed.append(t)
    for th, u, _ in people:
        rr = random.Random(u)
        resp = []
        for t in fixed:
            a, b, c = tp[t.id]
            resp.append((irt.ItemParams(t.a, t.b, t.c), rr.random() < float(irt.p_correct(th, a, b, c))))
        _, sef, post = irt.eap(resp, 0.0, 1.2)
        probs = {g: irt.prob_above(post, GRADES[g]["cut"]) for g in GRADE_ORDER}
        gf = None
        for g in GRADE_ORDER:
            if probs[g] >= 0.5:
                gf = g
        acc["fixed"].append((gf or "intern") == (grade_from_theta(th) or "intern"))
        se["fixed"].append(sef)
    return {k: {"grade_accuracy": round(sum(acc[k]) / n, 3), "mean_se": round(statistics.mean(se[k]), 3)} for k in acc} | {"items": length}


def stop_rule_ablation(n: int = 1000, seed: int = 31) -> dict:
    """Прежнее правило (остановка по точности SE ≤ 0.35, 10–16 заданий, задания по информации в θ̂) против
    классификационного (остановка при надёжном решении по каждому порогу, 8–22 задания, задания у порога)."""
    tp = true_params()
    configs = {"precision_se": CatConfig(min_items=10, max_items=16, coverage_items=16, stop_rule="precision", se_target=0.35, cut_window=0.0),
               "classification": CatConfig()}
    rng = random.Random(seed)
    pop = population(n, rng)
    seeds = [(rng.random(), rng.random(), rng.random()) for _ in pop]
    out = {}
    for name, cfg in configs.items():
        ok = agree = dec = far_ok = far_n = 0
        items = []
        for (th, spec, declared), (s0, s1, s2) in zip(pop, seeds):
            ctx = ctx_for(spec, random.Random(s0))
            r1, st1, _, _ = run_test(th, spec, ctx, declared, random.Random(s1), cfg, tp)
            r2, _, _, _ = run_test(th, spec, ctx, declared, random.Random(s2), cfg, tp)
            tg = grade_from_theta(th) or "intern"
            g1, g2 = assigned_grade(r1) or "intern", assigned_grade(r2) or "intern"
            ok += g1 == tg
            agree += g1 == g2
            dec += r1.passed == (th >= GRADES[declared]["cut"])
            items.append(len(st1.answered))
            if min(abs(th - GRADES[g]["cut"]) for g in GRADE_ORDER[1:]) > 0.25:
                far_n += 1
                far_ok += g1 == tg
        out[name] = {"exact": round(ok / n, 3), "far_from_cuts": round(far_ok / max(1, far_n), 3), "decision": round(dec / n, 3),
                     "retest_agreement": round(agree / n, 3), "mean_items": round(statistics.mean(items), 1),
                     "max_items": max(items)}
    return out


def calibration_recovery(item_obs: dict[str, list[tuple[float, int]]], seed: int = 4) -> dict:
    """Восстановление трудности по накопленным ответам + детекция дрейфа после имитации утечки «способа решения»."""
    tp = true_params()
    data = {tid: [(th, bool(y)) for th, y in obs] for tid, obs in item_obs.items()}
    res = recalibrate(data)
    errs_prior, errs_new = [], []
    for tid, r in res.items():
        b_true = tp[tid][1]
        errs_prior.append((REGISTRY[tid].b - b_true) ** 2)
        errs_new.append((r["b_new"] - b_true) ** 2)
    # дрейф: для 8 семейств задания «стали легче» на 1.2 логита (утёк приём решения)
    rng = random.Random(seed)
    drifted = set(rng.sample(sorted(res), min(8, len(res))))
    data2 = {}
    for tid, obs in data.items():
        if tid in drifted:
            a, b, c = tp[tid]
            data2[tid] = [(th, rng.random() < float(irt.p_correct(th, a, b - 1.2, c))) for th, _ in obs]
        else:
            data2[tid] = obs
    res2 = recalibrate(data2)
    flagged = {k for k, v in res2.items() if v["drift"]}
    return {
        "templates_calibrated": len(res),
        "rmse_b_prior": round(math.sqrt(statistics.mean(errs_prior)), 3) if errs_prior else None,
        "rmse_b_after": round(math.sqrt(statistics.mean(errs_new)), 3) if errs_new else None,
        "drift_simulated": len(drifted),
        "drift_detected": len(flagged & drifted),
        "false_alarms": len(flagged - drifted),
    }


def integrity_eval(n_honest: int = 800, n_cheaters: int = 300, seed: int = 41) -> dict:
    """Статистическая часть детектора нечестности (person-fit lz < −2.5 → контрольная форма).

    Честные кандидаты: θ ~ N(0.2, 1), все специализации. «Помощь извне»: кандидат уровня θ = −0.8 на половине заданий
    получает верный ответ независимо от трудности (подсказка, нейросеть). Поведенческие сигналы (уходы со вкладки,
    вставки, сверхбыстрые ответы) в симуляции не моделируются — их вклад видно только на реальных данных.
    """
    rng = random.Random(seed)
    tp = true_params()
    cfg = CatConfig()
    honest_flag = 0
    for _ in range(n_honest):
        spec = rng.choice(list(SPECIALIZATIONS))
        res, *_ = run_test(rng.gauss(0.2, 1.0), spec, ctx_for(spec, rng), "middle", random.Random(rng.random()), cfg, tp)
        honest_flag += (res.person_fit or 0) < LZ_CONFIRM
    flagged = passed = passed_unflagged = 0
    for _ in range(n_cheaters):
        res, *_ = run_test(-0.8, "backend", ctx_for("backend", rng), "middle", random.Random(rng.random()), cfg, tp, help_rate=0.5)
        f = (res.person_fit or 0) < LZ_CONFIRM
        flagged += f
        passed += res.passed
        passed_unflagged += res.passed and not f
    return {"lz_threshold": LZ_CONFIRM, "honest_flagged": round(honest_flag / n_honest, 4),
            "help_cheaters_flagged": round(flagged / n_cheaters, 3), "help_cheaters_pass_middle": round(passed / n_cheaters, 3),
            "help_cheaters_pass_unflagged": round(passed_unflagged / n_cheaters, 3), "n_honest": n_honest, "n_cheaters": n_cheaters}
