"""Нормализация навыков по онтологии: извлечение из текста, синонимы, связи навыков с компетенциями теста."""
from __future__ import annotations

import re
from functools import lru_cache

from rapidfuzz import fuzz, process

from app.catalog.data import COMPETENCIES, FRAMEWORK_SKILL, LANG_SKILL, PLATFORM_SKILL, SKILLS, SPECIALIZATIONS

# Короткие/двусмысленные алиасы распознаём только с учётом регистра (Go, JS…), чтобы не ловить обычные слова
CASE_SENSITIVE = {"Go": "Go", "JS": "JavaScript", "TS": "TypeScript", "ML": "Машинное обучение", "C#": "C#", "C++": "C++",
                  "PHP": "PHP", "SQL": "SQL", "NLP": "NLP", "CI/CD": "CI/CD", "K8s": "Kubernetes", "k8s": "Kubernetes",
                  "REST": "REST API", "CTF": "CTF", "AQA": "Автотесты", "DRF": "REST API"}
# дополнительные написания: множественное число, англоязычные формы, сленг, названия ролей
EXTRA_ALIASES = {
    "monitoring": "Мониторинг", "rest apis": "REST API", "реакт": "React", "тайпскрипт": "TypeScript", "джава": "Java",
    "реверс-инжиниринг": "Reverse Engineering", "reverse-engineering": "Reverse Engineering",
    "сетевое администрирование": "Сети", "компьютерных сетей": "Сети", "сетевых технологий": "Сети",
    "продуктовый аналитик": "Продуктовая аналитика", "product analyst": "Продуктовая аналитика",
    "a/b tests": "A/B-тестирование", "a/b test": "A/B-тестирование", "a/b-тестов": "A/B-тестирование",
    "automation qa": "Автотесты", "qa automation": "Автотесты",
    "кубер": "Kubernetes", "докер": "Docker", "django rest framework": "REST API", "сетевое программирование": "Сети",
    "продуктовых метрик": "Продуктовая аналитика", "unit economics": "Продуктовая аналитика", "баг-репорты": "Процессы QA",
    "баг-репортов": "Процессы QA", "разбор инцидентов": "Анализ инцидентов", "расследование инцидентов": "Анализ инцидентов",
    "криптографическая защита": "Криптография", "скзи": "Криптография",
}
UNSAFE = {"go", "js", "ts", "ml", "dl", "tf", "cv", "sh", "ci", "cd", "c", "го", "си", "плюсы", "py", "elk", "ios", "rest", "node",
          "flow", "compose", "mvp", "zap", "burp", "reverse", "ctf", "a/b", "ab testing", "jira", "сети"}


@lru_cache
def _alias_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for name in SKILLS:  # каноническое имя навыка важнее чужого алиаса (Vite ≠ «vite» как алиас Webpack)
        if name.lower() not in UNSAFE and len(name) > 1:
            idx[name.lower()] = name
    for alias, name in EXTRA_ALIASES.items():
        idx.setdefault(alias, name)
    for name, s in SKILLS.items():
        for alias in s["aliases"]:
            key = alias.lower()
            if key in UNSAFE or len(key) <= 1:
                continue
            idx.setdefault(key, name)
    # безопасные длинные формы для «опасных» алиасов
    idx.update({"golang": "Go", "node.js": "Node.js", "nodejs": "Node.js", "ios sdk": "iOS SDK", "ios-разработка": "iOS SDK",
                "a/b-тест": "A/B-тестирование", "a/b тест": "A/B-тестирование", "a/b-тестирование": "A/B-тестирование",
                "rest api": "REST API", "restful": "REST API", "jetpack compose": "Jetpack Compose", "burp suite": "Burp Suite",
                "capture the flag": "CTF", "reverse engineering": "Reverse Engineering"})
    return idx


def _key_pattern(key: str) -> str:
    # однословные кириллические алиасы — с падежными окончаниями: «на реакте», «в постгресе», «микросервисами»
    if re.fullmatch(r"[а-яё]{5,}", key):
        return re.escape(re.sub(r"[аяеиоуыьй]{1,2}$", "", key)) + r"[а-яё]{0,3}"
    return re.escape(key)


@lru_cache
def _alias_regex() -> re.Pattern:
    keys = sorted(_alias_index(), key=len, reverse=True)
    long_body = "|".join(_key_pattern(k) for k in keys if len(k) >= 3)
    short_body = "|".join(re.escape(k) for k in keys if len(k) < 3)
    # длинные алиасы допускают дефис и слеш рядом («MLOps-пайплайны», «HTML/CSS»); короткие — только целым словом
    parts = [rf"(?<![\w+#.])(?:{long_body})(?![\w+#])"]
    if short_body:
        parts.append(rf"(?<![\w+#/.-])(?:{short_body})(?![\w+#-])")
    return re.compile("|".join(parts), re.IGNORECASE)


def _lookup(token: str) -> str | None:
    idx = _alias_index()
    t = token.lower()
    if t in idx:
        return idx[t]
    for k, v in idx.items():  # словоформа кириллического алиаса
        if re.fullmatch(r"[а-яё]{5,}", k) and re.fullmatch(_key_pattern(k), t):
            return v
    return None


def extract_skills(text: str) -> list[str]:
    """Навыки онтологии, упомянутые в тексте (в порядке первого упоминания)."""
    if not text:
        return []
    found: list[str] = []
    for m in _alias_regex().finditer(text):
        name = _lookup(m.group(0))
        if name and name not in found:
            found.append(name)
    for token, name in CASE_SENSITIVE.items():
        if re.search(rf"(?<![\w+#]){re.escape(token)}(?![\w+#])", text) and name not in found:
            found.append(name)
    return found


def normalize_skill(raw: str) -> str | None:
    """Приводит произвольное написание навыка к каноническому имени (точное совпадение алиаса или нечёткий поиск)."""
    if not raw:
        return None
    s = raw.strip()
    if s in SKILLS:
        return s
    if s in CASE_SENSITIVE:
        return CASE_SENSITIVE[s]
    idx = _alias_index()
    if s.lower() in idx:
        return idx[s.lower()]
    best = process.extractOne(s.lower(), list(idx.keys()), scorer=fuzz.WRatio, score_cutoff=90)
    return idx[best[0]] if best else None


def normalize_list(items: list[str]) -> list[str]:
    out: list[str] = []
    for it in items or []:
        n = normalize_skill(it)
        if n and n not in out:
            out.append(n)
    return out


def related(a: str, b: str) -> float:
    """Близость двух навыков: 1 — совпадают, 0.6 — связаны в онтологии, 0 — не связаны."""
    if a == b:
        return 1.0
    sa, sb = SKILLS.get(a), SKILLS.get(b)
    if sa and b in sa["related"]:
        return 0.6
    if sb and a in sb["related"]:
        return 0.6
    return 0.0


# Навык → (компетенция, коэффициент доверия), если навык подтверждается не напрямую, а через смежную тему
INDIRECT: dict[str, tuple[str, float]] = {
    "PostgreSQL": ("databases", 0.85), "MySQL": ("databases", 0.85), "ClickHouse": ("databases", 0.7), "Oracle": ("databases", 0.75),
    "Redis": ("architecture", 0.6), "Kafka": ("architecture", 0.6), "RabbitMQ": ("architecture", 0.6), "gRPC": ("web", 0.6),
    "GraphQL": ("web", 0.6), "TypeScript": ("lang", 0.85), "Node.js": ("lang", 0.75), "Django": ("lang", 0.6), "FastAPI": ("lang", 0.6),
    "Flask": ("lang", 0.6), "Spring": ("lang", 0.6), "Laravel": ("lang", 0.6), "Pandas": ("lang", 0.7), "NumPy": ("lang", 0.6),
    "PyTorch": ("ml_theory", 0.7), "TensorFlow": ("ml_theory", 0.7), "Deep Learning": ("ml_theory", 0.8), "CatBoost": ("ml_theory", 0.8),
    "NLP": ("ml_theory", 0.5), "Computer Vision": ("ml_theory", 0.5), "Terraform": ("ci_cd", 0.7), "Ansible": ("ci_cd", 0.7),
    "Prometheus": ("sre", 0.85), "Grafana": ("sre", 0.85), "Nginx": ("networking", 0.5), "Pytest": ("lang", 0.6),
    "Selenium": ("qa_process", 0.5), "Автотесты": ("qa_process", 0.6), "Postman": ("web", 0.8), "JMeter": ("performance", 0.9),
    "Allure": ("qa_process", 0.6), "Ручное тестирование": ("test_design", 0.8), "Burp Suite": ("web_security", 0.85),
    "Пентест": ("web_security", 0.85), "CTF": ("web_security", 0.6), "Jetpack Compose": ("mobile_platform", 0.85),
    "SwiftUI": ("mobile_platform", 0.85), "Coroutines": ("mobile_platform", 0.7), "Redux": ("framework", 0.7),
    "Next.js": ("framework", 0.7), "RxJS": ("framework", 0.7), "Power BI": ("visualization", 0.8), "Tableau": ("visualization", 0.8),
    "Superset": ("visualization", 0.8), "Excel": ("visualization", 0.5), "Метрики ML": ("ml_math", 1.0), "Облака": ("containers", 0.5),
    "Webpack": ("browser", 0.5), "Vite": ("browser", 0.5), "Jest": ("framework", 0.5), "ООП": ("lang", 0.6),
    "Паттерны проектирования": ("architecture", 0.7), "Clean Architecture": ("architecture", 0.7), "Spark": ("databases", 0.5),
    "ETL": ("databases", 0.6), "Airflow": ("databases", 0.4),
}


def skill_competency(skill: str, spec: str | None = None, lang: str | None = None, framework: str | None = None) -> tuple[str, float] | None:
    """В какой компетенции теста проверяется навык (с учётом трека кандидата) и с каким доверием."""
    blueprint = SPECIALIZATIONS.get(spec or "", {}).get("blueprint", {})
    if skill in LANG_SKILL.values():
        if lang and LANG_SKILL.get(lang) == skill:
            return ("lang", 1.0)
        return None
    if skill in FRAMEWORK_SKILL.values():
        return ("framework", 1.0) if framework and FRAMEWORK_SKILL.get(framework) == skill else None
    if skill in PLATFORM_SKILL.values():
        return ("mobile_platform", 1.0) if lang and PLATFORM_SKILL.get(lang) == skill else None
    candidates = [c for c, info in COMPETENCIES.items() if skill in info["verifies"]]
    for c in candidates:
        if not blueprint or c in blueprint:
            return (c, 1.0)
    if skill == "Docker" and "containers" in blueprint:
        return ("containers", 1.0)
    if skill == "Git" and "ci_cd" in blueprint:
        return ("ci_cd", 1.0)
    if skill in INDIRECT:
        comp, k = INDIRECT[skill]
        if comp == "lang":
            target = {"TypeScript": "javascript", "Node.js": "javascript", "Django": "python", "FastAPI": "python", "Flask": "python",
                      "Pandas": "python", "NumPy": "python", "Pytest": "python", "Spring": "java", "Laravel": "php"}.get(skill)
            if target and lang and target != lang:
                return None
        if not blueprint or comp in blueprint:
            return (comp, k)
    return None


def infer_lang(skills: list[str], spec: str) -> str | None:
    langs = SPECIALIZATIONS.get(spec, {}).get("langs", [])
    inv = {v: k for k, v in LANG_SKILL.items()}
    for s in skills:
        code = inv.get(s)
        if s == "TypeScript":
            code = "javascript"
        if s in ("Android SDK", "Jetpack Compose"):
            code = "kotlin"
        if s in ("iOS SDK", "SwiftUI"):
            code = "swift"
        if s == "Flutter":
            code = "dart"
        if code in langs:
            return code
    return langs[0] if langs else None


def infer_framework(skills: list[str]) -> str | None:
    inv = {v: k for k, v in FRAMEWORK_SKILL.items()}
    for s in skills:
        if s in inv:
            return inv[s]
        if s in ("Next.js", "Redux"):
            return "react"
    return None
