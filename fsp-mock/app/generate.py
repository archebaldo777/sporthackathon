"""Генератор синтетического реестра ФСП (спортсмены, соревнования, результаты).

Запуск: python -m app.generate  → data/registry.json
Данные полностью синтетические и детерминированные (seed 2026). Поля с префиксом «_» — служебные:
скрытая «сила» спортсмена и основная специализация используются только сидером платформы для согласованности
синтетических кандидатов и никогда не отдаются через API реестра.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import uuid
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "registry.json"

FIRST_M = ["Александр", "Дмитрий", "Максим", "Иван", "Артём", "Никита", "Михаил", "Даниил", "Егор", "Андрей", "Кирилл", "Илья", "Алексей",
           "Матвей", "Тимофей", "Роман", "Владимир", "Ярослав", "Фёдор", "Глеб", "Арсений", "Лев", "Марк", "Степан", "Тимур", "Руслан"]
FIRST_F = ["Анна", "Мария", "Елена", "Дарья", "Алина", "Ксения", "Полина", "Виктория", "Екатерина", "София", "Арина", "Варвара",
           "Вероника", "Алиса", "Ульяна", "Милана", "Ева", "Кира", "Таисия", "Злата", "Диана", "Яна"]
LAST = ["Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", "Михайлов", "Новиков", "Фёдоров", "Морозов", "Волков",
        "Алексеев", "Лебедев", "Семёнов", "Егоров", "Павлов", "Козлов", "Степанов", "Николаев", "Орлов", "Андреев", "Макаров", "Никитин",
        "Захаров", "Зайцев", "Соловьёв", "Борисов", "Яковлев", "Григорьев", "Романов", "Воробьёв", "Сергеев", "Кузьмин", "Фролов",
        "Александров", "Дмитриев", "Королёв", "Гусев", "Киселёв", "Ильин", "Максимов", "Поляков", "Сорокин", "Виноградов", "Ковалёв",
        "Белов", "Медведев", "Антонов", "Тарасов", "Жуков", "Баранов", "Филиппов", "Комаров", "Давыдов", "Беляев", "Герасимов",
        "Богданов", "Осипов", "Сидоров", "Матвеев", "Титов", "Марков", "Миронов", "Крылов", "Куликов", "Карпов", "Власов", "Мельников"]
REGIONS = ["Москва", "Санкт-Петербург", "Республика Татарстан", "Новосибирская область", "Свердловская область", "Нижегородская область",
           "Самарская область", "Томская область", "Краснодарский край", "Пермский край", "Воронежская область", "Республика Башкортостан",
           "Приморский край", "Калининградская область", "Ростовская область"]
REGION_CITY = {"Москва": "Москва", "Санкт-Петербург": "Санкт-Петербург", "Республика Татарстан": "Казань", "Новосибирская область": "Новосибирск",
               "Свердловская область": "Екатеринбург", "Нижегородская область": "Нижний Новгород", "Самарская область": "Самара",
               "Томская область": "Томск", "Краснодарский край": "Краснодар", "Пермский край": "Пермь", "Воронежская область": "Воронеж",
               "Республика Башкортостан": "Уфа", "Приморский край": "Владивосток", "Калининградская область": "Калининград",
               "Ростовская область": "Ростов-на-Дону"}
SPEC_DISCIPLINES = {
    "backend": ["product", "product", "algorithmic"], "frontend": ["product", "product"], "mobile": ["product", "product", "robotics"],
    "ml": ["algorithmic", "product", "uav"], "data_analyst": ["product", "algorithmic"], "devops": ["product", "security"],
    "qa": ["product"], "infosec": ["security", "security", "algorithmic"],
}
SPEC_STACK = {
    "backend": [["Python", "FastAPI", "PostgreSQL", "Docker"], ["Go", "PostgreSQL", "Redis", "Docker"], ["Java", "Spring", "Kafka", "PostgreSQL"],
                ["Node.js", "TypeScript", "MongoDB"], ["Python", "Django", "Redis"]],
    "frontend": [["React", "TypeScript", "Vite"], ["Vue", "TypeScript"], ["React", "Next.js", "Redux"]],
    "mobile": [["Kotlin", "Jetpack Compose", "Android SDK"], ["Swift", "SwiftUI", "iOS SDK"], ["Flutter", "Dart"]],
    "ml": [["Python", "PyTorch", "Pandas"], ["Python", "CatBoost", "scikit-learn"], ["Python", "Computer Vision", "PyTorch"]],
    "data_analyst": [["Python", "Pandas", "SQL"], ["SQL", "ClickHouse", "Superset"]],
    "devops": [["Docker", "Kubernetes", "CI/CD"], ["Terraform", "Ansible", "Linux"]],
    "qa": [["Pytest", "Selenium", "Postman"], ["Автотесты", "Allure", "Python"]],
    "infosec": [["CTF", "Веб-безопасность", "Python"], ["Криптография", "Reverse Engineering", "CTF"]],
}
TEAM_ROLES = {"backend": "Backend-разработчик", "frontend": "Frontend-разработчик", "mobile": "Мобильный разработчик", "ml": "ML-инженер",
              "data_analyst": "Аналитик", "devops": "DevOps-инженер", "qa": "Тестировщик", "infosec": "Специалист по ИБ"}
DISC_NAMES = {"algorithmic": "алгоритмическому программированию", "product": "продуктовому программированию",
              "security": "программированию систем информационной безопасности", "robotics": "программированию робототехники",
              "uav": "программированию беспилотных авиационных систем"}
TEAM_WORDS = ["Byte", "Null", "Pointer", "Stack", "Kernel", "Lambda", "Vector", "Commit", "Deploy", "Hash", "Tensor", "Socket", "Patch", "Root"]


def _events(rng: random.Random) -> list[dict]:
    ev = []
    n = 0

    def add(name, disc, level, d: date, city, fmt, participants):
        nonlocal n
        n += 1
        ev.append({"event_id": f"EV-{d.year}-{n:03d}", "name": name, "discipline": disc, "level": level, "start_date": d.isoformat(),
                   "end_date": (d + timedelta(days=2)).isoformat(), "city": city, "format": fmt, "participants": participants,
                   "organizer": "Федерация спортивного программирования (демо-данные)"})

    for year in (2023, 2024, 2025, 2026):
        for disc in ("product", "algorithmic", "security"):
            add(f"Чемпионат России по {DISC_NAMES[disc]} {year}", disc, "national", date(year, rng.choice([10, 11]), rng.randint(5, 25)),
                "Москва", "team" if disc != "algorithmic" else "individual", rng.randint(300, 900))
        if year >= 2024:
            add(f"Кубок России по {DISC_NAMES['product']} {year}", "product", "national", date(year, 4, rng.randint(5, 25)), "Казань", "team",
                rng.randint(200, 600))
            for disc in ("robotics", "uav"):
                add(f"Всероссийские соревнования по {DISC_NAMES[disc]} {year}", disc, "national", date(year, 6, rng.randint(3, 25)),
                    "Иннополис", "team", rng.randint(80, 240))
        for okrug, city in [("ЦФО", "Москва"), ("СЗФО", "Санкт-Петербург"), ("ПФО", "Нижний Новгород"), ("СФО", "Новосибирск"),
                            ("УФО", "Екатеринбург")]:
            disc = rng.choice(["product", "algorithmic", "security"])
            add(f"Чемпионат {okrug} по {DISC_NAMES[disc]} {year}", disc, "interregional", date(year, rng.choice([2, 3, 9]), rng.randint(3, 25)),
                city, "team" if disc != "algorithmic" else "individual", rng.randint(80, 300))
        for reg in rng.sample(REGIONS, 5):
            disc = rng.choice(["product", "algorithmic", "security"])
            add(f"Чемпионат региона «{reg}» по {DISC_NAMES[disc]} {year}", disc, "regional", date(year, rng.choice([1, 2, 5, 12]), rng.randint(3, 25)),
                REGION_CITY[reg], "team" if disc != "algorithmic" else "individual", rng.randint(30, 150))
    add("Международные соревнования по спортивному программированию 2025", "algorithmic", "international", date(2025, 8, 18), "Москва",
        "individual", 520)
    today = date(2026, 10, 1)
    return [e for e in ev if date.fromisoformat(e["start_date"]) <= today]


def _sign(payload: str) -> str:
    return hashlib.sha256(("fsp-registry-demo-key:" + payload).encode()).hexdigest()[:40]


def generate(n_athletes: int = 300, seed: int = 2026) -> dict:
    rng = random.Random(seed)
    events = _events(rng)
    by_disc: dict[str, list[dict]] = {}
    for e in events:
        by_disc.setdefault(e["discipline"], []).append(e)
    athletes, results = [], []
    specs = list(SPEC_DISCIPLINES)
    spec_weights = [0.26, 0.15, 0.1, 0.12, 0.1, 0.1, 0.09, 0.08]
    used_names = set()
    for i in range(n_athletes):
        female = rng.random() < 0.3
        while True:
            first = rng.choice(FIRST_F if female else FIRST_M)
            last = rng.choice(LAST) + ("а" if female else "")
            if (first, last) not in used_names:
                used_names.add((first, last))
                break
        spec = rng.choices(specs, spec_weights)[0]
        latent = max(-2.5, min(2.8, rng.gauss(0.35, 0.95)))
        region = rng.choice(REGIONS)
        fsp_id = f"FSP-{rng.randint(1000000, 9999999)}"
        username = f"{_translit(first)[0]}.{_translit(last)}{rng.randint(1, 99)}".lower()
        rating = int(1200 + 350 * latent + rng.gauss(0, 120))
        rank = "МС" if rating > 2050 else "КМС" if rating > 1800 else "1 разряд" if rating > 1550 else "2 разряд" if rating > 1350 else None
        a = {
            "fsp_id": fsp_id, "sub": str(uuid.UUID(int=rng.getrandbits(128))), "username": username,
            "email": f"{username}@athletes.fsp.demo", "full_name": f"{first} {last}", "first_name": first, "last_name": last,
            "gender": "F" if female else "M", "birth_year": rng.randint(1994, 2008), "region": region, "city": REGION_CITY[region],
            "sport_rank": rank, "rating": rating, "club": f"Клуб спортивного программирования «{rng.choice(TEAM_WORDS)}»",
            "_latent": round(latent, 3), "_spec": spec, "_seed_linked": i >= 40,
        }
        athletes.append(a)
        n_res = rng.choices([1, 2, 3, 4, 5], [0.3, 0.3, 0.2, 0.12, 0.08])[0]
        discs = SPEC_DISCIPLINES[spec]
        used_events = set()
        for _ in range(n_res):
            disc = rng.choice(discs)
            pool = [e for e in by_disc.get(disc, []) if e["event_id"] not in used_events]
            # сильные спортсмены чаще выходят на всероссийский уровень
            if latent < 0.3:
                pool = [e for e in pool if e["level"] in ("regional", "interregional")] or pool
            if not pool:
                continue
            e = rng.choice(pool)
            used_events.add(e["event_id"])
            perf = latent + rng.gauss(0, 0.6) - {"regional": -0.4, "interregional": 0.0, "national": 0.6, "international": 1.0}[e["level"]]
            pct = 1 / (1 + math.exp(-1.6 * perf))
            pct = max(0.02, min(0.999, pct))
            units = e["participants"] // (4 if e["format"] == "team" else 1)
            place = max(1, int(round((1 - pct) * units)) + 1)
            team = f"{rng.choice(TEAM_WORDS)}{rng.choice(TEAM_WORDS)}" if e["format"] == "team" else None
            stack = rng.choice(SPEC_STACK[spec]) if disc == "product" else (
                ["C++", "Алгоритмы"] if disc == "algorithmic" and rng.random() < 0.6 else ["Python", "Алгоритмы"] if disc == "algorithmic" else
                ["CTF", "Веб-безопасность", "Криптография"] if disc == "security" else ["C++", "Python", "Computer Vision"])
            rid = f"R-{e['event_id']}-{fsp_id[-4:]}"
            payload = f"{rid}|{fsp_id}|{e['event_id']}|{place}"
            results.append({
                "result_id": rid, "event_id": e["event_id"], "fsp_id": fsp_id, "place": place, "units_total": units,
                "percentile": round(1 - (place - 1) / max(1, units), 3), "team_name": team,
                "team_role": TEAM_ROLES[spec] if team else None, "score": round(40 + 60 * pct, 1), "stack": stack,
                "diploma_url": f"https://fsp-registry.demo/diplomas/{rid}.pdf" if place <= 3 else None, "signature": _sign(payload),
            })
    demo = [a for a in athletes if not a["_seed_linked"]][:8]
    return {"generated_with_seed": seed, "events": events, "athletes": athletes, "results": results,
            "demo_logins": [{"username": a["username"], "full_name": a["full_name"], "fsp_id": a["fsp_id"]} for a in demo]}


def _translit(s: str) -> str:
    table = str.maketrans({"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "y",
                           "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
                           "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"})
    return s.lower().translate(table)


if __name__ == "__main__":
    data = generate()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"athletes={len(data['athletes'])} events={len(data['events'])} results={len(data['results'])} -> {OUT}")
