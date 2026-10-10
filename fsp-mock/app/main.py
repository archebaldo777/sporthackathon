"""Демо-стенд «ФСП ID + реестр достижений ФСП».

Эмулирует Keycloak-реалм (те же URL и формат токенов), чтобы платформа интегрировалась с ним так же,
как будет интегрироваться с настоящим ФСП ID на Keycloak:
  /realms/{realm}/.well-known/openid-configuration
  /realms/{realm}/protocol/openid-connect/{auth,token,userinfo,certs,logout}
и предлагает API реестра достижений, которое команда спроектировала сама (ТЗ не задаёт структуру данных ФСП):
  GET /api/v1/athletes/{fsp_id}            — профиль спортсмена
  GET /api/v1/athletes/{fsp_id}/results    — результаты соревнований (подписанные записи)
  GET /api/v1/events                       — календарь соревнований
Доступ к реестру: токен пользователя со scope fsp_achievements (только свои данные) или сервисный токен
(client_credentials, роль registry-reader) для фоновой синхронизации.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Form, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

DATA = Path(__file__).resolve().parents[1] / "data" / "registry.json"
REALM = os.getenv("FSP_REALM", "fsp")
PUBLIC_BASE = os.getenv("FSP_PUBLIC_BASE", "http://localhost:8081")
CLIENTS = {os.getenv("FSP_CLIENT_ID", "draft-platform"): os.getenv("FSP_CLIENT_SECRET", "draft-secret")}
DEMO_PASSWORD = os.getenv("FSP_DEMO_PASSWORD", "fsp2026")
# Разрешённые адреса возврата клиента (как «Valid Redirect URIs» в Keycloak): код авторизации уходит только на них
ALLOWED_REDIRECTS = [p.strip().rstrip("/") for p in os.getenv(
    "FSP_ALLOWED_REDIRECTS", "http://localhost:8080,http://localhost:5173,http://127.0.0.1:8080,http://127.0.0.1:5173").split(",") if p.strip()]


def _check_redirect(redirect_uri: str) -> None:
    if not any(redirect_uri == p or redirect_uri.startswith(p + "/") for p in ALLOWED_REDIRECTS):
        raise HTTPException(400, "invalid redirect_uri")

if not DATA.exists():
    from app.generate import generate

    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(generate(), ensure_ascii=False))
REG = json.loads(DATA.read_text())
ATHLETES = {a["fsp_id"]: a for a in REG["athletes"]}
BY_USERNAME = {a["username"]: a for a in REG["athletes"]}
BY_SUB = {a["sub"]: a for a in REG["athletes"]}
EVENTS = {e["event_id"]: e for e in REG["events"]}
RESULTS: dict[str, list[dict]] = {}
for r in REG["results"]:
    RESULTS.setdefault(r["fsp_id"], []).append(r)

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KID = secrets.token_hex(8)
CODES: dict[str, dict] = {}
ISSUER = f"{PUBLIC_BASE}/realms/{REALM}"

app = FastAPI(title="ФСП ID (демо, Keycloak-совместимый) + реестр достижений", version="1.0.0",
              description="Демонстрационный стенд для интеграции платформы «Драфт» с ФСП ID и реестром результатов. Данные синтетические.")


def _public(a: dict) -> dict:
    return {k: v for k, v in a.items() if not k.startswith("_")}


def _b64u(n: int) -> str:
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _token(claims: dict, ttl: int = 300) -> str:
    now = int(time.time())
    return jwt.encode({"iss": ISSUER, "iat": now, "exp": now + ttl, **claims}, KEY, algorithm="RS256", headers={"kid": KID})


def _verify(token: str) -> dict:
    try:
        return jwt.decode(token, KEY.public_key(), algorithms=["RS256"], issuer=ISSUER, options={"verify_aud": False})
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"invalid_token: {exc}")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    return f"<h1>ФСП ID — демо-стенд</h1><p>Issuer: {ISSUER}</p><p><a href='/docs'>OpenAPI</a></p>"


@app.get("/health")
def health():
    return {"status": "ok", "athletes": len(ATHLETES), "events": len(EVENTS)}


@app.get(f"/realms/{REALM}/.well-known/openid-configuration", tags=["oidc"])
def discovery():
    base = f"{ISSUER}/protocol/openid-connect"
    return {
        "issuer": ISSUER, "authorization_endpoint": f"{base}/auth", "token_endpoint": f"{base}/token", "userinfo_endpoint": f"{base}/userinfo",
        "jwks_uri": f"{base}/certs", "end_session_endpoint": f"{base}/logout", "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "client_credentials", "refresh_token"], "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"], "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["openid", "profile", "email", "fsp_achievements"],
    }


@app.get(f"/realms/{REALM}/protocol/openid-connect/certs", tags=["oidc"])
def certs():
    pub = KEY.public_key().public_numbers()
    return {"keys": [{"kid": KID, "kty": "RSA", "alg": "RS256", "use": "sig", "n": _b64u(pub.n), "e": _b64u(pub.e)}]}


# официальный логотип ФСП из брендбука (вариант для тёмного фона); страница помечена как демонстрационная
LOGO_SVG = (Path(__file__).parent / "static" / "fsp-short-dark.svg").read_text(encoding="utf-8")

LOGIN_PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ФСП ID — вход (демо)</title>
<style>
/* фирменный стиль ФСП: #402FFF, #EC1D35, градации серого #1B1C21 · #2D2E37 · #3A3C46 · #9B9C9E · #EDEDED */
:root{{--b:#402FFF;--r:#EC1D35;--bg:#1B1C21;--card:#2D2E37;--line:#3A3C46;--t:#EDEDED;--m:#9B9C9E}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--t);font:15px/1.5 Inter,system-ui,sans-serif;min-height:100vh;display:grid;place-items:center;padding:24px}}
.card{{width:100%;max-width:440px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:28px}}
.logo{{font-family:'JetBrains Mono',ui-monospace,monospace;font-weight:700;letter-spacing:.5px;display:flex;align-items:center;gap:12px;font-size:20px}}
.logo svg{{height:30px;width:auto}}
.demo{{margin:14px 0 20px;padding:10px 12px;border-radius:10px;background:#2a1720;border:1px solid #5a2333;color:#ffb3c0;font-size:13px}}
label{{display:block;font-size:13px;color:var(--m);margin:12px 0 6px}}
input{{width:100%;padding:12px 14px;border-radius:10px;border:1px solid var(--line);background:#1B1C21;color:var(--t);font:inherit}}
input:focus{{outline:2px solid var(--b);border-color:transparent}}
button{{width:100%;margin-top:18px;padding:13px;border:0;border-radius:12px;background:var(--b);color:#fff;font:600 15px Inter,sans-serif;cursor:pointer}}
.err{{color:#ff8a9b;font-size:13px;margin-top:10px}}
.list{{margin-top:22px;border-top:1px solid var(--line);padding-top:14px}}
.list p{{color:var(--m);font-size:13px;margin:0 0 8px}}
.acc{{display:flex;justify-content:space-between;gap:8px;width:100%;text-align:left;background:#1B1C21;border:1px solid var(--line);color:var(--t);padding:10px 12px;border-radius:10px;margin:6px 0;cursor:pointer;font:14px Inter,sans-serif}}
.acc span{{color:var(--m);font-family:'JetBrains Mono',monospace;font-size:12px}}
.scope{{font-size:13px;color:var(--m);margin-top:6px}}
</style></head><body><form class="card" method="post">
<div class="logo">{logo}<span>ID</span></div>
<div class="demo">Демонстрационный стенд (Keycloak-совместимый мок). Это не настоящий ФСП ID, данные синтетические.</div>
<div><b>{client}</b> запрашивает доступ к вашему профилю и результатам соревнований.</div>
<div class="scope">Запрашиваемые права: {scope}</div>
{hidden}
<label>Логин спортсмена</label><input name="username" id="u" value="{username}" autocomplete="username" required>
<label>Пароль</label><input name="password" id="p" type="password" value="" autocomplete="current-password" required>
{error}
<button type="submit">Войти и разрешить доступ</button>
<div class="list"><p>Демо-аккаунты спортсменов (пароль <b>{demo_pw}</b>):</p>{accounts}</div>
</form>
<script>document.querySelectorAll('.acc').forEach(b=>b.addEventListener('click',e=>{{e.preventDefault();document.getElementById('u').value=b.dataset.u;document.getElementById('p').value='{demo_pw}';}}));</script>
</body></html>"""


def _render_login(params: dict, error: str = "", username: str = "") -> HTMLResponse:
    hidden = "".join(f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(str(v))}">' for k, v in params.items())
    accounts = "".join(
        f'<button class="acc" data-u="{html.escape(d["username"])}">{html.escape(d["full_name"])}<span>{html.escape(d["fsp_id"])}</span></button>'
        for d in REG["demo_logins"])
    return HTMLResponse(LOGIN_PAGE.format(client=html.escape(params.get("client_id", "")), scope=html.escape(params.get("scope", "openid")),
                                          hidden=hidden, username=html.escape(username), accounts=accounts, demo_pw=DEMO_PASSWORD,
                                          error=f'<div class="err">{html.escape(error)}</div>' if error else "", logo=LOGO_SVG))


@app.get(f"/realms/{REALM}/protocol/openid-connect/auth", response_class=HTMLResponse, tags=["oidc"])
def authorize(client_id: str, redirect_uri: str, response_type: str = "code", scope: str = "openid", state: str = "", nonce: str = "",
              code_challenge: str = "", code_challenge_method: str = "S256"):
    if client_id not in CLIENTS:
        raise HTTPException(400, "unknown client_id")
    if response_type != "code":
        raise HTTPException(400, "unsupported response_type")
    _check_redirect(redirect_uri)
    return _render_login({"client_id": client_id, "redirect_uri": redirect_uri, "scope": scope, "state": state, "nonce": nonce,
                          "code_challenge": code_challenge, "code_challenge_method": code_challenge_method})


@app.post(f"/realms/{REALM}/protocol/openid-connect/auth", tags=["oidc"])
def authorize_submit(username: str = Form(...), password: str = Form(...), client_id: str = Form(...), redirect_uri: str = Form(...),
                     scope: str = Form("openid"), state: str = Form(""), nonce: str = Form(""), code_challenge: str = Form(""),
                     code_challenge_method: str = Form("S256")):
    if client_id not in CLIENTS:
        raise HTTPException(400, "unknown client_id")
    _check_redirect(redirect_uri)
    params = {"client_id": client_id, "redirect_uri": redirect_uri, "scope": scope, "state": state, "nonce": nonce,
              "code_challenge": code_challenge, "code_challenge_method": code_challenge_method}
    a = BY_USERNAME.get(username.strip().lower())
    if not a or not secrets.compare_digest(password, DEMO_PASSWORD):
        return _render_login(params, "Неверный логин или пароль", username)
    code = secrets.token_urlsafe(24)
    CODES[code] = {"sub": a["sub"], "client_id": client_id, "redirect_uri": redirect_uri, "scope": scope, "nonce": nonce,
                   "challenge": code_challenge, "exp": time.time() + 120}
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}{urlencode({'code': code, 'state': state})}", status_code=302)


def _client_auth(authorization: str | None, client_id: str | None, client_secret: str | None) -> str:
    if authorization and authorization.lower().startswith("basic "):
        cid, _, sec = base64.b64decode(authorization[6:]).decode().partition(":")
    else:
        cid, sec = client_id or "", client_secret or ""
    if CLIENTS.get(cid) != sec:
        raise HTTPException(401, "invalid_client")
    return cid


def _user_tokens(a: dict, cid: str, scope: str, nonce: str | None) -> dict:
    common = {"sub": a["sub"], "preferred_username": a["username"], "email": a["email"], "email_verified": True, "name": a["full_name"],
              "given_name": a["first_name"], "family_name": a["last_name"], "fsp_id": a["fsp_id"]}
    access = _token({**common, "aud": ["fsp-registry", "account"], "azp": cid, "typ": "Bearer", "scope": scope,
                     "realm_access": {"roles": ["athlete"]}}, 300)
    idt = _token({**common, "aud": cid, "azp": cid, "typ": "ID", **({"nonce": nonce} if nonce else {})}, 300)
    refresh = _token({"sub": a["sub"], "aud": ISSUER, "typ": "Refresh", "azp": cid, "scope": scope}, 1800)
    return {"access_token": access, "id_token": idt, "refresh_token": refresh, "token_type": "Bearer", "expires_in": 300,
            "refresh_expires_in": 1800, "scope": scope}


@app.post(f"/realms/{REALM}/protocol/openid-connect/token", tags=["oidc"])
async def token(request: Request, authorization: str | None = Header(None)):
    form = await request.form()
    grant = form.get("grant_type")
    cid = _client_auth(authorization, form.get("client_id"), form.get("client_secret"))
    if grant == "authorization_code":
        data = CODES.pop(form.get("code", ""), None)
        if not data or data["exp"] < time.time() or data["client_id"] != cid or data["redirect_uri"] != form.get("redirect_uri"):
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        if data["challenge"]:
            verifier = form.get("code_verifier", "")
            calc = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            if calc != data["challenge"]:
                return JSONResponse({"error": "invalid_grant", "error_description": "PKCE verification failed"}, status_code=400)
        return _user_tokens(BY_SUB[data["sub"]], cid, data["scope"], data["nonce"])
    if grant == "refresh_token":
        claims = _verify(form.get("refresh_token", ""))
        if claims.get("typ") != "Refresh":
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        return _user_tokens(BY_SUB[claims["sub"]], cid, claims.get("scope", "openid"), None)
    if grant == "client_credentials":
        access = _token({"sub": f"service-account-{cid}", "aud": ["fsp-registry"], "azp": cid, "typ": "Bearer",
                         "realm_access": {"roles": ["registry-reader"]}, "scope": "fsp_achievements"}, 300)
        return {"access_token": access, "token_type": "Bearer", "expires_in": 300, "scope": "fsp_achievements"}
    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)


@app.get(f"/realms/{REALM}/protocol/openid-connect/userinfo", tags=["oidc"])
def userinfo(authorization: str = Header(...)):
    claims = _verify(authorization.removeprefix("Bearer ").strip())
    a = BY_SUB.get(claims["sub"])
    if not a:
        raise HTTPException(404, "user not found")
    return {"sub": a["sub"], "preferred_username": a["username"], "email": a["email"], "email_verified": True, "name": a["full_name"],
            "fsp_id": a["fsp_id"]}


@app.get(f"/realms/{REALM}/protocol/openid-connect/logout", tags=["oidc"])
def logout(post_logout_redirect_uri: str | None = None):
    return RedirectResponse(post_logout_redirect_uri or "/")


def _authorize_registry(authorization: str | None, fsp_id: str) -> None:
    if not authorization:
        raise HTTPException(401, "bearer token required")
    claims = _verify(authorization.removeprefix("Bearer ").strip())
    roles = claims.get("realm_access", {}).get("roles", [])
    if "registry-reader" in roles:
        return
    if "fsp_achievements" in claims.get("scope", "") and claims.get("fsp_id") == fsp_id:
        return
    raise HTTPException(403, "access to this athlete is not granted")


@app.get("/api/v1/athletes/{fsp_id}", tags=["registry"])
def athlete(fsp_id: str, authorization: str | None = Header(None)):
    _authorize_registry(authorization, fsp_id)
    a = ATHLETES.get(fsp_id)
    if not a:
        raise HTTPException(404, "athlete not found")
    return _public(a)


@app.get("/api/v1/athletes/{fsp_id}/results", tags=["registry"])
def athlete_results(fsp_id: str, authorization: str | None = Header(None)):
    _authorize_registry(authorization, fsp_id)
    a = ATHLETES.get(fsp_id)
    if not a:
        raise HTTPException(404, "athlete not found")
    items = [{**r, "event": EVENTS[r["event_id"]]} for r in RESULTS.get(fsp_id, [])]
    items.sort(key=lambda x: x["event"]["start_date"], reverse=True)
    return {"athlete": _public(a), "results": items, "generated_at": int(time.time()), "schema_version": "1.0"}


@app.get("/api/v1/events", tags=["registry"])
def events(discipline: str | None = Query(None), level: str | None = Query(None), year: int | None = Query(None)):
    out = [e for e in EVENTS.values() if (not discipline or e["discipline"] == discipline) and (not level or e["level"] == level)
           and (not year or e["start_date"].startswith(str(year)))]
    return {"items": sorted(out, key=lambda e: e["start_date"], reverse=True)}
