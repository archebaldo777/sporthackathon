"""Разбор резюме (PDF/текст): ФИО, контакты, стек, стаж, грейд, роли, софт-скиллы, специализация.

Пайплайн без внешних ML-сервисов (работает офлайн и укладывается в скромные ресурсы):
  1) извлечение текста из PDF (pypdf);
  2) правила и словари для контактов, дат, ролей, городов;
  3) онтология навыков с синонимами и нечётким сопоставлением (RapidFuzz);
  4) классификация специализации по «прототипам» — косинусной близости набора навыков к ядру специализации.
Каждое поле сопровождается оценкой уверенности, кандидат подтверждает результат перед сохранением.
"""
from __future__ import annotations

import io
import re
from datetime import date

from pypdf import PdfReader

from app.catalog.data import CITIES, CITY_ALIASES, DOMAINS, SOFT_SKILLS, SPECIALIZATIONS
from app.catalog.skills import extract_skills

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}")
TG = re.compile(r"(?:t\.me/|telegram[:\s]+@?|tg[:\s]+@?|(?<![\w.])@)([A-Za-z][\w]{4,31})", re.IGNORECASE)
GH = re.compile(r"github\.com/([\w-]+)", re.IGNORECASE)
MONTHS = {"янв": 1, "фев": 2, "мар": 3, "апр": 4, "мая": 5, "май": 5, "июн": 6, "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
          "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
NOW_WORDS = r"(?:(?:по\s+)?н\.?\s?в\.?|наст\.?\s?время|настоящее время|по настоящее время|сейчас|present|now|current)"
RANGE = re.compile(
    rf"(?:(?P<m1>[а-яa-z]{{3,9}}\.?|\d{{1,2}})[\s./]+)?(?P<y1>20\d\d|19\d\d)\s*[—–-]+\s*(?:(?P<now>{NOW_WORDS})|(?:(?P<m2>[а-яa-z]{{3,9}}\.?|\d{{1,2}})[\s./]+)?(?P<y2>20\d\d|19\d\d))",
    re.IGNORECASE,
)
EXPLICIT_EXP = [
    re.compile(r"опыт работы[^\d]{0,20}(\d{1,2})\s*(?:год\w*|лет)(?:\s*(?:и\s*)?(\d{1,2})\s*мес\w*)?", re.IGNORECASE),
    re.compile(r"опыт работы[^\d]{0,20}()(\d{1,2})\s*мес\w*", re.IGNORECASE),  # «Опыт работы 10 месяцев»
    re.compile(r"(?:work\s+)?experience[^\d\n]{0,10}(\d{1,2})\s*years?(?:\s*(?:and\s*)?(\d{1,2})\s*months?)?", re.IGNORECASE),
]
GRADE_WORDS = [("senior", "senior"), ("сеньор", "senior"), ("ведущий", "senior"), ("lead", "senior"), ("тимлид", "senior"), ("старший", "senior"),
               ("middle", "middle"), ("мидл", "middle"), ("junior", "junior"), ("джун", "junior"), ("младший", "junior"),
               ("стажер", "intern"), ("стажёр", "intern"), ("intern", "intern"), ("trainee", "intern")]
ROLE_WORDS = {
    "backend": ["backend", "бэкенд", "бекенд", "серверн"],
    "frontend": ["frontend", "фронтенд", "верстальщик", "ui-разработ"],
    "mobile": ["android", "ios", "мобильн", "flutter"],
    "ml": ["data scientist", "ml-инженер", "ml engineer", "machine learning", "машинного обучения", "nlp-инженер"],
    "data_analyst": ["аналитик данных", "data analyst", "продуктовый аналитик", "bi-аналитик", "bi аналитик"],
    "devops": ["devops", "sre", "системный администратор", "инженер инфраструктуры", "platform engineer"],
    "qa": ["qa", "тестировщик", "инженер по тестированию", "sdet", "автотестир"],
    "infosec": ["пентест", "безопасност", "security", "soc-аналитик", "аналитик soc", "appsec"],
}
TEAM_ROLES = {"teamlead": ["тимлид", "team lead", "teamlead", "руководитель группы"], "techlead": ["техлид", "tech lead", "архитектор"],
              "mentor": ["ментор", "наставни"], "pm": ["product owner", "менеджер продукта"]}
SOFT = {s: s.lower()[:7] for s in SOFT_SKILLS}
SOFT.update({"Работа в команде": "команд", "Менторство": "ментор", "Лидерство": "лидер", "Аналитическое мышление": "аналитическ"})
EDU_WORDS = ["университет", "институт", "академия", "мгу", "мфти", "вшэ", "итмо", "бауман", "мифи", "спбгу", "university", "колледж"]
NAME_SUFFIX = re.compile(r"(ов|ев|ёв|ин|ын|ский|цкий|ова|ева|ёва|ина|ына|ская|цкая|ко|ук|юк|ян|дзе|швили)$", re.IGNORECASE)
# строки-заголовки вида «Flutter Developer», «Site Reliability Engineer» не должны приниматься за ФИО
TITLE_HINT = re.compile(
    r"(developer|engineer|analyst|scientist|manager|tester|designer|architect|lead|intern|summary|experience|skills|contacts?|"
    r"резюме|разработчик|инженер|аналитик|тестировщик|специалист|программист|дизайнер|архитектор|стаж[её]р|студент|"
    r"junior|middle|senior|frontend|backend|fullstack|devops|data|python|java|golang|android|ios|опыт|навыки|контакты|о себе)",
    re.IGNORECASE)
NAME_SPLIT = re.compile(r"\s+[—–-]\s+|[,|·•;/():]")


def _city_pattern(name: str) -> str:
    """Город с типичными падежными окончаниями: «Москва» → «в Москве», «Пермь» → «из Перми»."""
    if re.fullmatch(r"[А-ЯЁ][а-яё]{3,}", name):
        return re.escape(re.sub(r"[аяеиоуыьй]$", "", name)) + r"[а-яё]{0,2}"
    return re.escape(name)


CITY_RE = [(re.compile(rf"(?<![\wА-Яа-яЁё]){_city_pattern(c)}(?![\wА-Яа-яЁё-])"), c) for c in CITIES] + \
          [(re.compile(rf"(?<![\w]){re.escape(a)}(?![\w-])"), c) for a, c in CITY_ALIASES.items()]


def find_city(text: str) -> str | None:
    """Город, упомянутый в тексте раньше других (обычно — в шапке резюме или вакансии)."""
    best = None
    for rx, city in CITY_RE:
        m = rx.search(text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), city)
    return best[1] if best else None


def pdf_to_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages[:10])


def _month(tok: str | None) -> int:
    if not tok:
        return 6
    tok = tok.lower().strip(".")
    if tok.isdigit():
        return max(1, min(12, int(tok)))
    return MONTHS.get(tok[:3], 6)


def experience_years(text: str, today: date | None = None) -> tuple[float | None, float]:
    today = today or date.today()
    for rx in EXPLICIT_EXP:
        m = rx.search(text)
        if m:
            return round(int(m.group(1) or 0) + (int(m.group(2) or 0) / 12), 1), 0.9
    spans = []
    for r in RANGE.finditer(text):
        y1 = int(r.group("y1"))
        start = y1 * 12 + _month(r.group("m1"))
        if r.group("now"):
            end = today.year * 12 + today.month
        elif r.group("y2"):
            end = int(r.group("y2")) * 12 + _month(r.group("m2"))
        else:
            continue
        if end > start and y1 >= 1990:
            spans.append((start, end))
    if not spans:
        return None, 0.0
    spans.sort()
    total, cur_s, cur_e = 0, *spans[0]
    for s, e in spans[1:]:
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += cur_e - cur_s
            cur_s, cur_e = s, e
    total += cur_e - cur_s
    return round(total / 12, 1), 0.7


def guess_name(lines: list[str]) -> tuple[str | None, float]:
    """ФИО: 2–3 слова с заглавной буквы в шапке резюме. Строка режется по разделителям («Павел Орлов — DevOps-инженер»,
    «Фёдоров Илья, 29 лет»); заголовки должностей, города и строки с цифрами пропускаются; кириллица приоритетнее латиницы."""
    latin = None
    for ln in lines[:8]:
        for part in NAME_SPLIT.split(ln):
            part = part.strip()
            if not part or TITLE_HINT.search(part) or "@" in part or re.search(r"\d", part) or find_city(part):
                continue
            words = re.sub(r"[^\wА-Яа-яЁё\s-]", " ", part).split()
            if not 2 <= len(words) <= 3:
                continue
            if all(w.isupper() and len(w) > 1 for w in words):  # «ALEXEY SMIRNOV»
                words = [w.capitalize() for w in words]
            if not all(w[:1].isupper() and w[1:].replace("-", "").islower() for w in words):
                continue
            if all(re.match(r"^[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?$", w) for w in words):
                return " ".join(words), (0.9 if any(NAME_SUFFIX.search(w) for w in words) else 0.8)
            if latin is None and all(re.match(r"^[A-Z][a-z]+$", w) for w in words):
                latin = " ".join(words)
    return (latin, 0.6) if latin else (None, 0.0)


def classify_specialization(skills: list[str], text: str) -> tuple[str | None, float, dict]:
    low = text.lower()
    scores = {}
    for code, info in SPECIALIZATIONS.items():
        core = set(info["core_skills"])
        overlap = len(core & set(skills)) / max(1, len(core)) ** 0.5
        role_hits = sum(low.count(w) for w in ROLE_WORDS.get(code, []))
        scores[code] = overlap + 0.6 * min(3, role_hits)
    best = max(scores, key=scores.get)
    total = sum(scores.values()) or 1
    conf = scores[best] / total if scores[best] > 0 else 0
    return (best if scores[best] > 0 else None), round(min(0.95, conf * 1.6), 2), {k: round(v, 2) for k, v in scores.items()}


def grade_guess(text: str, years: float | None) -> tuple[str | None, float]:
    head = text[:600].lower()
    for w, g in GRADE_WORDS:
        if re.search(rf"(?<![a-zа-яё]){w}", head):
            return g, 0.75
    if years is None:
        return None, 0.0
    if years < 1:
        return "intern", 0.5
    if years < 2:
        return "junior", 0.5
    if years < 5:
        return "middle", 0.5
    return "senior", 0.5


def parse_resume(text: str, today: date | None = None) -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    low = text.lower()
    name, name_conf = guess_name(lines)
    emails = EMAIL.findall(text)
    phones = PHONE.findall(text)
    tg = TG.search(text)
    gh = GH.search(text)
    city = find_city(text)
    # ссылки и адреса не должны превращаться в навыки (github.com/… → Git)
    skills = extract_skills(re.sub(r"\S+@\S+|(?:https?://)?(?:www\.)?[\w-]+\.(?:com|ru|io|me|org|dev|pro)/\S*|"
                                   r"\b(?:github|gitlab|linkedin|telegram|tg|e-?mail)\s*:", " ", text, flags=re.IGNORECASE))
    years, yconf = experience_years(text, today)
    spec, sconf, spec_scores = classify_specialization(skills, text)
    grade, gconf = grade_guess(text, years)
    roles = [code for code, words in ROLE_WORDS.items() if any(w in low for w in words)]
    team_role = next((r for r, ws in TEAM_ROLES.items() if any(w in low for w in ws)), None)
    soft = [s for s, stem in SOFT.items() if stem in low]
    domains = [code for code, title in DOMAINS.items() if any(w in low for w in _domain_words(code))]
    headline = next((ln for ln in lines[:12] if any(w in ln.lower() for ws in ROLE_WORDS.values() for w in ws) and len(ln) < 90), None)
    education = [ln for ln in lines if any(w in ln.lower() for w in EDU_WORDS)][:3]
    about_m = re.search(r"(?:о себе|about me|обо мне)[:\s]*\n?(.{30,600}?)(?:\n\s*\n|$)", text, re.IGNORECASE | re.DOTALL)
    return {
        "full_name": {"value": name, "confidence": name_conf},
        "email": {"value": emails[0] if emails else None, "confidence": 0.95 if emails else 0},
        "phone": {"value": re.sub(r"[^\d+]", "", phones[0]) if phones else None, "confidence": 0.9 if phones else 0},
        "telegram": {"value": "@" + tg.group(1) if tg else None, "confidence": 0.7 if tg else 0},
        "github": {"value": f"https://github.com/{gh.group(1)}" if gh else None, "confidence": 0.9 if gh else 0},
        "city": {"value": city, "confidence": 0.7 if city else 0},
        "headline": {"value": headline, "confidence": 0.6 if headline else 0},
        "skills": {"value": skills, "confidence": 0.85 if skills else 0},
        "experience_years": {"value": years, "confidence": yconf},
        "declared_grade": {"value": grade, "confidence": gconf},
        "specialization": {"value": spec, "confidence": sconf, "scores": spec_scores},
        "roles": {"value": roles, "confidence": 0.6 if roles else 0},
        "team_role": {"value": team_role, "confidence": 0.6 if team_role else 0},
        "soft_skills": {"value": soft, "confidence": 0.6 if soft else 0},
        "domains": {"value": domains, "confidence": 0.5 if domains else 0},
        "education": {"value": [{"place": e} for e in education], "confidence": 0.5 if education else 0},
        "about": {"value": about_m.group(1).strip() if about_m else None, "confidence": 0.5 if about_m else 0},
    }


def _domain_words(code: str) -> list[str]:
    return {
        "fintech": ["банк", "финтех", "fintech", "платеж", "кредит"], "ecommerce": ["e-commerce", "маркетплейс", "интернет-магазин", "ритейл"],
        "gamedev": ["геймдев", "gamedev", "игр"], "govtech": ["госуслуг", "госсектор", "government"], "edtech": ["edtech", "образоват", "обучени"],
        "healthtech": ["медицин", "healthtech", "клиник"], "telecom": ["телеком", "оператор связи"], "industrial": ["промышлен", "завод", "производств"],
        "media": ["медиа", "стриминг", "новост"], "logistics": ["логистик", "доставк", "транспорт"], "security": ["кибербез", "soc", "siem"],
        "it_services": ["аутсорс", "интегратор", "it-услуг"],
    }.get(code, [])
