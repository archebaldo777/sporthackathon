"""NLP-разбор резюме и потребности; свойства функции ранжирования."""
from datetime import datetime, timezone

from app.catalog.skills import extract_skills, normalize_skill
from app.matching.scoring import Achievement, CandView, NeedView, score
from app.nlp.need_parser import parse_need
from app.nlp.resume_parser import parse_resume

RESUME = """Петров Иван Сергеевич
Senior Backend-разработчик
ivan.petrov@mail.ru  +7 (916) 123-45-67  t.me/ivanpetrov_dev  github.com/ivpetrov
Москва
Опыт работы 6 лет 2 месяца
Стек: Python, FastAPI, postgres, Docker, k8s, Kafka, Redis
Тимлид команды из 5 человек, менторство, работа в команде.
Образование: МГТУ им. Н. Э. Баумана, 2018
"""


def test_resume_parsing_extracts_core_fields():
    f = parse_resume(RESUME)
    assert f["full_name"]["value"] == "Петров Иван Сергеевич"
    assert f["email"]["value"] == "ivan.petrov@mail.ru"
    assert f["phone"]["value"].startswith("+7916")
    assert f["telegram"]["value"] == "@ivanpetrov_dev"
    assert f["experience_years"]["value"] == 6.2
    assert f["declared_grade"]["value"] == "senior"
    assert f["specialization"]["value"] == "backend"
    assert {"Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "Kafka", "Redis"} <= set(f["skills"]["value"])
    assert f["team_role"]["value"] == "teamlead"
    assert f["city"]["value"] == "Москва"


def test_skill_normalization():
    assert normalize_skill("postgres") == "PostgreSQL"
    assert normalize_skill("k8s") == "Kubernetes"
    assert "Go" in extract_skills("Пишем на Go и PostgreSQL")
    assert "Go" not in extract_skills("Let's go to the park")


def test_need_parsing():
    r = parse_need("Ищем Middle Python-разработчика в финтех. Обязательно: Python, PostgreSQL, Docker. Будет плюсом: Kafka. "
                   "Удалённо или гибрид. Зарплата 220 000 – 300 000 ₽")
    assert r["specialization"] == "backend" and r["grades"] == ["middle"]
    assert {"Python", "PostgreSQL", "Docker"} <= set(r["must_skills"]) and r["nice_skills"] == ["Kafka"]
    assert (r["salary_from"], r["salary_to"]) == (220000, 300000)
    assert set(r["work_formats"]) == {"remote", "hybrid"} and "fintech" in r["domains"]


def _cand(**kw):
    base = dict(id=1, spec="backend", grade="middle", theta=0.6, lang="python", declared_skills=["Python", "PostgreSQL", "Docker"],
                verified_skills=["Python"], topic_scores={"databases": {"theta": 0.7, "score": 0.75, "n": 3, "correct": 2}},
                salary_from=250000, salary_to=300000, work_formats=["remote"], search_status="active",
                last_activity_at=datetime.now(timezone.utc))
    base.update(kw)
    return CandView(**base)


NEED = NeedView(spec="backend", grades=["middle"], must_skills=["Python", "PostgreSQL", "Docker"], salary_from=220000, salary_to=300000,
                work_formats=["remote"])


def test_must_skill_gate_lowers_score():
    full = score(_cand(), NEED)["score"]
    missing = score(_cand(declared_skills=["Java"], verified_skills=[], lang="java"), NEED)["score"]
    assert full > missing + 15


def test_fsp_boosts_but_absence_not_excluded():
    no_fsp = score(_cand(), NEED)
    with_fsp = score(_cand(fsp_score=0.7, achievements=[Achievement("Чемпионат России", "product", "national", 2, "Призёр", 2025, ["Python"])]), NEED)
    assert no_fsp is not None and with_fsp["score"] > no_fsp["score"]


def test_fsp_discipline_relevance_to_need():
    """Идея организаторов: результат в профильной дисциплине весит больше, чем тот же результат в далёкой; ноль не даёт никакой."""
    from datetime import date

    from app.catalog.data import discipline_fit
    from app.fsp.scoring import fsp_score, result_weight

    def ach(disc, stack=()):
        return Achievement("Соревнование", disc, "national", 2, "Призёр", 2025, list(stack),
                           weight=result_weight(2, 40, None, date(2025, 9, 1)), prize=True)

    assert discipline_fit("security", "infosec") == "profile" and discipline_fit("robotics", "infosec") == "other"
    sec = NeedView(spec="infosec", grades=["middle"], must_skills=["OWASP"], salary_from=220000, salary_to=300000)
    cand = dict(spec="infosec", declared_skills=["OWASP"], verified_skills=["OWASP"], fsp_score=0.3)
    f = {d: next(c for c in score(_cand(achievements=[ach(d)], **cand), sec)["components"] if c["key"] == "F")["value"]
         for d in ("security", "robotics")}
    assert f["security"] > f["robotics"] > 0
    robo = score(_cand(achievements=[ach("robotics")], **cand), sec)
    assert any("непрофильн" in w for w in robo["warnings"])
    # стек решения совпал с навыками запроса — результат профильный, даже если дисциплина далёкая
    f_stack = next(c for c in score(_cand(achievements=[ach("robotics", ["OWASP"])], **cand), sec)["components"] if c["key"] == "F")["value"]
    assert f_stack == f["security"]
    # профиль: сила ФСП зависит от специализации кандидата
    rows = [type("A", (), dict(discipline="security", place=1, participants=30, percentile=None, event_date=date(2025, 5, 1)))()]
    assert fsp_score(rows, spec="infosec") > fsp_score(rows, spec="frontend") > 0


def test_other_category_excluded_and_explained():
    assert score(_cand(spec="frontend"), NEED) is None
    res = score(_cand(), NEED)
    assert res["relation"] == "target" and res["reasons"] and {c["key"] for c in res["components"]} == {"L", "S", "F", "A", "C", "D"}


def test_salary_above_budget_penalized_with_warning():
    pricey = score(_cand(salary_from=420000, salary_to=480000), NEED)
    assert pricey["score"] < score(_cand(), NEED)["score"] and any("выше вилки" in w for w in pricey["warnings"])


def test_resume_parsing_quality_on_labeled_sets():
    """Регресс качества разбора на размеченных вручную резюме (основной и отложенный наборы)."""
    from app.validation.resume_eval import evaluate_all

    r = evaluate_all()
    for part in ("dev", "holdout"):
        acc = r[part]["field_accuracy"]
        assert acc["email"] == 1.0 and acc["phone"] == 1.0 and acc["name"] >= 0.9 and acc["city"] >= 0.9
        assert acc["specialization"] >= 0.9 and acc["experience_years"] >= 0.85
        assert r[part]["skills"]["f1"] >= 0.92


def test_parser_handles_header_variants():
    from app.nlp.resume_parser import parse_resume

    p = parse_resume("Павел Орлов — DevOps-инженер\nЕкатеринбург\nGitHub: github.com/porlov\nОпыт: 2022 – наст. время, k8s, Terraform")
    assert p["full_name"]["value"] == "Павел Орлов" and p["city"]["value"] == "Екатеринбург"
    assert "Git" not in p["skills"]["value"] and "Kubernetes" in p["skills"]["value"]
    p = parse_resume("Flutter Developer\nАхмедов Руслан\nработал в розничной сети, пишу на реакте\nMoscow")
    assert p["full_name"]["value"] == "Ахмедов Руслан" and p["city"]["value"] == "Москва"
    assert "React" in p["skills"]["value"] and "Сети" not in p["skills"]["value"]
