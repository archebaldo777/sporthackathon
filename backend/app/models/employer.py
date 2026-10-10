from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow
from app.models.types import JSONType


class Company(Base):
    __tablename__ = "companies"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(64))
    website: Mapped[str | None] = mapped_column(String(200))
    size: Mapped[str | None] = mapped_column(String(32))
    city: Mapped[str | None] = mapped_column(String(100))
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(254))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    telegram: Mapped[str | None] = mapped_column(String(64))
    inn: Mapped[str | None] = mapped_column(String(12))
    accent: Mapped[str | None] = mapped_column(String(16))
    trust_score: Mapped[int] = mapped_column(Integer, default=40)
    trust_factors: Mapped[list] = mapped_column(JSONType, default=list)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    user = relationship("User", back_populates="company")


class HiringNeed(Base):
    """Потребность работодателя («кого ищем») — основа для подборки кандидатов."""

    __tablename__ = "hiring_needs"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("companies.user_id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    specialization: Mapped[str] = mapped_column(String(32))
    grades: Mapped[list] = mapped_column(JSONType)
    must_skills: Mapped[list] = mapped_column(JSONType, default=list)
    nice_skills: Mapped[list] = mapped_column(JSONType, default=list)
    work_formats: Mapped[list] = mapped_column(JSONType, default=list)
    city: Mapped[str | None] = mapped_column(String(100))
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    fsp_weight: Mapped[float] = mapped_column(Float, default=0.5)  # важность достижений ФСП, 0..1
    domains: Mapped[list] = mapped_column(JSONType, default=list)
    status: Mapped[str] = mapped_column(String(16), default="active")
    last_run_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class ShortlistEntry(Base):
    """Сохранённая подборка: оценка + пометки работодателя сохраняются при уточнении запроса."""

    __tablename__ = "shortlist_entries"
    __table_args__ = (UniqueConstraint("need_id", "candidate_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    need_id: Mapped[int] = mapped_column(ForeignKey("hiring_needs.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.user_id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[dict] = mapped_column(JSONType)
    mark: Mapped[str] = mapped_column(String(16), default="new")  # new | starred | hidden
    note: Mapped[str | None] = mapped_column(String(500))
    first_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("companies.user_id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    specialization: Mapped[str] = mapped_column(String(32), index=True)
    grade: Mapped[str] = mapped_column(String(16))
    must_skills: Mapped[list] = mapped_column(JSONType, default=list)
    nice_skills: Mapped[list] = mapped_column(JSONType, default=list)
    work_formats: Mapped[list] = mapped_column(JSONType, default=list)
    city: Mapped[str | None] = mapped_column(String(100))
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="published")  # draft | published | closed
    risk_flags: Mapped[list] = mapped_column(JSONType, default=list)
    views: Mapped[int] = mapped_column(Integer, default=0)
    external_id: Mapped[str | None] = mapped_column(String(64), index=True)  # идентификатор вакансии в ATS работодателя
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    company = relationship("Company", foreign_keys=[employer_id], lazy="joined")


class Application(Base):
    """Самостоятельный отклик кандидата на вакансию."""

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("vacancy_id", "candidate_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.user_id", ondelete="CASCADE"), index=True)
    cover_letter: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="sent")  # sent | viewed | interview | offer | rejected | withdrawn
    match_score: Mapped[float | None] = mapped_column(Float)
    explanation: Mapped[dict | None] = mapped_column(JSONType)
    employer_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    viewed_at: Mapped[datetime | None]

    vacancy = relationship("Vacancy", lazy="joined")


class Invitation(Base):
    """Приглашение от работодателя конкретному кандидату — ядро «обратной» механики."""

    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("companies.user_id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.user_id", ondelete="CASCADE"), index=True)
    need_id: Mapped[int | None] = mapped_column(ForeignKey("hiring_needs.id", ondelete="SET NULL"))
    vacancy_id: Mapped[int | None] = mapped_column(ForeignKey("vacancies.id", ondelete="SET NULL"))
    batch_id: Mapped[str | None] = mapped_column(String(32))

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    work_format: Mapped[str | None] = mapped_column(String(16))
    city: Mapped[str | None] = mapped_column(String(100))
    contact_method: Mapped[str] = mapped_column(String(300))

    status: Mapped[str] = mapped_column(String(16), default="sent", index=True)
    stage: Mapped[str | None] = mapped_column(String(16))  # после принятия: contact | interview | offer | hired | closed
    decline_reason: Mapped[str | None] = mapped_column(String(32))
    decline_comment: Mapped[str | None] = mapped_column(Text)
    candidate_message: Mapped[str | None] = mapped_column(Text)
    match_score: Mapped[float | None] = mapped_column(Float)
    explanation: Mapped[dict | None] = mapped_column(JSONType)
    risk_flags: Mapped[list] = mapped_column(JSONType, default=list)

    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    viewed_at: Mapped[datetime | None]
    responded_at: Mapped[datetime | None]
    expires_at: Mapped[datetime]
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    # кандидат закрыл работодателю доступ к своим контактам после принятия (переписка на платформе остаётся)
    contacts_revoked_at: Mapped[datetime | None]

    company = relationship("Company", foreign_keys=[employer_id], lazy="joined")
    vacancy = relationship("Vacancy", foreign_keys=[vacancy_id])


class Message(Base):
    """Переписка кандидата и работодателя внутри принятого приглашения — без обмена контактами."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    invitation_id: Mapped[int] = mapped_column(ForeignKey("invitations.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    sender_role: Mapped[str] = mapped_column(String(16))  # candidate | employer
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    read_at: Mapped[datetime | None]


class EmployerTask(Base):
    """Короткая задача от работодателя для регулярных заданий кандидатам."""

    __tablename__ = "employer_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("companies.user_id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    specialization: Mapped[str] = mapped_column(String(32), index=True)
    grades: Mapped[list] = mapped_column(JSONType)
    kind: Mapped[str] = mapped_column(String(16), default="approach")  # solution | approach
    est_minutes: Mapped[int] = mapped_column(Integer, default=30)
    key_points: Mapped[list] = mapped_column(JSONType, default=list)  # скрытая рубрика для автооценки
    skills: Mapped[list] = mapped_column(JSONType, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    company = relationship("Company", foreign_keys=[employer_id], lazy="joined")


class TaskAssignment(Base):
    __tablename__ = "task_assignments"
    __table_args__ = (UniqueConstraint("task_id", "candidate_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("employer_tasks.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.user_id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="assigned")  # assigned | submitted | reviewed | expired | skipped
    assigned_at: Mapped[datetime] = mapped_column(default=utcnow)
    due_at: Mapped[datetime]
    answer: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None]
    auto_score: Mapped[float | None] = mapped_column(Float)
    auto_details: Mapped[dict | None] = mapped_column(JSONType)
    score: Mapped[int | None] = mapped_column(Integer)  # оценка работодателя 1..5
    feedback: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None]

    task = relationship("EmployerTask", lazy="joined")


class Report(Base):
    """Жалоба кандидата на приглашение/вакансию/работодателя (антифрод)."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    employer_id: Mapped[int] = mapped_column(ForeignKey("companies.user_id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ApiKey(Base):
    """Ключ доступа ATS-системы работодателя к API интеграции."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("companies.user_id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    prefix: Mapped[str] = mapped_column(String(16), index=True)
    key_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("companies.user_id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    secret: Mapped[str] = mapped_column(String(64))
    events: Mapped[list] = mapped_column(JSONType)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhooks.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONType)
    status_code: Mapped[int | None] = mapped_column(Integer)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(String(500))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
