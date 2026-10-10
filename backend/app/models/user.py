from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow
from app.models.types import JSONType


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), index=True)  # candidate | employer | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verify_code_hash: Mapped[str | None] = mapped_column(String(128))
    verify_token: Mapped[str | None] = mapped_column(String(64), index=True)
    verify_expires_at: Mapped[datetime | None]

    # sub пользователя в ФСП ID (Keycloak) — связь аккаунта с участником ФСП
    fsp_sub: Mapped[str | None] = mapped_column(String(64), unique=True)

    login_failed_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_login_at: Mapped[datetime | None]

    candidate = relationship("CandidateProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    company = relationship("Company", back_populates="user", uselist=False, cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Consent(Base):
    """Журнал согласий (152-ФЗ): каждое изменение — отдельная запись с версией документа."""

    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # pd_processing | profile_publication | fsp_data | marketing
    version: Mapped[str] = mapped_column(String(16))
    granted: Mapped[bool] = mapped_column(Boolean)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))
    read_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


class AuditLog(Base):
    """Аудит чувствительных действий: раскрытие контактов, изменение согласий, выгрузка данных."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[int | None] = mapped_column(Integer)
    meta: Mapped[dict | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class OidcState(Base):
    """Состояние OIDC-авторизации через ФСП ID (state + PKCE verifier)."""

    __tablename__ = "oidc_states"

    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    code_verifier: Mapped[str] = mapped_column(String(128))
    nonce: Mapped[str] = mapped_column(String(64))
    intent: Mapped[str] = mapped_column(String(16))  # login | link
    user_id: Mapped[int | None] = mapped_column(Integer)
    role: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
