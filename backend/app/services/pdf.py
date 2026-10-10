"""Стандартизированный PDF-профиль кандидата с QR-кодом проверки подлинности.

QR ведёт на /verify/<token>, где token = base64(user_id:issued_at).hmac — работодатель, получивший PDF вне
платформы, может убедиться, что категория и достижения действительно подтверждены платформой и ФСП.
"""
from __future__ import annotations

import base64
import io
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.catalog.data import DOMAINS, FSP_DISCIPLINES, FSP_LEVELS, GRADES, SPECIALIZATIONS, TEAM_ROLES, WORK_FORMATS, category_label
from app.core.config import settings
from app.core.security import sign
from app.models import CandidateProfile

# фирменный стиль ФСП: #402FFF, #EC1D35, графит #1B1C21; шрифты JetBrains Mono и TDAText (SIL OFL, app/assets/fonts)
BRAND = HexColor("#402FFF")
RED = HexColor("#EC1D35")
INK = HexColor("#1B1C21")
MUTED = HexColor("#62636B")
LINE = HexColor("#DCDCE0")
SOFT = HexColor("#F1EFFF")
ASSETS = Path(__file__).resolve().parents[1] / "assets"

FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf"),
]
MONO_CANDIDATES = [str(ASSETS / "fonts" / "JetBrainsMono-Bold.ttf"), "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"]
PIXEL_FONT = ASSETS / "fonts" / "TDAText.ttf"
FSP_LOGO = ASSETS / "brand" / "fsp-short-dark.png"
_fonts: tuple[str, str, str] | None = None
_pixel: str | None = None


def _pixel_font(fallback: str) -> str:
    """Акцентный шрифт ФСП для словесного знака «ДРАФТ»."""
    global _pixel
    if _pixel is None:
        _pixel = fallback
        if PIXEL_FONT.exists():
            pdfmetrics.registerFont(TTFont("Pixel", str(PIXEL_FONT)))
            _pixel = "Pixel"
    return _pixel


def _register_fonts() -> tuple[str, str, str]:
    global _fonts
    if _fonts:
        return _fonts
    regular = bold = mono = None
    custom = os.environ.get("PDF_FONT_DIR")
    pairs = ([(f"{custom}/regular.ttf", f"{custom}/bold.ttf")] if custom else []) + FONT_CANDIDATES
    for r, b in pairs:
        if os.path.exists(r) and os.path.exists(b):
            pdfmetrics.registerFont(TTFont("Body", r))
            pdfmetrics.registerFont(TTFont("BodyBold", b))
            regular, bold = "Body", "BodyBold"
            break
    for m in MONO_CANDIDATES:
        if os.path.exists(m):
            pdfmetrics.registerFont(TTFont("Mono", m))
            mono = "Mono"
            break
    regular = regular or "Helvetica"
    bold = bold or "Helvetica-Bold"
    _fonts = (regular, bold, mono or bold)
    return _fonts


def verify_token(user_id: int) -> str:
    raw = f"{user_id}:{int(time.time())}"
    b = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return f"{b}.{sign(raw)[:32]}"


def parse_verify_token(token: str) -> tuple[int, int] | None:
    try:
        b, sig = token.split(".", 1)
        raw = base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode()
        if sign(raw)[:32] != sig:
            return None
        uid, ts = raw.split(":")
        return int(uid), int(ts)
    except Exception:  # noqa: BLE001
        return None


class _Writer:
    def __init__(self, c: canvas.Canvas, fonts):
        self.c, (self.reg, self.bold, self.mono) = c, fonts
        self.w, self.h = A4
        self.y = self.h - 40
        self.margin = 40

    def ensure(self, need: float):
        if self.y - need < 60:
            self.c.showPage()
            self.y = self.h - 50

    def section(self, title: str):
        self.ensure(40)
        self.y -= 14
        self.c.setFillColor(BRAND)
        self.c.rect(self.margin, self.y - 2, 4, 14, stroke=0, fill=1)
        self.c.setFillColor(INK)
        self.c.setFont(self.mono, 11)
        self.c.drawString(self.margin + 10, self.y, title.upper())
        self.y -= 18

    def text(self, s: str, size=10, color=INK, bold=False, indent=0, leading=14, max_w=None):
        font = self.bold if bold else self.reg
        max_w = max_w or (self.w - 2 * self.margin - indent)
        for line in _wrap(s, font, size, max_w):
            self.ensure(leading)
            # шрифт задаём после возможного разрыва страницы: showPage() сбрасывает состояние canvas
            self.c.setFont(font, size)
            self.c.setFillColor(color)
            self.c.drawString(self.margin + indent, self.y, line)
            self.y -= leading

    def chips(self, items: list[tuple[str, bool]], size=9):
        x = self.margin
        self.ensure(22)
        for label, strong in items:
            tw = pdfmetrics.stringWidth(label, self.reg, size) + 16
            if x + tw > self.w - self.margin:
                x = self.margin
                self.y -= 20
                self.ensure(22)
            self.c.setFillColor(BRAND if strong else SOFT)
            self.c.roundRect(x, self.y - 5, tw, 16, 7, stroke=0, fill=1)
            self.c.setFillColor(white if strong else INK)
            self.c.setFont(self.reg, size)
            self.c.drawString(x + 8, self.y, label)
            x += tw + 6
        self.y -= 22


def _wrap(s: str, font: str, size: float, max_w: float) -> list[str]:
    out = []
    for para in (s or "").split("\n"):
        words, line = para.split(), ""
        for w in words:
            cand = f"{line} {w}".strip()
            if pdfmetrics.stringWidth(cand, font, size) <= max_w:
                line = cand
            else:
                if line:
                    out.append(line)
                line = w
        out.append(line)
    return out


def build_profile_pdf(cand: CandidateProfile) -> bytes:
    fonts = _register_fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Профиль кандидата {cand.public_code}")
    c.setAuthor("Платформа «Драфт»")
    W = _Writer(c, fonts)
    w, h = A4
    # шапка: словесный знак «ДРАФТ_» акцентным шрифтом ФСП и официальный логотип ФСП
    c.setFillColor(INK)
    c.rect(0, h - 150, w, 150, stroke=0, fill=1)
    pixel = _pixel_font(W.mono)
    c.setFillColor(white)
    c.setFont(pixel, 16)
    c.drawString(40, h - 42, "ДРАФТ")
    x = 40 + pdfmetrics.stringWidth("ДРАФТ", pixel, 16)
    c.setFillColor(RED)
    c.drawString(x, h - 42, "_")
    x += pdfmetrics.stringWidth("_", pixel, 16) + 10
    c.setFillColor(HexColor("#9B9C9E"))
    c.setFont(W.mono, 9)
    c.drawString(x, h - 41, "ВЕРИФИЦИРОВАННЫЙ ПРОФИЛЬ")
    if FSP_LOGO.exists():
        lw = 66
        c.drawImage(str(FSP_LOGO), w - 40 - 104 - 16 - lw, h - 49, width=lw, height=lw * 810 / 2397, mask="auto")
    c.setFillColor(white)
    c.setFont(W.bold, 22)
    c.drawString(40, h - 80, cand.full_name or f"Кандидат {cand.public_code}")
    c.setFont(W.reg, 11)
    c.setFillColor(HexColor("#C9C2FF"))
    c.drawString(40, h - 100, (cand.headline or SPECIALIZATIONS.get(cand.specialization or "", {}).get("name", ""))[:80])
    # бейдж категории
    label = category_label(cand.specialization, cand.grade)
    c.setFont(W.mono, 11)
    bw = pdfmetrics.stringWidth(label, W.mono, 11) + 24
    c.setFillColor(BRAND)
    c.roundRect(40, h - 135, bw, 22, 11, stroke=0, fill=1)
    c.setFillColor(white)
    c.drawString(52, h - 128, label)
    # QR
    token = verify_token(cand.user_id)
    url = f"{settings.public_url}/verify/{token}"
    qr = QrCodeWidget(url)
    b = qr.getBounds()
    size = 96
    d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0])
    d.add(qr)
    c.setFillColor(white)
    c.roundRect(w - 40 - size - 8, h - 140, size + 8, size + 8, 6, stroke=0, fill=1)
    renderPDF.draw(d, c, w - 40 - size - 4, h - 136)
    W.y = h - 175

    W.section("Категория и подтверждение")
    if cand.grade:
        conf = cand.grade_confirmed_at.strftime("%d.%m.%Y") if cand.grade_confirmed_at else "—"
        W.text(f"{SPECIALIZATIONS[cand.specialization]['name']} · грейд {GRADES[cand.grade]['name']} — подтверждён адаптивным тестом {conf}.")
        extra = []
        if cand.category_percentile is not None:
            extra.append(f"сила профиля выше, чем у {int(cand.category_percentile)}% кандидатов категории")
        if cand.theta is not None:
            extra.append(f"оценка способности θ = {cand.theta:+.2f} ± {cand.theta_se or 0:.2f}")
        if extra:
            W.text("; ".join(extra).capitalize() + ".", color=MUTED, size=9)
    else:
        W.text("Категория ещё не присвоена — кандидат не завершил тестирование.", color=MUTED)

    if cand.topic_scores:
        W.section("Результаты по компетенциям")
        for comp, ts in sorted(cand.topic_scores.items(), key=lambda kv: -kv[1]["score"]):
            W.ensure(20)
            c.setFont(W.reg, 9.5)
            c.setFillColor(INK)
            c.drawString(W.margin, W.y, ts["name"][:42])
            bar_x, bar_w = W.margin + 230, w - 2 * W.margin - 305
            c.setFillColor(LINE)
            c.roundRect(bar_x, W.y - 2, bar_w, 8, 4, stroke=0, fill=1)
            c.setFillColor(BRAND)
            c.roundRect(bar_x, W.y - 2, max(8, bar_w * ts["score"]), 8, 4, stroke=0, fill=1)
            c.setFillColor(MUTED)
            c.drawRightString(w - W.margin, W.y, f"{round(ts['score'] * 100)}%  ({ts['correct']}/{ts['n']})")
            W.y -= 16

    W.section("Навыки")
    verified = sorted({v["skill"] for v in (cand.verified_skills or [])})
    declared = [s for s in (cand.skills or []) if s not in verified]
    if verified:
        W.text("Подтверждены тестом:", size=9, color=MUTED)
        W.chips([(s, True) for s in verified])  # синяя плашка = подтверждено (знак ✓ есть не во всех шрифтах)
    if declared:
        W.text("Заявлены кандидатом:", size=9, color=MUTED)
        W.chips([(s, False) for s in declared[:24]])

    W.section("Достижения ФСП")
    if cand.achievements:
        for a in cand.achievements[:8]:
            place = f"{a.place} место из {a.participants}" if a.place and a.participants else a.result_title
            W.text(a.event_name if str(a.event_date.year) in a.event_name else f"{a.event_name} ({a.event_date.year})", bold=True, size=10)
            W.text(f"{FSP_DISCIPLINES.get(a.discipline, {}).get('name', a.discipline)} · {FSP_LEVELS.get(a.level, {}).get('name', a.level)} уровень · "
                   f"{place}" + (f" · команда «{a.team_name}», роль: {a.team_role}" if a.team_name else ""), size=9, color=MUTED)
        W.text(f"Данные получены из реестра ФСП по ФСП ID {cand.fsp_id}." if cand.fsp_id else "", size=8, color=MUTED)
    else:
        W.text("Истории участия в соревнованиях ФСП нет — категория определена тестированием.", color=MUTED, size=9)

    if cand.experience:
        W.section("Опыт работы")
        for e in cand.experience[:6]:
            period = f"{e.get('start', '')} — {e.get('end') or 'н.в.'}"
            W.text(f"{e.get('title', '')} · {e.get('company', '')}", bold=True)
            W.text(period, size=9, color=MUTED)
            if e.get("description"):
                W.text(e["description"][:400], size=9)
            W.y -= 4

    W.section("Дополнительно")
    facts = []
    if cand.experience_years is not None:
        facts.append(f"Стаж: {cand.experience_years:g} лет")
    if cand.team_role:
        facts.append(f"Роль в команде: {TEAM_ROLES.get(cand.team_role, cand.team_role)}")
    if cand.work_formats:
        facts.append("Формат: " + ", ".join(WORK_FORMATS.get(f, f).lower() for f in cand.work_formats))
    if cand.city:
        facts.append(f"Город: {cand.city}" + (" (готов к переезду)" if cand.relocation else ""))
    if cand.domains:
        facts.append("Отрасли: " + ", ".join(DOMAINS.get(d, d) for d in cand.domains))
    if cand.soft_skills:
        facts.append("Софт-скиллы: " + ", ".join(cand.soft_skills))
    for e in cand.education or []:
        facts.append("Образование: " + " ".join(str(v) for v in e.values() if v))
    for f in facts:
        W.text(f, size=9.5)
    contacts = [x for x in [cand.user.email if cand.user else None, cand.phone, cand.telegram, cand.github] if x]
    if contacts:
        W.section("Контакты")
        W.text(" · ".join(contacts), size=9.5)

    c.setFont(W.reg, 7.5)
    c.setFillColor(MUTED)
    c.drawString(40, 30, f"Сформировано {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC · проверка подлинности: {url[:90]}")
    c.save()
    return buf.getvalue()
