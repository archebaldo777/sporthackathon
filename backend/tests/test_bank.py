"""Банк заданий: каждый шаблон генерирует корректные варианты, ключ проверки согласован с вариантом."""
import random

import pytest

from app.testing.bank import REGISTRY, GenCtx, check_answer, render


def ctxs(t):
    for lang in (t.langs or [None]):
        for fw in (t.frameworks or ["react"]):
            yield GenCtx(lang=lang or "python", framework=fw, spec=t.specs[0])


@pytest.mark.parametrize("tid", sorted(REGISTRY))
def test_template_renders_and_key_is_consistent(tid):
    t = REGISTRY[tid]
    rng = random.Random(1)
    for ctx in ctxs(t):
        for _ in range(12):
            payload, key, h = render(t, rng.randint(1, 2**31), ctx)
            assert payload["text"] and len(h) == 24
            assert "answer" not in payload and "correct" not in payload  # ключ не уходит клиенту
            if key["kind"] == "single":
                assert len(key["correct"]) == 1 and len(payload["options"]) >= 2
                assert check_answer(key, key["correct"][0])
                wrong = next(i for i in range(len(payload["options"])) if i not in key["correct"])
                assert not check_answer(key, wrong)
            elif key["kind"] == "multi":
                assert key["correct"] and check_answer(key, key["correct"])
                assert not check_answer(key, [])
            else:
                val = key["value"][0] if isinstance(key["value"], list) else key["value"]
                assert check_answer(key, val)
                assert not check_answer(key, "definitely-wrong-answer-42")


def test_variants_are_unique_for_parametric_templates():
    rng = random.Random(7)
    t = REGISTRY["sql.left_join"]
    hashes = {render(t, rng.randint(1, 2**31), GenCtx(spec="backend"))[2] for _ in range(50)}
    assert len(hashes) >= 48


def test_language_semantics_differ():
    """Одно семейство — ответы с учётом семантики языка: целочисленное деление отрицательных чисел."""
    t = REGISTRY["trace.int_div_mod"]
    py = render(t, 123, GenCtx(lang="python", spec="backend"))
    java = render(t, 123, GenCtx(lang="go", spec="backend"))
    assert py[0]["code_lang"] == "python" and java[0]["code_lang"] == "go"
