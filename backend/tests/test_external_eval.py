"""Оценка подбора на внешнем размеченном наборе пар «вакансия — кандидат»."""
import pytest

from app.validation.external_eval import EvalError, evaluate_external, norm_grade, norm_spec

PY_RESUME = "Backend-разработчик. Python, Django, PostgreSQL, Docker, Redis. Опыт работы 4 года."


def dataset() -> dict:
    cands = [
        # сильный и подтверждённый тестом
        {"id": "strong", "resume_text": PY_RESUME, "grade": "middle", "salary_from": 230000, "work_formats": ["remote"],
         "test": {"grade": "middle", "theta": 0.9, "verified_skills": ["Python", "SQL"]},
         "fsp": [{"discipline": "product", "level": "national", "place": 2, "participants": 120, "date": "2025-11-20"}]},
        # заявляет Middle, тест показал Junior
        {"id": "inflated", "resume_text": PY_RESUME + " Kafka, Kubernetes, gRPC, микросервисы.", "grade": "middle",
         "test": {"grade": "junior", "theta": -0.4, "verified_skills": ["Python"]}},
        # без теста и без ФСП — должен обрабатываться, а не падать
        {"id": "plain", "specialization": "Бэкенд", "grade": "мидл", "skills": ["Python", "PostgreSQL"], "salary_from": 210000},
        # другая специализация
        {"id": "front", "resume_text": "Frontend-разработчик: React, TypeScript, CSS", "grade": "middle",
         "test": {"grade": "middle", "theta": 0.6, "verified_skills": ["TypeScript"]}},
        # дорогой и только офис
        {"id": "pricey", "resume_text": PY_RESUME, "grade": "middle", "salary_from": 450000, "work_formats": ["office"],
         "test": {"grade": "middle", "theta": 0.5, "verified_skills": ["Python"]}},
    ]
    return {
        "vacancies": [{"id": "v1", "text": "Ищем Python backend-разработчика уровня Middle. Обязательно: Python, PostgreSQL. "
                                           "Будет плюсом: Docker.\n\nЗарплата 200–280 тыс. ₽, удалённо."}],
        "candidates": cands,
        "labels": [{"vacancy": "v1", "candidate": "strong", "relevance": 3}, {"vacancy": "v1", "candidate": "plain", "relevance": 2},
                   {"vacancy": "v1", "candidate": "inflated", "relevance": 1}, {"vacancy": "v1", "candidate": "front", "relevance": 0},
                   {"vacancy": "v1", "candidate": "pricey", "relevance": 1}],
    }


def test_aliases():
    assert norm_grade("Мидл") == "middle" and norm_grade("Senior") == "senior" and norm_grade("стажёр") == "intern"
    assert norm_spec("Бэкенд") == "backend" and norm_spec("Frontend") == "frontend" and norm_spec("Data Analyst") == "data_analyst"


def test_external_eval_ranks_verified_first():
    r = evaluate_external(dataset())
    assert r["vacancies_evaluated"] == 1 and r["scale"] == "graded_0_3" and r["threshold"] == 2
    v = r["per_vacancy"][0]
    assert v["parsed"]["specialization"] == "backend" and v["parsed"]["grades"] == ["middle"]
    top = [t["candidate"] for t in v["top"]]
    assert top[0] == "strong"
    assert "front" not in top  # другая специализация не попадает в подборку
    assert top.index("plain") < top.index("pricey")  # кандидат без теста и ФСП учитывается и обходит «дорогого»
    ours = r["summary"]["pool"]["ours"]
    assert ours["mrr"] == 1.0 and ours["recall@30"] == 1.0
    assert r["candidates_with_test"] == 4 and r["candidates_with_fsp"] == 1


def test_binary_labels_and_errors():
    d = dataset()
    for lb in d["labels"]:
        lb["relevance"] = 1 if lb["relevance"] >= 2 else 0
    r = evaluate_external(d)
    assert r["scale"] == "binary" and r["threshold"] == 1
    bad = dataset()
    bad["labels"].append({"vacancy": "v1", "candidate": "ghost", "relevance": 1})
    with pytest.raises(EvalError):
        evaluate_external(bad)
    with pytest.raises(EvalError):
        evaluate_external({"vacancies": [], "candidates": [], "labels": []})


def test_external_eval_api(client):
    r = client.post("/api/v1/validation/external-eval", json=dataset())
    assert r.status_code == 200, r.text
    assert r.json()["per_vacancy"][0]["top"][0]["candidate"] == "strong"
    r = client.post("/api/v1/validation/external-eval", json={"vacancies": []})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_dataset"
    ex = client.get("/api/v1/validation/external-eval/example").json()
    assert ex["vacancies"] and ex["candidates"] and ex["labels"]
    r = client.post("/api/v1/validation/external-eval", json=ex)
    assert r.status_code == 200
    s = r.json()["summary"]["pool"]
    assert s["ours"]["ndcg@10"] >= s["keyword_baseline"]["ndcg@10"]
