"""Лёгкая текстовая близость (TF-IDF по псевдо-основам слов) без тяжёлых ML-зависимостей.

Русская морфология грубо нормализуется усечением слова до 6 символов («разрабатывал», «разработка» → «разраб»),
навыки онтологии добавляются как отдельные токены. Используется как слабый сигнал «контекста» потребности.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from app.catalog.skills import extract_skills

TOKEN = re.compile(r"[a-zа-яё][a-zа-яё0-9+#.-]{2,}", re.IGNORECASE)
STOP = {"для", "что", "как", "это", "или", "при", "над", "под", "без", "наш", "наша", "наши", "команда", "команде", "работа", "работы",
        "опыт", "опытом", "задачи", "задач", "the", "and", "with", "for", "you", "our", "будет", "будешь", "нужно", "нужен", "ищем",
        "который", "которые", "также", "очень", "можно", "есть", "года", "лет", "год"}


def tokens(text: str) -> list[str]:
    out = []
    for m in TOKEN.finditer((text or "").lower().replace("ё", "е")):
        w = m.group(0).strip(".-")
        if w in STOP or len(w) < 3:
            continue
        out.append(w[:6])
    out += [f"skill:{s.lower()}" for s in extract_skills(text or "")]
    return out


class TfIdf:
    def __init__(self, docs: dict[int, str]):
        self.tf = {k: Counter(tokens(v)) for k, v in docs.items()}
        df: Counter = Counter()
        for c in self.tf.values():
            df.update(c.keys())
        n = max(1, len(docs))
        self.idf = {t: math.log((1 + n) / (1 + d)) + 1 for t, d in df.items()}
        self.vec = {k: self._weigh(c) for k, c in self.tf.items()}

    def _weigh(self, c: Counter) -> dict[str, float]:
        v = {t: (1 + math.log(f)) * self.idf.get(t, 1.0) for t, f in c.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def query(self, text: str) -> dict[int, float]:
        q = self._weigh(Counter(tokens(text)))
        return {k: sum(w * v.get(t, 0.0) for t, w in q.items()) for k, v in self.vec.items()}
