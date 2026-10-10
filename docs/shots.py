"""Скриншоты интерфейса для презентации и документации (headless Chrome через DevTools Protocol).

Запуск при работающем стенде (frontend :5173, backend :8000):
    backend/.venv/bin/python docs/shots.py
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
APP = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173"
OUT = Path(os.environ.get("SHOTS_OUT") or Path(__file__).resolve().parent / "img" / "screens")
PORT = 9333


def token(email: str) -> dict:
    req = urllib.request.Request(f"{APP}/api/v1/auth/login", data=json.dumps({"email": email, "password": "Demo2026!"}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())


class Tab:
    def __init__(self, ws_url: str):
        self.ws = connect(ws_url, max_size=50 * 1024 * 1024)
        self.n = 0

    def call(self, method: str, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                return msg.get("result", {})

    def shot(self, url: str, name: str, scroll: int = 0, wait: float = 2.8, height: int = 900, js: str | None = None):
        self.call("Emulation.setDeviceMetricsOverride", width=1440, height=height, deviceScaleFactor=2, mobile=False)
        self.call("Page.navigate", url=url)
        time.sleep(wait)
        if js:
            self.call("Runtime.evaluate", expression=js, awaitPromise=True)
            time.sleep(1.2)
        if scroll:
            self.call("Runtime.evaluate", expression=f"window.scrollTo(0,{scroll})")
            time.sleep(0.6)
        data = self.call("Page.captureScreenshot", format="png")["data"]
        (OUT / f"{name}.png").write_bytes(base64.b64decode(data))
        print("saved", name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp()
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={tmp}", "--hide-scrollbars",
                             "--window-size=1440,900", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
                ws = next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        tab = Tab(ws)
        tab.call("Page.enable")

        def login_as(email):
            t = token(email)
            tab.call("Page.navigate", url=f"{APP}/")
            time.sleep(1)
            tab.call("Runtime.evaluate", expression=f"localStorage.setItem('draft.access','{t['access_token']}');"
                                                     f"localStorage.setItem('draft.refresh','{t['refresh_token']}')")

        tab.shot(f"{APP}/", "landing")
        tab.shot(f"{APP}/how", "how")
        tab.shot(f"{APP}/mechanics", "mechanics_lab", scroll=1180, wait=3.5)
        tab.shot(f"{APP}/mechanics", "mechanics_sim", scroll=2050, wait=3.5)
        tab.shot(f"{APP}/validation", "validation", scroll=380, wait=3)
        tab.shot(f"{APP}/login", "login")
        cand = token("candidate@draft.demo")
        req = urllib.request.Request(f"{APP}/api/v1/candidate/me", headers={"Authorization": f"Bearer {cand['access_token']}"})
        cand_id = json.loads(urllib.request.urlopen(req).read())["id"]
        login_as("employer@draft.demo")
        tab.shot(f"{APP}/e/candidates/{cand_id}", "candidate_card", scroll=420)
        tab.shot(f"{APP}/e", "employer_dashboard")
        tab.shot(f"{APP}/e/needs/1", "shortlist")
        tab.shot(f"{APP}/e/needs/1", "shortlist_explain", js="document.querySelectorAll('button').forEach(b=>{if(b.textContent.includes('Почему в подборке')&&!window._o){window._o=1;b.click()}})", scroll=470)
        tab.shot(f"{APP}/e/needs/1", "compare", wait=3.5, js="(async()=>{const c=[...document.querySelectorAll('input[aria-label=\"Выбрать\"]')];c[0].click();c[1].click();await new Promise(r=>setTimeout(r,400));[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Сравнить').click();await new Promise(r=>setTimeout(r,1500));})()")
        tab.shot(f"{APP}/e/talent", "talent_map")
        tab.shot(f"{APP}/e/needs/new", "need_form", js="(async()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Подставить пример'));b&&b.click();await new Promise(r=>setTimeout(r,300));const p=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Разобрать текст'));p&&p.click();})()")
        tab.shot(f"{APP}/e/invitations", "employer_invitations", js="(()=>{const b=document.querySelector('main button.flex.w-full');b&&b.click()})()")
        login_as("candidate@draft.demo")
        tab.shot(f"{APP}/c", "candidate_dashboard")
        tab.shot(f"{APP}/c/invitations", "candidate_invitations")
        tab.shot(f"{APP}/c/assessment", "assessment")
        tab.shot(f"{APP}/c/growth", "growth", wait=3.5)
        tab.shot(f"{APP}/c/settings", "settings_fsp")
        login_as("newbie@draft.demo")
        tab.shot(f"{APP}/c/assessment", "newbie_assessment")
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
