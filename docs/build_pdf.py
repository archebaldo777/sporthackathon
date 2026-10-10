"""Сборка сводной сопроводительной документации в PDF: Markdown → HTML (фирменный стиль) → PDF (headless Chrome).

Запуск: backend/.venv/bin/python docs/build_pdf.py
"""
from __future__ import annotations

import base64
import datetime
import re
import subprocess
from pathlib import Path

import markdown

DOCS = Path(__file__).resolve().parent
ROOT = DOCS.parent
OUT_HTML = DOCS / "build" / "documentation.html"
OUT_PDF = DOCS / "Драфт — сопроводительная документация.pdf"
CHAPTERS = ["01-architecture.md", "02-testing-mechanics.md", "03-matching.md", "04-validation.md", "05-fsp-integration.md",
            "06-api.md", "07-libraries.md", "08-deployment.md", "09-security.md", "10-roadmap.md",
            "11-qa-session.md"]
CHROME = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "chromium", "chromium-browser"]

CSS = """
@page { size: A4; margin: 16mm 15mm 18mm 15mm; }
* { box-sizing: border-box; }
body { font-family: Inter, 'DejaVu Sans', Arial, sans-serif; color: #1B1C21; font-size: 10.3pt; line-height: 1.5; }
h1, h2, h3, h4 { font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace; letter-spacing: -0.01em; line-height: 1.25; }
h1 { font-size: 19pt; text-transform: uppercase; letter-spacing: .02em; margin: 0 0 10pt; padding-top: 4pt; border-bottom: 3px solid #402FFF; padding-bottom: 6pt; page-break-before: always; }
h2 { font-size: 13.5pt; margin: 18pt 0 6pt; color: #1B1C21; }
h3 { font-size: 11.5pt; margin: 14pt 0 4pt; color: #3424E0; }
p { margin: 5pt 0; }
a { color: #3424E0; text-decoration: none; }
code { font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace; font-size: 8.8pt; background: #F1EFFF; color: #1F1585; padding: 0.5pt 3pt; border-radius: 3pt; }
pre { background: #1B1C21; color: #EDEDED; padding: 9pt 11pt; border-radius: 7pt; font-size: 7pt; line-height: 1.45; white-space: pre-wrap; word-break: break-word; page-break-inside: avoid; }
pre code { background: none; color: inherit; padding: 0; font-size: inherit; }
table { width: 100%; border-collapse: collapse; margin: 7pt 0 10pt; font-size: 8.8pt; page-break-inside: auto; }
th { background: #F3F3F4; text-align: left; font-weight: 600; border-bottom: 1.5px solid #C9C2FF; padding: 4pt 6pt; }
td { border-bottom: 1px solid #DCDCE0; padding: 4pt 6pt; vertical-align: top; }
tr { page-break-inside: avoid; }
ul, ol { margin: 4pt 0 6pt; padding-left: 16pt; }
li { margin: 2pt 0; }
img { max-width: 100%; display: block; margin: 8pt auto; page-break-inside: avoid; }
blockquote { border-left: 3px solid #402FFF; margin: 8pt 0; padding: 2pt 10pt; color: #3A3C46; background: #F3F3F4; }
.cover { width: 210mm; height: 296.5mm; display: flex; flex-direction: column; justify-content: space-between; color: #fff;
  background: linear-gradient(160deg, #1B1C21 0%, #1B1C21 55%, #0A006B 100%); overflow: hidden;
  margin: 0; padding: 0; page-break-after: always; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.cover .strip { height: 11mm; background-repeat: repeat-x; background-position: left center; background-size: auto 100%; }
.cover .body { flex: 1; display: flex; flex-direction: column; justify-content: space-between; padding: 22mm 20mm 16mm; }
.cover .brand { font-family: 'TDAText', 'JetBrains Mono', monospace; letter-spacing: .06em; font-size: 22pt; }
.cover .brand span { color: #EC1D35; }
.cover .fsp { height: 11mm; width: auto; margin: 9mm 0 0; }
.cover h1 { border: 0; font-size: 28pt; color: #fff; page-break-before: avoid; margin-top: 26mm; }
.cover .sub { color: #C9C2FF; font-size: 13pt; max-width: 150mm; }
.cover .meta { color: #9B9C9E; font-size: 10pt; font-family: 'JetBrains Mono', monospace; }
.toc { page-break-after: always; }
.toc h1 { page-break-before: avoid; }
.toc ol { font-size: 12pt; line-height: 2; }
"""


FONT_DIR = ROOT / "frontend" / "public" / "fonts"
# фирменные шрифты ФСП — локальные файлы (как в приложении), без внешних CDN
FONTS = "".join(f"@font-face {{ font-family: '{fam}'; src: url('{(FONT_DIR / f).as_uri()}') format('woff'); font-weight: {w}; }}\n"
                for fam, f, w in (("Inter", "Inter-var.woff", "100 900"), ("JetBrains Mono", "JetBrainsMono-var.woff", "100 800"),
                                  ("TDAText", "TDAText.woff", "400")))


def data_uri(path: Path) -> str:
    mime = "image/svg+xml" if path.suffix == ".svg" else "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def md_to_html(text: str) -> str:
    # ссылки на соседние .md внутри PDF не нужны — оставляем только текст
    text = re.sub(r"\]\((\d\d-[\w-]+\.md)\)", "]", text)
    return markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists", "attr_list"])


def build() -> Path:
    parts = []
    titles = []
    for ch in CHAPTERS:
        src = (DOCS / ch).read_text()
        titles.append(re.search(r"^# (.+)$", src, re.M).group(1))
        html = md_to_html(src)
        html = re.sub(r'src="img/([^"]+)"', lambda m: f'src="{data_uri(DOCS / "img" / m.group(1))}"', html)
        parts.append(f"<section>{html}</section>")
    today = datetime.date.today().strftime("%d.%m.%Y")
    brand = ROOT / "frontend" / "public" / "brand"
    strip = f"background-image:url('{data_uri(brand / 'pattern-strip-dark.svg')}')"
    cover = f"""<div class="cover"><div class="strip" style="{strip}"></div><div class="body"><div>
<div class="brand">ДРАФТ<span>_</span></div><img class="fsp" src="{data_uri(brand / 'fsp-full-dark.svg')}" alt="ФСП">
<h1>Сопроводительная документация</h1>
<div class="sub">Цифровая платформа-агрегатор ИТ-вакансий с верифицированным профилем достижений участника
Федерации спортивного программирования: обратная механика подбора, адаптивное тестирование, интеграция с ФСП ID.</div></div>
<div class="meta">Хакатон ФСП · {today}<br>Репозиторий: README.md · API: /api/docs · Демо: docker compose up</div></div>
<div class="strip" style="{strip}"></div></div>"""
    items = "".join(f"<li>{re.sub(r'^[0-9]+[.] ', '', t)}</li>" for t in titles)  # номер даёт сам список
    toc = f"<div class='toc'><h1>Содержание</h1><ol>{items}</ol></div>"
    head = f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Драфт — документация</title><style>{FONTS}{CSS}'
    OUT_HTML.parent.mkdir(exist_ok=True)
    # обложка — отдельной страницей без полей (на всю страницу), остальное — с обычными полями; затем склеиваем
    cover_html = OUT_HTML.with_name("cover.html")
    cover_html.write_text(f"{head}@page {{ size: A4; margin: 0; }} body {{ margin: 0; }}</style></head><body>{cover}</body></html>")
    OUT_HTML.write_text(f"{head}</style></head><body>{toc}{''.join(parts)}</body></html>")
    chrome = next((c for c in CHROME if Path(c).exists() or subprocess.run(["which", c], capture_output=True).returncode == 0), None)
    if not chrome:
        raise SystemExit(f"Chrome не найден; HTML сохранён: {OUT_HTML}")
    pdfs = []
    for src in (cover_html, OUT_HTML):
        out = src.with_suffix(".pdf")
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={out}",
                        "--virtual-time-budget=8000", src.as_uri()], check=True, capture_output=True)
        pdfs.append(out)
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for f in pdfs:
        for page in PdfReader(f).pages[:1] if f == pdfs[0] else PdfReader(f).pages:
            writer.add_page(page)
    writer.add_metadata({"/Title": "Драфт — сопроводительная документация", "/Author": "Команда «Драфт»"})
    with open(OUT_PDF, "wb") as fh:
        writer.write(fh)
    for f in pdfs:
        f.unlink()
    return OUT_PDF


if __name__ == "__main__":
    print(build())
