"""Онлайн-калибровка трудности семейств заданий и детекция дрейфа параметров.

Для шаблона с n ≥ 30 ответами оценивается трудность b методом максимального правдоподобия при известных θ
испытуемых (итоговые оценки попыток) и фиксированной дискриминативности a. Итог сжимается к априорному
значению: b = (n·b̂ + 20·b₀)/(n + 20). Если задание стало заметно легче ожидаемого (b̂ < b₀ − 0.6),
семейство помечается флагом дрейфа — типичный след утечки «способа решения» в сообщество.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ItemStat, TestAttempt, TestItem
from app.testing import irt
from app.testing.bank import REGISTRY

GRID = np.linspace(-3.5, 3.5, 141)
MIN_N, PRIOR_N, DRIFT = 30, 20.0, 0.6


def estimate_b(thetas: np.ndarray, correct: np.ndarray, a: float, c: float) -> float:
    ll = []
    for b in GRID:
        p = np.clip(irt.p_correct(thetas, a, b, c), 1e-6, 1 - 1e-6)
        ll.append(float(np.sum(correct * np.log(p) + (1 - correct) * np.log(1 - p))))
    return float(GRID[int(np.argmax(ll))])


def recalibrate(data: dict[str, list[tuple[float, bool]]]) -> dict[str, dict]:
    out = {}
    for tid, rows in data.items():
        t = REGISTRY.get(tid)
        if not t or len(rows) < MIN_N:
            continue
        th = np.array([r[0] for r in rows])
        y = np.array([1.0 if r[1] else 0.0 for r in rows])
        b_hat = estimate_b(th, y, t.a, t.c)
        n = len(rows)
        b_new = (n * b_hat + PRIOR_N * t.b) / (n + PRIOR_N)
        out[tid] = {"n": n, "b_prior": round(t.b, 3), "b_hat": round(b_hat, 3), "b_new": round(b_new, 3),
                    "drift": b_hat < t.b - DRIFT, "harder": b_hat > t.b + DRIFT + 0.2}
    return out


def recalibrate_from_db(db: Session) -> dict:
    rows = db.execute(select(TestItem.template_id, TestAttempt.theta, TestItem.is_correct)
                      .join(TestAttempt, TestAttempt.id == TestItem.attempt_id)
                      .where(TestAttempt.status == "completed", TestItem.is_correct.is_not(None), TestAttempt.theta.is_not(None))).all()
    data: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    for tid, th, ok in rows:
        data[tid].append((th, bool(ok)))
    res = recalibrate(data)
    for tid, r in res.items():
        st = db.get(ItemStat, tid) or ItemStat(template_id=tid, administered=len(data[tid]), correct=sum(1 for x in data[tid] if x[1]))
        st.a, st.b, st.drift_flag = REGISTRY[tid].a, r["b_new"], r["drift"]
        db.add(st)
    db.commit()
    return {"calibrated": len(res), "drift_flagged": [k for k, v in res.items() if v["drift"]], "details": res}
