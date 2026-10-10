"""Разбор текстового описания потребности/вакансии работодателя в структурированный запрос подбора."""
from __future__ import annotations

import re

from app.catalog.data import GRADE_ORDER, SPECIALIZATIONS
from app.catalog.skills import extract_skills
from app.nlp.resume_parser import ROLE_WORDS, _domain_words, classify_specialization, find_city

NICE_MARKERS = re.compile(r"(будет плюсом|плюсом будет|желательно|nice to have|приветствуется|преимуществом)", re.IGNORECASE)
SALARY = re.compile(
    r"(?:от\s*)?(\d{2,3}(?:[\s ]?\d{3})?)\s*(к|k|тыс\.?|000)?\s*(?:[—–-]|до)\s*(\d{2,3}(?:[\s ]?\d{3})?)\s*(к|k|тыс\.?|000)?",
    re.IGNORECASE,
)
# Суммы на платформе — gross (до вычета НДФЛ). Если в тексте указано «на руки», переводим по ставке НДФЛ 13%.
NET_MARKERS = re.compile(r"на\s+руки|чистыми|нетто|\bnet\b|после\s+вычета", re.IGNORECASE)
NDFL = 0.13
YEARS = re.compile(r"(?:от|не менее|более)\s*(\d{1,2})(?:[+-]|\s*-\s*\d)?\s*(?:лет|года|год)", re.IGNORECASE)


def _num(s: str, unit: str | None) -> int:
    v = int(re.sub(r"\D", "", s))
    if unit or v < 1000:
        v *= 1000 if v < 1000 else 1
    return v


def parse_need(text: str) -> dict:
    low = text.lower()
    # навыки «будет плюсом»: всё после маркера до конца абзаца
    nice_text = ""
    m = NICE_MARKERS.search(text)
    if m:
        tail = text[m.end():]
        nice_text = re.split(r"\n\s*\n", tail, maxsplit=1)[0]
    must_text = text.replace(nice_text, " ") if nice_text else text
    nice = extract_skills(nice_text)
    must = [s for s in extract_skills(must_text) if s not in nice]
    spec, conf, _ = classify_specialization(must + nice, text)
    grades = []
    for w, g in [("стаж", "intern"), ("intern", "intern"), ("junior", "junior"), ("джун", "junior"), ("middle", "middle"), ("мидл", "middle"),
                 ("senior", "senior"), ("сеньор", "senior"), ("ведущ", "senior"), ("lead", "senior"), ("старш", "senior")]:
        if w in low and g not in grades:
            grades.append(g)
    ym = YEARS.search(text)
    if not grades and ym:
        y = int(ym.group(1))
        grades = ["intern"] if y < 1 else ["junior"] if y < 2 else ["middle"] if y < 4 else ["senior"]
    grades = sorted(grades, key=GRADE_ORDER.index) or ["middle"]
    sal_from = sal_to = None
    salary_net = False
    sm = SALARY.search(text)
    if sm:
        a, b = _num(sm.group(1), sm.group(2) or sm.group(4)), _num(sm.group(3), sm.group(4))
        if 20000 <= a <= b <= 3_000_000:
            sal_from, sal_to = a, b
            # «на руки» в пределах той же фразы, что и сумма → пересчёт в gross
            if NET_MARKERS.search(text[max(0, sm.start() - 60):sm.end() + 60]):
                salary_net = True
                sal_from, sal_to = (round(x / (1 - NDFL) / 1000) * 1000 for x in (a, b))
    formats = []
    if re.search(r"удал[её]н|remote|из любого города", low):
        formats.append("remote")
    if re.search(r"гибрид|hybrid", low):
        formats.append("hybrid")
    if re.search(r"офис|office", low):
        formats.append("office")
    city = find_city(text)
    domains = [code for code in ["fintech", "ecommerce", "gamedev", "govtech", "edtech", "healthtech", "telecom", "industrial", "media",
                                 "logistics", "security", "it_services"] if any(w in low for w in _domain_words(code))]
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    title = first[:120] if len(first) < 120 else None
    return {
        "title": title,
        "specialization": spec or "backend",
        "specialization_confidence": conf,
        "grades": grades,
        "must_skills": must[:12],
        "nice_skills": nice[:10],
        "salary_from": sal_from,
        "salary_to": sal_to,
        "salary_converted_from_net": salary_net,
        "work_formats": formats,
        "city": city,
        "domains": domains,
        "spec_name": SPECIALIZATIONS.get(spec or "backend", {}).get("name"),
        "role_hits": [code for code, ws in ROLE_WORDS.items() if any(w in low for w in ws)],
    }
