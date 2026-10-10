"""IRT и адаптивный тест: монотонность оценок, решения о грейде, контроль экспозиции."""
import random

from app.catalog.data import SPECIALIZATIONS
from app.testing import irt
from app.testing.bank import GenCtx
from app.testing.cat import CatConfig, simulate


def test_eap_monotonic_in_correct_answers():
    items = [irt.ItemParams(1.5, b, 0.1) for b in (-1, 0, 1, 2)]
    low, _, _ = irt.eap([(p, False) for p in items])
    high, _, _ = irt.eap([(p, True) for p in items])
    mid, _, _ = irt.eap([(items[0], True), (items[1], True), (items[2], False), (items[3], False)])
    assert low < mid < high


def test_information_peaks_near_difficulty():
    assert irt.information(1.0, 1.5, 1.0, 0.0) > irt.information(-1.5, 1.5, 1.0, 0.0)


def test_cat_separates_strong_and_weak():
    spec = "backend"
    ctx = GenCtx(lang="python", spec=spec)
    strong, _ = simulate(2.0, spec, ctx, "middle", SPECIALIZATIONS[spec]["blueprint"], random.Random(1), CatConfig())
    weak, _ = simulate(-1.5, spec, ctx, "middle", SPECIALIZATIONS[spec]["blueprint"], random.Random(2), CatConfig())
    assert strong.passed and strong.upgrade_grade == "senior"
    assert not weak.passed and weak.suggested_grade in ("intern", "junior")


def test_cat_respects_blueprint_and_length():
    spec = "data_analyst"
    _, st = simulate(0.3, spec, GenCtx(lang="python", spec=spec), "middle", SPECIALIZATIONS[spec]["blueprint"], random.Random(3), CatConfig())
    assert 8 <= len(st.answered) <= 22
    assert {x.competency for x in st.answered} == set(SPECIALIZATIONS[spec]["blueprint"])
    assert len({x.template_id for x in st.answered}) == len(st.answered)  # семейства не повторяются в попытке


def test_person_fit_flags_aberrant_pattern():
    items = [irt.ItemParams(1.8, b, 0.02) for b in (-2, -1.5, -1, 1.5, 2, 2.5, -1.8, 1.8)]
    normal = [(p, p.b < 0) for p in items]
    aberrant = [(p, p.b > 0) for p in items]
    assert irt.person_fit_lz(aberrant, 0.0) < irt.person_fit_lz(normal, 0.0)


def test_classification_stop_spends_items_on_borderline_cases():
    """Очевидные случаи завершаются быстрее, пограничные (θ у порога) получают больше заданий."""
    spec = "backend"
    bp = SPECIALIZATIONS[spec]["blueprint"]
    lengths = {"clear": [], "border": []}
    for i in range(30):
        ctx = GenCtx(lang="python", spec=spec)
        _, st = simulate(-1.6, spec, ctx, "middle", bp, random.Random(100 + i), CatConfig())
        lengths["clear"].append(len(st.answered))
        _, st = simulate(0.0, spec, ctx, "middle", bp, random.Random(200 + i), CatConfig())
        lengths["border"].append(len(st.answered))
    assert max(lengths["clear"] + lengths["border"]) <= 22 and min(lengths["clear"]) >= 8
    assert sum(lengths["border"]) / 30 > sum(lengths["clear"]) / 30 + 3
