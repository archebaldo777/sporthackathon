"""Демо-видео работы прототипа: браузер сам проходит сквозные сценарии кандидата и работодателя, на экране — подписи.

Запуск при работающем стенде (frontend :5173, backend :8000, fsp-mock :8081) на свежезаполненной БД:
    backend/.venv/bin/pip install imageio-ffmpeg
    backend/.venv/bin/python docs/demo_video.py            → docs/demo/draft-demo.mp4

Запись — через DevTools Protocol (Page.startScreencast), кадры склеиваются ffmpeg с исходными интервалами.
Внимание: сценарий меняет состояние демо-данных (новый кандидат проходит тест, приглашения принимаются).
"""
from __future__ import annotations

import base64
import json
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.db import SessionLocal  # noqa: E402
from app.models import TestItem  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
APP = "http://localhost:5173"
API = f"{APP}/api/v1"
OUT = ROOT / "docs" / "demo" / "draft-demo.mp4"
W, H = 1440, 900
PORT = 9344

OVERLAY = r"""
(() => {
  if (window.__say) return;
  const CSS = `
    #demo-cap{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:2147483647;max-width:1060px;width:max-content;
      background:rgba(14,14,18,.93);color:#fff;border-radius:16px;padding:14px 22px 14px 16px;display:flex;gap:14px;align-items:center;
      font:500 19px/1.4 Inter,system-ui,sans-serif;box-shadow:0 18px 50px -12px rgba(0,0,0,.55);transition:opacity .35s}
    #demo-cap b{font:700 12px/1 'JetBrains Mono',monospace;letter-spacing:.08em;text-transform:uppercase;color:#fff;background:#402FFF;
      border-radius:8px;padding:7px 9px;white-space:nowrap}
    #demo-cur{position:fixed;z-index:2147483646;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;
      border:3px solid #402FFF;background:rgba(64,47,255,.18);pointer-events:none;transition:left .55s ease,top .55s ease}
    .demo-ripple{position:fixed;z-index:2147483645;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;background:rgba(236,29,53,.45);
      pointer-events:none;animation:demoR .6s ease-out forwards}
    @keyframes demoR{to{transform:scale(4);opacity:0}}`;
  const ensure = () => {
    if (!document.body) return null;
    if (!document.getElementById('demo-css')) { const s = document.createElement('style'); s.id = 'demo-css'; s.textContent = CSS; document.head.appendChild(s); }
    let cap = document.getElementById('demo-cap');
    if (!cap) { cap = document.createElement('div'); cap.id = 'demo-cap'; cap.style.opacity = 0; document.body.appendChild(cap); }
    let cur = document.getElementById('demo-cur');
    if (!cur) { cur = document.createElement('div'); cur.id = 'demo-cur'; cur.style.left = '50%'; cur.style.top = '45%'; document.body.appendChild(cur); }
    return { cap, cur };
  };
  window.__say = (step, text) => {
    try { sessionStorage.setItem('demo.cap', JSON.stringify([step, text])); } catch (e) {}
    const el = ensure(); if (!el) return;
    el.cap.innerHTML = (step ? `<b>${step}</b>` : '') + `<span>${text}</span>`; el.cap.style.opacity = text ? 1 : 0;
  };
  window.__move = (x, y) => { const el = ensure(); if (el) { el.cur.style.left = x + 'px'; el.cur.style.top = y + 'px'; } };
  window.__ripple = (x, y) => { if (!document.body) return; const r = document.createElement('div'); r.className = 'demo-ripple';
    r.style.left = x + 'px'; r.style.top = y + 'px'; document.body.appendChild(r); setTimeout(() => r.remove(), 700); };
  const restore = () => { try { const s = JSON.parse(sessionStorage.getItem('demo.cap') || 'null'); if (s) window.__say(s[0], s[1]); else ensure(); } catch (e) {} };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', restore); else restore();
})();
"""


class Browser:
    def __init__(self, frames_dir: Path):
        self.tmp = tempfile.mkdtemp()
        self.proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={self.tmp}",
                                      "--hide-scrollbars", f"--window-size={W},{H}", "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
                ws = next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        self.ws = connect(ws, max_size=64 * 1024 * 1024)
        self.n = 0
        self.lock = threading.Lock()
        self.waiting: dict[int, list] = {}
        self.frames_dir = frames_dir
        self.frames: list[tuple[float, Path]] = []
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            for raw in self.ws:
                msg = json.loads(raw)
                if "id" in msg and msg["id"] in self.waiting:
                    slot = self.waiting.pop(msg["id"])
                    slot[1] = msg
                    slot[0].set()
                elif msg.get("method") == "Page.screencastFrame":
                    p = msg["params"]
                    path = self.frames_dir / f"{len(self.frames):06d}.jpg"
                    path.write_bytes(base64.b64decode(p["data"]))
                    self.frames.append((p["metadata"]["timestamp"], path))
                    self.call("Page.screencastFrameAck", wait=False, sessionId=p["sessionId"])
        except Exception:  # noqa: BLE001 — соединение закрыто
            pass

    def call(self, method: str, wait: bool = True, **params):
        with self.lock:
            self.n += 1
            mid = self.n
        slot = [threading.Event(), None]
        if wait:
            self.waiting[mid] = slot
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        if not wait:
            return None
        slot[0].wait(30)
        return (slot[1] or {}).get("result", {})

    def js(self, expr: str):
        r = self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        return (r.get("result") or {}).get("value")

    def close(self):
        self.proc.terminate()
        shutil.rmtree(self.tmp, ignore_errors=True)


class Demo:
    def __init__(self, b: Browser):
        self.b = b

    # ------------------------------------------------------------ примитивы
    def pause(self, s: float):
        time.sleep(s)

    def wait(self, cond: str, timeout: float = 12) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.b.js(f"!!({cond})"):
                return True
            time.sleep(0.25)
        print("  ! не дождались:", cond[:80])
        return False

    def nav(self, path: str, wait_for: str = "document.querySelector('main, h1')"):
        self.b.call("Page.navigate", url=path if path.startswith("http") else APP + path)
        time.sleep(0.8)
        self.wait(f"document.readyState === 'complete' && {wait_for}")
        time.sleep(0.6)

    def say(self, step: str, text: str):
        self.b.js(f"window.__say && window.__say({json.dumps(step)}, {json.dumps(text)})")

    def scroll(self, y: int, pause: float = 1.4):
        self.b.js(f"window.scrollTo({{top: {y}, behavior: 'smooth'}})")
        time.sleep(pause)

    def scroll_to(self, text: str, sel: str = "h1,h2,h3", offset: int = 110, pause: float = 1.4):
        self.b.js(f"""(() => {{ const el = [...document.querySelectorAll({json.dumps(sel)})].find(e => e.textContent.includes({json.dumps(text)}));
            if (el) window.scrollTo({{top: el.getBoundingClientRect().top + scrollY - {offset}, behavior: 'smooth'}}); }})()""")
        time.sleep(pause)

    def _click_js(self, finder: str) -> bool:
        pos = self.b.js(f"""(() => {{ const el = {finder}; if (!el) return null; el.scrollIntoView({{block: 'center', behavior: 'smooth'}});
            return true; }})()""")
        if not pos:
            return False
        time.sleep(0.5)
        xy = self.b.js(f"(() => {{ const el = {finder}; const r = el.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }})()")
        self.b.js(f"window.__move && window.__move({xy[0]}, {xy[1]})")
        time.sleep(0.65)
        self.b.js(f"(() => {{ window.__ripple && window.__ripple({xy[0]}, {xy[1]}); const el = {finder}; el.click(); }})()")
        time.sleep(0.5)
        return True

    def click(self, text: str, sel: str = "button, a", exact: bool = False, within: str = "document", nth: int = 0) -> bool:
        cmp = f"e.textContent.trim() === {json.dumps(text)}" if exact else f"e.textContent.includes({json.dumps(text)})"
        finder = (f"[...{within}.querySelectorAll({json.dumps(sel)})].filter(e => {cmp} && e.offsetParent !== null && !e.disabled)[{nth}]")
        ok = self._click_js(finder)
        if not ok:
            print("  ! не нашли кнопку:", text)
        return ok

    def click_sel(self, css: str, nth: int = 0) -> bool:
        ok = self._click_js(f"document.querySelectorAll({json.dumps(css)})[{nth}]")
        if not ok:
            print("  ! не нашли элемент:", css)
        return ok

    def type(self, css: str, text: str, delay: float = 0.035):
        """Посимвольный ввод в React-поле (через нативный setter + событие input)."""
        self._click_js(f"document.querySelector({json.dumps(css)})")
        acc = ""
        for ch in text:
            acc += ch
            self.b.js(f"""(() => {{ const el = document.querySelector({json.dumps(css)}); const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement : HTMLInputElement;
                Object.getOwnPropertyDescriptor(proto.prototype, 'value').set.call(el, {json.dumps(acc)});
                el.dispatchEvent(new Event('input', {{bubbles: true}})); }})()""")
            time.sleep(delay)

    def login(self, email: str):
        req = urllib.request.Request(f"{API}/auth/login", data=json.dumps({"email": email, "password": "Demo2026!"}).encode(),
                                     headers={"Content-Type": "application/json"})
        t = json.loads(urllib.request.urlopen(req).read())
        self.b.js(f"localStorage.setItem('draft.access', {json.dumps(t['access_token'])}); localStorage.setItem('draft.refresh', {json.dumps(t['refresh_token'])})")
        return t["access_token"]

    def logout(self):
        self.b.js("localStorage.removeItem('draft.access'); localStorage.removeItem('draft.refresh')")


def api(token: str, method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    return json.loads(urllib.request.urlopen(req).read())


def answer_for(item_id: int, correct: bool = True):
    with SessionLocal() as db:
        key = db.get(TestItem, item_id).answer_key
    if not correct:  # правдоподобная ошибка: соседнее число или другой вариант
        if key["kind"] == "input":
            v = key["value"][0] if isinstance(key["value"], list) else key["value"]
            try:
                return str(int(float(v)) + 1)
            except (TypeError, ValueError):
                return "null"
        return key["correct"][:1] if key["kind"] == "multi" else next(i for i in range(9) if i not in key["correct"])
    if key["kind"] == "single":
        return key["correct"][0]
    if key["kind"] == "multi":
        return key["correct"]
    return key["value"][0] if isinstance(key["value"], list) else key["value"]


# ---------------------------------------------------------------- сценарий
def scenario(d: Demo):
    b = d.b
    # 1. Платформа
    d.nav("/")
    d.say("Драфт", "ИТ-найм наоборот: компании сами приходят к кандидатам с подтверждённым уровнем и достижениями ФСП")
    d.pause(3.5)
    d.scroll(650, 2.2)
    d.scroll(1350, 2.4)
    d.scroll(0, 1.0)

    # 2. Новый кандидат: опрос
    d.login("newbie@draft.demo")
    d.nav("/c/assessment")
    d.say("Кандидат", "Категорию определяет не резюме, а опрос и адаптивный тест. Шаг 1 — направление, специализация, стек, заявленный грейд")
    d.pause(2.0)
    d.click("Разработка ПО", "button")
    d.click("Далее", "button")
    d.click("Backend-разработка", "button")
    d.wait("[...document.querySelectorAll('main button')].some(e => e.textContent.trim() === 'Python')", 5)
    d.click("Python", "main button", exact=True)
    d.click("Далее", "button")
    d.type("main .input input", "Pyth", delay=0.08)
    d.click("Python", "main .absolute button", exact=True)
    for s in ("PostgreSQL", "Docker"):
        d.click_sel("main .input")
        d.click(s, "main .absolute button", exact=True)
    d.b.js("document.activeElement && document.activeElement.blur()")
    d.click("Далее", "button")
    d.click("Middle", "main button")
    d.pause(0.8)
    d.click("Сохранить и перейти к тесту", "button")
    d.wait("[...document.querySelectorAll('button')].some(e => e.textContent.includes('Начать тест'))")
    d.say("Кандидат", "План теста: доли компетенций по специализации. Тест — на заявленный грейд Middle")
    d.pause(2.5)
    d.click("Начать тест", "button")
    d.wait("location.pathname.includes('/assessment/test/')")

    # 3. Адаптивный тест
    token = b.js("localStorage.getItem('draft.access')")
    attempt_id = int(b.js("location.pathname.split('/').pop()"))
    d.say("Тест", "Каждое задание генерируется заново: у другого кандидата будут другие данные и код — «слить» ответы бесполезно")
    rng = random.Random(4)
    for k in range(3):
        d.wait("document.querySelector('.animate-fade-in')")
        d.pause(2.2 if k == 0 else 1.3)
        item = api(token, "GET", f"/candidate/assessment/attempts/{attempt_id}")["item"]
        ans = answer_for(item["item_id"], correct=k != 1)
        if item["kind"] == "single":
            d.click_sel(".animate-fade-in .mt-6 .space-y-2 > button", nth=ans)
        elif item["kind"] == "multi":
            for i in ans:
                d.click_sel(".animate-fade-in .mt-6 .space-y-2 > button", nth=i)
        else:
            d.type(".animate-fade-in input", str(ans))
        if k == 1:
            d.say("Тест", "Следующее задание подбирается по модели IRT под текущую оценку; ответы и время проверяет сервер")
        d.click("Ответить", "button")
        d.pause(0.8)
    d.say("Тест", "Тест заканчивается, когда решение о грейде надёжно: очевидным случаям — 8–12 заданий, пограничным — до 22")
    d.pause(2.0)
    item = api(token, "GET", f"/candidate/assessment/attempts/{attempt_id}").get("item")
    while item:
        r = api(token, "POST", f"/candidate/assessment/attempts/{attempt_id}/answer",
                {"item_id": item["item_id"], "response": answer_for(item["item_id"], correct=rng.random() < 0.85), "time_ms": 40000})
        if r["finished"]:
            break
        item = r["item"]
    d.nav(f"/c/assessment/result/{attempt_id}")
    d.say("Результат", "Категория «Backend · Middle» подтверждена тестом; профиль компетенций; при уверенном результате — предложение повысить грейд")
    d.pause(3.2)
    d.scroll(520, 2.6)
    d.logout()

    # 4. Кандидат с историей: профиль и приглашения
    d.login("candidate@draft.demo")
    d.say("Профиль", "Работодатели видят категорию, подтверждённые навыки и достижения ФСП. Контакты скрыты до согласия кандидата")
    d.nav("/c")
    d.pause(3.5)
    d.say("Приглашения", "Приглашение приходит с обязательной зарплатной вилкой и объяснением, почему компания выбрала именно вас")
    d.nav("/c/invitations")
    d.pause(1.5)
    d.click("Отправлено", "main button.w-full") or d.click("Просмотрено", "main button.w-full")
    d.pause(2.5)
    d.click("Принять и открыть контакты", "button")
    d.pause(1.0)
    d.click("Принять", "[role=dialog] button", exact=True)
    d.say("Приглашения", "Кандидат принял приглашение — только теперь работодатель получает его контакты")
    d.pause(2.5)
    d.wait("document.querySelector('textarea[placeholder=\"Сообщение…\"]')", 6)
    d.say("Переписка", "Дальше — переписка на платформе без обмена контактами; доступ к контактам кандидат может закрыть в любой момент")
    d.type('textarea[placeholder="Сообщение…"]', "Добрый день! Удобно созвониться в среду после 15:00.")
    d.click("Отправить", "button", exact=True)
    d.pause(2.5)
    d.nav("/c/assessment")
    d.scroll_to("Мои категории", "h3", pause=1.2)
    d.say("Категории", "Несколько категорий: основная и до двух дополнительных. Грейд в каждой подтверждается только своим тестом")
    d.pause(3.5)
    d.nav("/c/growth")
    d.say("Рост", "«Рост и зарплаты»: ожидания относительно рынка категории, что просят на следующем грейде, слабая тема теста")
    d.pause(3.0)
    d.scroll(520, 2.2)
    d.logout()

    # 5. Работодатель: потребность → подборка → приглашение
    d.login("employer@draft.demo")
    d.say("Работодатель", "Работодатель не публикует вакансию и не ждёт откликов: он описывает, кого ищет")
    d.nav("/e")
    d.pause(2.8)
    d.click("Описать потребность", "a, button")
    d.wait("[...document.querySelectorAll('button')].some(e => e.textContent.includes('Подставить пример'))")
    d.click("Подставить пример", "button")
    d.pause(1.2)
    d.say("Работодатель", "Текст разбирается автоматически: специализация, грейды, обязательные навыки, вилка, формат")
    d.click("Разобрать текст", "button")
    d.pause(2.8)
    d.scroll(520, 1.8)
    d.click("Сформировать подборку", "button")
    d.wait("location.pathname.match(/needs\\/\\d+$/)", 15)
    d.pause(1.5)
    d.say("Подборка", "Подборка по категориям: сначала целевая, затем смежные. Выше — подтверждённый уровень, навыки и опыт ФСП")
    d.pause(3.0)
    d.click("Почему в подборке", "button")
    d.pause(1.0)
    d.say("Подборка", "Выдача объяснима: вклад каждой компоненты, подтверждённые навыки, причины и вероятность принятия приглашения")
    d.pause(3.5)
    d.click_sel('main input[aria-label="Выбрать"]:not(:disabled)', nth=0)
    d.click_sel('main input[aria-label="Выбрать"]:not(:disabled)', nth=1)
    d.click("Сравнить", "button", exact=True)
    d.wait("document.querySelector('[role=dialog]') && document.querySelector('[role=dialog]').textContent.includes('Почему')", 10)
    d.say("Сравнение", "Сравнение кандидатов: те же компоненты формулы подбора и ответ на вопрос «почему A выше B»")
    d.pause(3.0)
    d.b.js("(() => { const m = document.querySelector('[role=dialog] .overflow-y-auto') || document.querySelector('[role=dialog]'); m.scrollTo({top: 600, behavior: 'smooth'}); })()")
    d.pause(2.5)
    d.b.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
    d.pause(0.8)
    d.click("Пригласить", "main button", exact=True)
    d.wait("document.querySelector('[role=dialog]')")
    d.pause(1.2)
    d.say("Приглашение", "Зарплатная вилка обязательна — кандидат видит условия сразу, до начала общения")
    d.type('[role=dialog] input[placeholder^="Ольга"]', "Ольга Смирнова, Telegram @technovector_hr")
    d.pause(1.0)
    d.click("Отправить приглашение", "button")
    d.pause(2.2)
    d.say("Статусы", "Статусы видны обеим сторонам: отправлено → просмотрено → принято / отклонено; дальше — этапы найма и ATS")
    d.nav("/e/invitations")
    d.pause(2.0)
    d.click_sel("main button.flex.w-full")
    d.pause(3.0)
    d.nav("/e/integrations")
    d.say("ATS", "Интеграция с ATS: вакансии из ATS, отклики и кандидаты — в ATS, статусы и этапы — в обе стороны (API и подписанные вебхуки)")
    d.pause(3.5)
    d.logout()

    # 6. Механика тестирования
    d.say("Механика", "Два кандидата — два разных варианта одного задания одинаковой трудности (IRT). Ключи не покидают сервер")
    d.nav("/mechanics")
    d.scroll_to("Лаборатория вариантов", "h3")
    d.pause(2.5)
    d.click("Сгенерировать заново", "button")
    d.pause(2.8)
    d.scroll_to("Симулятор", "h3")
    d.say("Механика", "Симулятор адаптивного теста: оценка способности уточняется после каждого ответа")
    d.pause(3.5)

    # 6б. Режим эксперта для жюри
    token = d.login("expert1@draft.demo")
    api(token, "POST", "/candidate/survey", {"direction": "development", "specialization": "backend", "primary_lang": "python",
                                             "stack": ["Python", "PostgreSQL"], "experience_years": 3, "declared_grade": "middle"})
    d.nav("/c/assessment")
    d.wait("[...document.querySelectorAll('button')].some(e => e.textContent.includes('Начать тест'))")
    d.click("Начать тест", "button")
    d.wait("location.pathname.includes('/assessment/test/') && document.querySelector('select[aria-label=\"Уровень профиля\"]')", 12)
    d.say("Жюри", "Режим эксперта: пройти тест как синтетический кандидат заданного уровня — проверка разделяющей силы за минуту")
    d.pause(3.0)
    d.click("Пройти как этот профиль", "button")
    d.wait("location.pathname.includes('/assessment/result/')", 20)
    d.say("Жюри", "Тот же уровень в другом аккаунте — другие задания и тот же грейд; разные уровни — разные грейды")
    d.pause(3.5)
    d.logout()

    # 7. Валидация и проверка на своём наборе пар
    d.say("Валидация", "Проверяем тест и подбор на данных со скрытой истиной: точность грейда, повторяемость, устойчивость к утечке, nDCG подбора")
    d.nav("/validation")
    d.pause(3.0)
    d.scroll(560, 3.0)
    d.scroll_to("своём наборе", "h3")
    d.say("Валидация", "Жюри может загрузить свой размеченный набор пар «вакансия — кандидат» и сразу получить метрики подбора")
    d.click("Прогнать пример", "button")
    d.pause(4.0)

    # 8. ФСП ID
    d.say("ФСП ID", "Вход и привязка профиля через ФСП ID по OIDC (совместимо с Keycloak) — достижения подтягиваются из реестра")
    d.nav("/login")
    d.pause(2.0)
    d.click("Войти через ФСП ID", "button")
    d.wait("location.port === '8081' && document.querySelector('.acc')", 12)
    d.b.js(OVERLAY)
    d.say("ФСП ID", "Страница авторизации ФСП ID (в прототипе — совместимый мок): спортсмен разрешает доступ к профилю")
    d.pause(2.0)
    d.click_sel(".acc")
    d.pause(0.8)
    d.click("Войти и разрешить доступ", "button")
    d.wait("location.port === '5173' && location.pathname.startsWith('/c')", 15)
    d.pause(1.2)
    d.say("ФСП ID", "Спортсмен вошёл через ФСП ID: результаты соревнований подтянулись из реестра с подписью и попадут в подборку")
    d.nav("/c/settings")
    d.scroll_to("ФСП", "h3", pause=1.0)
    d.pause(3.0)
    d.say("ФСП ID", "Дальше — тот же путь: опрос и тест. Кандидат без истории ФСП проходит его так же и не исключается из выдачи")
    d.pause(3.0)

    # 9. Финал
    d.logout()
    d.say("Драфт", "Обратная механика · адаптивный тест · верифицированный профиль ФСП. Запуск: docker compose up --build")
    d.nav("/")
    d.pause(4.0)


def encode(frames: list[tuple[float, Path]], out: Path):
    import imageio_ffmpeg

    out.parent.mkdir(parents=True, exist_ok=True)
    lst = frames[0][1].parent / "list.txt"
    lines = []
    for (t, p), (t2, _) in zip(frames, frames[1:] + [(frames[-1][0] + 2.0, None)]):
        lines.append(f"file '{p}'\nduration {max(0.02, min(8.0, t2 - t)):.3f}")
    lines.append(f"file '{frames[-1][1]}'")
    lst.write_text("\n".join(lines))
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-vf", f"fps=30,scale={W}:{H}:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", "23",
           "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)


def main():
    frames_dir = Path(tempfile.mkdtemp())
    b = Browser(frames_dir)
    try:
        b.call("Page.enable")
        b.call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
        b.call("Page.addScriptToEvaluateOnNewDocument", source=OVERLAY)
        b.call("Page.navigate", url=APP + "/")
        time.sleep(1.5)
        b.call("Page.startScreencast", format="jpeg", quality=88, maxWidth=W, maxHeight=H, everyNthFrame=1)
        t0 = time.time()
        scenario(Demo(b))
        b.call("Page.stopScreencast")
        print(f"сценарий: {time.time() - t0:.0f} с, кадров: {len(b.frames)}")
    finally:
        b.close()
    encode(sorted(b.frames), OUT)
    print("видео:", OUT, f"{OUT.stat().st_size / 1e6:.1f} МБ")
    shutil.rmtree(frames_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
