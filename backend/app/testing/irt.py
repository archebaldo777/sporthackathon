"""Модель IRT (трёхпараметрическая логистическая, 3PL) и байесовская оценка способности (EAP).

P_i(θ) = c_i + (1 − c_i) / (1 + exp(−a_i (θ − b_i)))

* a — дискриминативность (насколько резко задание разделяет слабых и сильных),
* b — трудность (θ, при которой вероятность верного ответа посередине между c и 1),
* c — вероятность угадывания (для выбора из k вариантов ≈ 1/k).

Оценка способности — EAP (expected a posteriori) на сетке квадратур: устойчива при малом числе ответов
и не расходится при «все верно/все неверно», в отличие от MLE.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

GRID = np.linspace(-4.0, 4.0, 161)


@dataclass(frozen=True)
class ItemParams:
    a: float
    b: float
    c: float


def p_correct(theta: float | np.ndarray, a: float, b: float, c: float):
    return c + (1.0 - c) / (1.0 + np.exp(-a * (theta - b)))


def information(theta: float | np.ndarray, a: float, b: float, c: float):
    """Информация Фишера 3PL-задания в точке θ."""
    p = p_correct(theta, a, b, c)
    q = 1.0 - p
    return (a**2) * ((p - c) ** 2 / (1.0 - c) ** 2) * (q / p)


def posterior(responses: list[tuple[ItemParams, bool]], prior_mu: float = 0.0, prior_sd: float = 1.0) -> np.ndarray:
    log_post = -0.5 * ((GRID - prior_mu) / prior_sd) ** 2
    for prm, correct in responses:
        p = np.clip(p_correct(GRID, prm.a, prm.b, prm.c), 1e-9, 1 - 1e-9)
        log_post += np.log(p) if correct else np.log(1.0 - p)
    log_post -= log_post.max()
    post = np.exp(log_post)
    return post / post.sum()


def eap(responses: list[tuple[ItemParams, bool]], prior_mu: float = 0.0, prior_sd: float = 1.0) -> tuple[float, float, np.ndarray]:
    """Возвращает (θ̂, SE, апостериорное распределение на сетке)."""
    post = posterior(responses, prior_mu, prior_sd)
    mean = float((GRID * post).sum())
    sd = float(math.sqrt(((GRID - mean) ** 2 * post).sum()))
    return mean, sd, post


def prob_above(post: np.ndarray, cut: float) -> float:
    """Апостериорная вероятность того, что истинная способность не ниже порога."""
    return float(post[GRID >= cut].sum())


def person_fit_lz(responses: list[tuple[ItemParams, bool]], theta: float) -> float | None:
    """Стандартизированный индекс согласованности ответов lz (Drasgow et al., 1985).

    Сильно отрицательные значения (< −1.96) означают аномальный паттерн: например, кандидат «проваливает»
    лёгкие задания и решает трудные — типичный признак подсказок или утечки ответов.
    """
    if len(responses) < 6:
        return None
    l0 = e = v = 0.0
    for prm, u in responses:
        p = float(np.clip(p_correct(theta, prm.a, prm.b, prm.c), 1e-6, 1 - 1e-6))
        l0 += math.log(p) if u else math.log(1 - p)
        e += p * math.log(p) + (1 - p) * math.log(1 - p)
        v += p * (1 - p) * (math.log(p / (1 - p))) ** 2
    if v <= 1e-9:
        return None
    return (l0 - e) / math.sqrt(v)


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
