"""Регистрация по e-mail с подтверждением, вход, обновление токенов, вход/связывание через ФСП ID (OIDC)."""
from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db, utcnow
from app.core.deps import auth_limiter, get_current_user, require_role
from app.core.errors import COMMON_ERRORS, AppError, err
from app.core.security import create_access_token, hash_password, jwks, random_code, random_token, sha256, verify_password
from app.fsp import client as fsp
from app.models import CandidateProfile, Company, RefreshToken, User
from app.schemas import (
    EmailIn,
    FspAuthorizeOut,
    FspCallbackIn,
    FspCallbackOut,
    LoginIn,
    RefreshIn,
    RegisterIn,
    RegisterOut,
    TokenOut,
    UserOut,
    VerifyIn,
)
from app.services.common import audit, email_layout, record_consent, send_email
from app.services.trust import refresh_trust

router = APIRouter(prefix="/auth", tags=["Аутентификация"])


def new_public_code(db: Session) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        code = "K-" + "".join(secrets.choice(alphabet) for _ in range(5))
        if not db.scalar(select(CandidateProfile).where(CandidateProfile.public_code == code)):
            return code


def user_out(db: Session, u: User) -> UserOut:
    name = None
    if u.role == "candidate":
        c = db.get(CandidateProfile, u.id)
        name = c.full_name if c else None
    elif u.role == "employer":
        c = db.get(Company, u.id)
        name = c.name if c else None
    return UserOut(id=u.id, email=u.email, role=u.role, email_verified=u.email_verified, fsp_linked=bool(u.fsp_sub), display_name=name)


def issue_tokens(db: Session, u: User, ua: str | None = None) -> TokenOut:
    access, ttl = create_access_token(u.id, u.email, u.role, u.email_verified, bool(u.fsp_sub))
    refresh = random_token(40)
    db.add(RefreshToken(user_id=u.id, token_hash=sha256(refresh), expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
                        user_agent=(ua or "")[:250]))
    u.last_login_at = utcnow()
    db.commit()
    return TokenOut(access_token=access, refresh_token=refresh, expires_in=ttl, user=user_out(db, u))


def send_verification(db: Session, u: User) -> bool:
    code, token = random_code(), random_token(24)
    u.verify_code_hash, u.verify_token, u.verify_expires_at = sha256(f"{u.id}:{code}"), token, utcnow() + timedelta(hours=24)
    db.commit()
    link = f"{settings.public_url}/verify-email?token={token}"
    body = (f"<p>Код подтверждения: <b style='font-family:monospace;font-size:20px;letter-spacing:4px'>{code}</b></p>"
            "<p>Или подтвердите адрес по кнопке ниже. Ссылка действует 24 часа.</p>")
    return send_email(u.email, "Подтвердите e-mail — Драфт", f"Код подтверждения: {code}\nСсылка: {link}",
                      email_layout("Подтверждение адреса", body, ("Подтвердить e-mail", link)))


def create_candidate(db: Session, email: str, password: str | None, verified: bool = False) -> User:
    u = User(email=email.lower(), password_hash=hash_password(password) if password else None, role="candidate", email_verified=verified)
    db.add(u)
    db.flush()
    db.add(CandidateProfile(user_id=u.id, public_code=new_public_code(db)))
    db.flush()
    return u


@router.post("/register", response_model=RegisterOut, status_code=201, summary="Регистрация по e-mail",
             responses={**err(409, "E-mail уже зарегистрирован"), **err(422, "Ошибка валидации")}, dependencies=[Depends(auth_limiter)])
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise AppError(409, "email_taken", "Пользователь с таким e-mail уже зарегистрирован")
    ip, ua = request.client.host if request.client else None, request.headers.get("user-agent")
    if body.role == "candidate":
        u = create_candidate(db, body.email, body.password)
        cand = db.get(CandidateProfile, u.id)
        if body.consent_publication and cand:
            cand.visible = True
        if cand:
            cand.age_group = body.age_group
        record_consent(db, u.id, "profile_publication", body.consent_publication, ip, ua)
        if body.age_group == "minor":
            record_consent(db, u.id, "guardian_consent", True, ip, ua)
    else:
        u = User(email=body.email.lower(), password_hash=hash_password(body.password), role="employer")
        db.add(u)
        db.flush()
        comp = Company(user_id=u.id, name=body.company_name.strip(), contact_email=body.email.lower(), created_at=utcnow())
        db.add(comp)
        db.flush()
        refresh_trust(db, comp)
    record_consent(db, u.id, "pd_processing", True, ip, ua)
    audit(db, u.id, "register", "user", u.id, role=body.role)
    db.commit()
    sent = send_verification(db, u)
    return RegisterOut(user_id=u.id, email=u.email, verification_sent=sent, demo_mailbox_url=settings.demo_mailbox_url if settings.demo_mode else None)


@router.post("/verify-email", response_model=TokenOut, summary="Подтверждение e-mail кодом или токеном из письма",
             responses={**err(400, "Неверный или просроченный код")}, dependencies=[Depends(auth_limiter)])
def verify_email(body: VerifyIn, request: Request, db: Session = Depends(get_db)):
    u = None
    if body.token:
        u = db.scalar(select(User).where(User.verify_token == body.token))
    elif body.email and body.code:
        cand = db.scalar(select(User).where(User.email == body.email.lower()))
        if cand and cand.verify_code_hash == sha256(f"{cand.id}:{body.code}"):
            u = cand
    if not u or not u.verify_expires_at or (u.verify_expires_at if u.verify_expires_at.tzinfo else u.verify_expires_at.replace(
            tzinfo=utcnow().tzinfo)) < utcnow():
        raise AppError(400, "invalid_code", "Неверный или просроченный код подтверждения")
    u.email_verified = True
    u.verify_code_hash = u.verify_token = None
    audit(db, u.id, "email_verified", "user", u.id)
    db.commit()
    return issue_tokens(db, u, request.headers.get("user-agent"))


@router.post("/resend-verification", status_code=202, summary="Повторно отправить письмо с кодом", dependencies=[Depends(auth_limiter)])
def resend(body: EmailIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if u and not u.email_verified:
        send_verification(db, u)
    return {"status": "accepted", "demo_mailbox_url": settings.demo_mailbox_url if settings.demo_mode else None}


@router.post("/login", response_model=TokenOut, summary="Вход по e-mail и паролю",
             responses={**err(401, "Неверные учётные данные"), **err(423, "Учётная запись временно заблокирована")},
             dependencies=[Depends(auth_limiter)])
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    now = utcnow()
    if u and u.locked_until and (u.locked_until if u.locked_until.tzinfo else u.locked_until.replace(tzinfo=now.tzinfo)) > now:
        raise AppError(423, "locked", "Слишком много неудачных попыток. Попробуйте через несколько минут")
    if not u or not verify_password(body.password, u.password_hash):
        if u:
            u.login_failed_count = (u.login_failed_count or 0) + 1
            if u.login_failed_count >= 5:
                u.locked_until, u.login_failed_count = now + timedelta(minutes=5), 0
            db.commit()
        raise AppError(401, "invalid_credentials", "Неверный e-mail или пароль")
    if not u.is_active:
        raise AppError(403, "inactive", "Учётная запись отключена")
    u.login_failed_count = 0
    return issue_tokens(db, u, request.headers.get("user-agent"))


@router.post("/refresh", response_model=TokenOut, summary="Обновить access-токен (ротация refresh-токена)", responses=err(401, "Недействительный токен"))
def refresh(body: RefreshIn, request: Request, db: Session = Depends(get_db)):
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256(body.refresh_token)))
    now = utcnow()
    if not rt or rt.revoked_at or (rt.expires_at if rt.expires_at.tzinfo else rt.expires_at.replace(tzinfo=now.tzinfo)) < now:
        raise AppError(401, "invalid_token", "Сессия истекла, войдите снова")
    rt.revoked_at = now
    u = db.get(User, rt.user_id)
    if not u or not u.is_active:
        raise AppError(401, "invalid_token", "Пользователь недоступен")
    return issue_tokens(db, u, request.headers.get("user-agent"))


@router.post("/logout", status_code=204, summary="Выход (отзыв refresh-токена)")
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256(body.refresh_token)))
    if rt and not rt.revoked_at:
        rt.revoked_at = utcnow()
        db.commit()


@router.get("/me", response_model=UserOut, summary="Текущий пользователь", responses=COMMON_ERRORS)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_out(db, user)


@router.get("/jwks", summary="Публичные ключи подписи токенов (JWKS)")
def get_jwks():
    return jwks()


@router.get("/.well-known/openid-configuration", summary="OIDC discovery платформы (Keycloak-совместимые claims)")
def discovery():
    base = f"{settings.public_url}/api/v1/auth"
    return {"issuer": settings.jwt_issuer, "jwks_uri": f"{base}/jwks", "token_endpoint": f"{base}/login",
            "id_token_signing_alg_values_supported": ["RS256"], "claims_supported": ["sub", "email", "email_verified", "realm_access", "fsp_linked"]}


# ---------------------------------------------------------------- ФСП ID
@router.get("/fsp/login", response_model=FspAuthorizeOut, summary="Начать вход/регистрацию кандидата через ФСП ID",
            responses=err(503, "ФСП ID недоступен"))
def fsp_login(db: Session = Depends(get_db)):
    return FspAuthorizeOut(authorize_url=fsp.begin(db, "login", role="candidate"))


@router.get("/fsp/link", response_model=FspAuthorizeOut, summary="Начать связывание профиля кандидата с ФСП ID", responses=COMMON_ERRORS)
def fsp_link(user: User = Depends(require_role("candidate")), db: Session = Depends(get_db)):
    return FspAuthorizeOut(authorize_url=fsp.begin(db, "link", user_id=user.id))


@router.post("/fsp/callback", response_model=FspCallbackOut, summary="Завершение OIDC-авторизации ФСП ID",
             responses={**err(400, "Ошибка авторизации"), **err(409, "ФСП ID уже связан с другим аккаунтом")})
def fsp_callback(body: FspCallbackIn, request: Request, db: Session = Depends(get_db)):
    st, tokens, claims = fsp.complete(db, body.code, body.state)
    sub, fsp_id = claims["sub"], claims.get("fsp_id")
    ip, ua = request.client.host if request.client else None, request.headers.get("user-agent")
    owner = db.scalar(select(User).where(User.fsp_sub == sub))
    if st.intent == "link":
        u = db.get(User, st.user_id)
        if owner and owner.id != u.id:
            raise AppError(409, "fsp_taken", "Этот ФСП ID уже связан с другим аккаунтом")
    else:
        if owner:
            return FspCallbackOut(intent="login", tokens=issue_tokens(db, owner, ua), linked=True, fsp_id=fsp_id)
        if db.scalar(select(User).where(User.email == (claims.get("email") or "").lower())):
            raise AppError(409, "email_exists", "Аккаунт с этим e-mail уже есть — войдите по паролю и свяжите ФСП ID в настройках")
        u = create_candidate(db, claims.get("email") or f"{sub}@fsp-id.local", None, verified=bool(claims.get("email_verified")))
        db.flush()
        record_consent(db, u.id, "pd_processing", True, ip, ua)
        record_consent(db, u.id, "profile_publication", False, ip, ua)
        cand = db.get(CandidateProfile, u.id)
        cand.full_name = claims.get("name")
    cand = db.get(CandidateProfile, u.id)
    u.fsp_sub = sub
    cand.fsp_id, cand.fsp_linked_at = fsp_id, utcnow()
    record_consent(db, u.id, "fsp_data", True, ip, ua)
    count = 0
    try:
        count = fsp.apply_results(db, cand, fsp.fetch_results(tokens["access_token"], fsp_id))
    except Exception:  # noqa: BLE001 — реестр может быть недоступен: связь сохраняем, синхронизация повторится позже
        pass
    audit(db, u.id, "fsp_linked", "candidate", u.id, fsp_id=fsp_id, achievements=count)
    db.commit()
    return FspCallbackOut(intent=st.intent, tokens=issue_tokens(db, u, ua) if st.intent == "login" else None, linked=True, fsp_id=fsp_id,
                          achievements=count)
