"""Каркас банка заданий.

Ключевая идея устойчивости к утечкам: в банке хранятся не задания, а *шаблоны-семейства* (item families).
Каждый шаблон — генератор, который по зерну (seed) порождает уникальный вариант: другие числа, данные,
идентификаторы, порядок строк кода, набор утверждений и порядок вариантов ответа. Верный ответ не хранится
в банке, а **вычисляется** генератором (исполнением SQL на сгенерированной таблице, симуляцией алгоритма,
пересчётом формулы). Поэтому «слитый» ответ на один вариант бесполезен для другого, а трудность
вариантов внутри семейства одинакова (изоморфные задания) — IRT-параметры калибруются на уровне семейства.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# Трудность по умолчанию для номинального уровня шаблона (шкала θ)
LEVEL_B = {1: -1.6, 2: -0.5, 3: 0.55, 4: 1.55}
LEVEL_NAMES = {1: "Стажёр", 2: "Junior", 3: "Middle", 4: "Senior"}


@dataclass
class Variant:
    """Сгенерированный экземпляр задания."""

    text: str
    kind: str  # single | multi | input
    options: list[tuple[str, bool]] | None = None
    answer: Any = None  # для input: число или список допустимых строк
    input_type: str = "text"  # number | text
    tolerance: float = 0.0
    code: str | None = None
    code_lang: str | None = None
    tables: list[dict] | None = None
    hint: str | None = None
    explanation: str | None = None


@dataclass
class GenCtx:
    lang: str | None = None
    framework: str | None = None
    spec: str | None = None


@dataclass
class Template:
    id: str
    title: str
    competency: str
    specs: tuple[str, ...]
    level: int
    kind: str
    gen: Callable[[random.Random, GenCtx], Variant]
    langs: tuple[str, ...] | None = None  # для каких языковых треков применимо (None — для всех)
    frameworks: tuple[str, ...] | None = None
    a_override: float | None = None
    b_offset: float = 0.0
    time_limit: int = 150
    method: str = "parametric"  # parametric | pool | hybrid
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def a(self) -> float:
        # Априорная дискриминативность по формату: задания с вводом ответа не допускают угадывания и обычно
        # различают кандидатов сильнее, чем выбор из вариантов. Уточняется онлайн-калибровкой (ItemStat).
        if self.a_override is not None:
            return self.a_override
        return {"input": 1.8, "multi": 1.6, "single": 1.3}[self.kind] - (0.1 if self.method == "pool" else 0.0)

    @property
    def b(self) -> float:
        return LEVEL_B[self.level] + self.b_offset

    @property
    def c(self) -> float:
        # вероятность угадывания: для одиночного выбора из 4 — ~0.2 (с учётом правдоподобных дистракторов),
        # для множественного выбора и ввода ответа — близка к нулю
        return {"single": 0.2, "multi": 0.05, "input": 0.02}[self.kind]

    def applicable(self, spec: str, ctx: GenCtx) -> bool:
        if spec not in self.specs:
            return False
        if self.langs is not None and (ctx.lang not in self.langs):
            return False
        if self.frameworks is not None and (ctx.framework not in self.frameworks):
            return False
        return True


REGISTRY: dict[str, Template] = {}


def template(
    id: str,
    title: str,
    competency: str,
    specs: tuple[str, ...] | list[str],
    level: int,
    kind: str,
    *,
    langs=None,
    frameworks=None,
    a: float | None = None,
    b_offset: float = 0.0,
    time_limit: int = 150,
    method: str = "parametric",
):
    """Декоратор регистрации шаблона-генератора."""

    def deco(fn):
        REGISTRY[id] = Template(
            id=id,
            title=title,
            competency=competency,
            specs=tuple(specs),
            level=level,
            kind=kind,
            gen=fn,
            langs=tuple(langs) if langs else None,
            frameworks=tuple(frameworks) if frameworks else None,
            a_override=a,
            b_offset=b_offset,
            time_limit=time_limit,
            method=method,
        )
        return fn

    return deco


# ------------------------------------------------------------------ рендер варианта
def render(tpl: Template, seed: int, ctx: GenCtx) -> tuple[dict, dict, str]:
    """Генерирует вариант: (payload для кандидата, ключ ответа для сервера, хэш варианта)."""
    rng = random.Random(seed)
    v = tpl.gen(rng, ctx)
    payload: dict[str, Any] = {"kind": v.kind, "text": v.text}
    key: dict[str, Any] = {"kind": v.kind}
    if v.code:
        payload["code"] = v.code
        payload["code_lang"] = v.code_lang or ctx.lang or "text"
    if v.tables:
        payload["tables"] = v.tables
    if v.hint:
        payload["hint"] = v.hint
    if v.kind in ("single", "multi"):
        opts = list(v.options or [])
        # дедупликация вариантов с сохранением порядка
        seen, uniq = set(), []
        for text, ok in opts:
            if text in seen:
                continue
            seen.add(text)
            uniq.append((text, ok))
        rng.shuffle(uniq)
        payload["options"] = [t for t, _ in uniq]
        key["correct"] = sorted(i for i, (_, ok) in enumerate(uniq) if ok)
    else:
        payload["input"] = {"type": v.input_type}
        key["input_type"] = v.input_type
        key["value"] = v.answer
        key["tolerance"] = v.tolerance
    if v.explanation:
        key["explanation"] = v.explanation
    # хеш содержания варианта: порядок вариантов ответа не учитывается — перемешанный тот же вопрос считается тем же
    content = {k: payload.get(k) for k in ("text", "code", "tables")} | {"options": sorted(payload.get("options") or [])}
    digest = hashlib.sha1(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    return payload, key, digest


def _norm_text(s: str) -> str:
    return " ".join(str(s).strip().lower().replace("ё", "е").replace(",", " ").split())


def check_answer(key: dict, response: Any) -> bool:
    """Проверка ответа на сервере. Ключ никогда не покидает сервер до завершения теста."""
    kind = key["kind"]
    if response is None:
        return False
    if kind == "single":
        try:
            return [int(response)] == key["correct"]
        except (TypeError, ValueError):
            return False
    if kind == "multi":
        try:
            return sorted({int(x) for x in response}) == key["correct"]
        except (TypeError, ValueError):
            return False
    if key.get("input_type") == "number":
        try:
            val = float(str(response).replace(",", ".").replace(" ", ""))
        except ValueError:
            return False
        tol = max(float(key.get("tolerance") or 0.0), 1e-9)
        return abs(val - float(key["value"])) <= tol + 1e-9
    accepted = key["value"] if isinstance(key["value"], list) else [key["value"]]
    r = _norm_text(response)
    return any(r == _norm_text(a) for a in accepted)


# ------------------------------------------------------------------ помощники для генераторов
def single(text: str, correct: str, distractors: list[str], **kw) -> Variant:
    opts = [(correct, True)] + [(d, False) for d in distractors if d != correct]
    return Variant(text=text, kind="single", options=opts, **kw)


def pick_distractors(rng: random.Random, correct, candidates: list, k: int = 3) -> list:
    pool = [c for c in dict.fromkeys(candidates) if c != correct]
    rng.shuffle(pool)
    return pool[:k]


def numeric_distractors(rng: random.Random, correct: int | float, spread: list[int | float], k: int = 3) -> list:
    cands = [correct + d for d in spread if d != 0]
    cands = [c for c in cands if c != correct and (not isinstance(correct, int) or c >= 0)]
    return pick_distractors(rng, correct, cands, k)


def statements_multi(rng: random.Random, stems: list[str], true_pool: list[str], false_pool: list[str], n: int = 5,
                     min_true: int = 1, max_true: int = 3, **kw) -> Variant:
    """«Выберите все верные утверждения» из пулов фактов: число комбинаций растёт комбинаторно,
    поэтому заучить «ответ» можно, только выучив сам предмет."""
    n_true = rng.randint(min_true, min(max_true, len(true_pool), n - 1))
    chosen = [(s, True) for s in rng.sample(true_pool, n_true)] + [(s, False) for s in rng.sample(false_pool, n - n_true)]
    return Variant(text=rng.choice(stems), kind="multi", options=chosen, hint="Отметьте все верные варианты", **kw)


def statements_single(rng: random.Random, stems: list[str], true_pool: list[str], false_pool: list[str], **kw) -> Variant:
    """«Какое утверждение верно?» — 1 факт из пула верных + 3 из пула неверных."""
    t = rng.choice(true_pool)
    fs = rng.sample(false_pool, 3)
    return single(rng.choice(stems), t, fs, **kw)


def scenario_single(rng: random.Random, scenarios: list[tuple[list[str], str]], answer_space: list[str], prefix: str = "", **kw) -> Variant:
    """Ситуационное задание: случайный сценарий (с перефразировками) → выбор из пространства ответов."""
    texts, correct = rng.choice(scenarios)
    distractors = pick_distractors(rng, correct, answer_space, 3)
    return single(prefix + rng.choice(texts), correct, distractors, **kw)


NAMES_EN = ["alice", "bob", "carol", "dave", "erin", "frank", "grace", "heidi", "ivan", "judy", "mallory", "oscar", "peggy", "trent", "victor", "walter"]
VAR_NAMES = ["items", "values", "data", "nums", "arr", "xs", "seq", "batch", "scores", "points"]
FUNC_NAMES = ["solve", "calc", "process", "transform", "compute", "walk", "visit", "run"]
