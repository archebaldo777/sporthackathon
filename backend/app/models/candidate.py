from datetime import date, datetime

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow
from app.models.types import EncryptedText, JSONType

DEFAULT_PRIVACY = {
    "hide_name": True,  # до принятия приглашения работодатель видит только код кандидата
    "hide_current_company": True,
    "show_salary": True,
    "show_fsp": True,
    "show_tasks": True,
}


class CandidateProfile(Base):
    """Профиль кандидата.

    Разделяет данные на три слоя:
      * самоописание (резюме/анкета) — skills, experience, declared_grade;
      * верифицированные данные (тест, ФСП, задачи) — grade, theta, topic_scores, verified_skills, fsp_*;
      * служебные (кэш рейтинга, синтетическая «истина» для валидации).
    Категория, видимая работодателю, = (specialization, grade) и формируется только из верифицированного слоя.
    """

    __tablename__ = "candidate_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    public_code: Mapped[str] = mapped_column(String(16), unique=True)

    # --- самоописание ---
    # ФИО и контакты хранятся зашифрованными (AES-256-GCM): утечка дампа БД не раскрывает, кому звонить
    full_name: Mapped[str | None] = mapped_column(EncryptedText("candidate.full_name"))
    headline: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(EncryptedText("candidate.phone"))
    telegram: Mapped[str | None] = mapped_column(EncryptedText("candidate.telegram"))
    github: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    relocation: Mapped[bool] = mapped_column(Boolean, default=False)
    about: Mapped[str | None] = mapped_column(Text)
    experience_years: Mapped[float | None] = mapped_column(Float)
    work_formats: Mapped[list] = mapped_column(JSONType, default=list)
    salary_from: Mapped[int | None] = mapped_column(Integer)
    salary_to: Mapped[int | None] = mapped_column(Integer)
    search_status: Mapped[str] = mapped_column(String(16), default="open")  # active | open | not_looking
    skills: Mapped[list] = mapped_column(JSONType, default=list)  # заявленные навыки (строки из онтологии)
    roles: Mapped[list] = mapped_column(JSONType, default=list)
    soft_skills: Mapped[list] = mapped_column(JSONType, default=list)
    domains: Mapped[list] = mapped_column(JSONType, default=list)
    experience: Mapped[list] = mapped_column(JSONType, default=list)
    education: Mapped[list] = mapped_column(JSONType, default=list)
    resume_text: Mapped[str | None] = mapped_column(Text)
    resume_filename: Mapped[str | None] = mapped_column(String(200))

    # --- результаты опроса ---
    direction: Mapped[str | None] = mapped_column(String(32))
    specialization: Mapped[str | None] = mapped_column(String(32), index=True)
    primary_lang: Mapped[str | None] = mapped_column(String(32))
    framework: Mapped[str | None] = mapped_column(String(32))
    team_role: Mapped[str | None] = mapped_column(String(32))
    declared_grade: Mapped[str | None] = mapped_column(String(16))
    survey_completed_at: Mapped[datetime | None]

    # --- верифицированный слой ---
    grade: Mapped[str | None] = mapped_column(String(16), index=True)
    grade_confirmed_at: Mapped[datetime | None]
    grade_locked_until: Mapped[datetime | None]
    theta: Mapped[float | None] = mapped_column(Float)
    theta_se: Mapped[float | None] = mapped_column(Float)
    topic_scores: Mapped[dict] = mapped_column(JSONType, default=dict)
    verified_skills: Mapped[list] = mapped_column(JSONType, default=list)
    last_attempt_id: Mapped[int | None] = mapped_column(Integer)

    fsp_id: Mapped[str | None] = mapped_column(String(32), index=True)
    fsp_linked_at: Mapped[datetime | None]
    fsp_synced_at: Mapped[datetime | None]
    fsp_profile: Mapped[dict | None] = mapped_column(JSONType)
    fsp_score: Mapped[float] = mapped_column(Float, default=0.0)

    tasks_done: Mapped[int] = mapped_column(Integer, default=0)
    task_score: Mapped[float | None] = mapped_column(Float)
    last_activity_at: Mapped[datetime | None]

    # --- настройки ---
    privacy: Mapped[dict] = mapped_column(JSONType, default=lambda: dict(DEFAULT_PRIVACY))
    visible: Mapped[bool] = mapped_column(Boolean, default=False)  # согласие на публикацию профиля работодателям

    # --- кэш ранжирования ---
    strength: Mapped[float] = mapped_column(Float, default=0.0)
    category_percentile: Mapped[float | None] = mapped_column(Float)

    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    # adult — 18+; minor — 15–17 лет: регистрация с согласием законного представителя, работодатель видит ограничения ТК РФ
    age_group: Mapped[str] = mapped_column(String(16), default="adult", server_default="adult")
    synthetic_truth: Mapped[dict | None] = mapped_column(JSONType)  # только для валидации, наружу не отдаётся

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="candidate")
    achievements = relationship(
        "FspAchievement", back_populates="candidate", cascade="all, delete-orphan", order_by="FspAchievement.event_date.desc()"
    )
    extra_categories = relationship(
        "CandidateCategory", back_populates="candidate", cascade="all, delete-orphan", order_by="CandidateCategory.created_at"
    )


# Поля категории: у основной они хранятся в профиле, у дополнительной — в CandidateCategory (одинаковые имена)
CATEGORY_FIELDS = ("direction", "specialization", "primary_lang", "framework", "declared_grade", "grade", "grade_confirmed_at",
                   "grade_locked_until", "theta", "theta_se", "topic_scores", "verified_skills", "last_attempt_id")


class CandidateCategory(Base):
    """Дополнительная категория кандидата (специализация × грейд) — например, backend-разработчик, который ещё и DevOps.

    Основная категория хранится в профиле: по ней проходит тест и строится «Рост и зарплаты». Дополнительную можно
    сделать основной — поля категорий меняются местами (снимок CATEGORY_FIELDS), поэтому у каждой категории свои грейд,
    результат теста, блокировка смены грейда и подтверждённые навыки. Работодатель находит кандидата во всех его категориях;
    неподтверждённая тестом дополнительная категория показывается, как и основная, со статусом и ниже подтверждённых.
    """

    __tablename__ = "candidate_categories"
    __table_args__ = (UniqueConstraint("user_id", "specialization", name="uq_candidate_category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.user_id", ondelete="CASCADE"), index=True)
    direction: Mapped[str | None] = mapped_column(String(32))
    specialization: Mapped[str] = mapped_column(String(32), index=True)
    primary_lang: Mapped[str | None] = mapped_column(String(32))
    framework: Mapped[str | None] = mapped_column(String(32))
    declared_grade: Mapped[str | None] = mapped_column(String(16))
    grade: Mapped[str | None] = mapped_column(String(16))
    grade_confirmed_at: Mapped[datetime | None]
    grade_locked_until: Mapped[datetime | None]
    theta: Mapped[float | None] = mapped_column(Float)
    theta_se: Mapped[float | None] = mapped_column(Float)
    topic_scores: Mapped[dict] = mapped_column(JSONType, default=dict)
    verified_skills: Mapped[list] = mapped_column(JSONType, default=list)
    last_attempt_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    candidate = relationship("CandidateProfile", back_populates="extra_categories")


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.user_id", ondelete="CASCADE"), index=True)
    answers: Mapped[dict] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class GradeChange(Base):
    __tablename__ = "grade_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.user_id", ondelete="CASCADE"), index=True)
    specialization: Mapped[str] = mapped_column(String(32))
    from_grade: Mapped[str | None] = mapped_column(String(16))
    to_grade: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(32))  # initial | upgrade | retest_up | retest_down
    attempt_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class FspAchievement(Base):
    """Достижение участника, полученное из реестра ФСП (верифицированный источник)."""

    __tablename__ = "fsp_achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.user_id", ondelete="CASCADE"), index=True)
    result_id: Mapped[str] = mapped_column(String(64))
    event_id: Mapped[str] = mapped_column(String(64))
    event_name: Mapped[str] = mapped_column(String(300))
    discipline: Mapped[str] = mapped_column(String(32))
    level: Mapped[str] = mapped_column(String(32))
    event_date: Mapped[date] = mapped_column(Date)
    place: Mapped[int | None] = mapped_column(Integer)
    participants: Mapped[int | None] = mapped_column(Integer)
    result_title: Mapped[str] = mapped_column(String(64))
    team_name: Mapped[str | None] = mapped_column(String(200))
    team_role: Mapped[str | None] = mapped_column(String(64))
    stack: Mapped[list] = mapped_column(JSONType, default=list)
    percentile: Mapped[float | None] = mapped_column(Float)
    diploma_url: Mapped[str | None] = mapped_column(String(300))
    signature: Mapped[str | None] = mapped_column(String(128))
    verified: Mapped[bool] = mapped_column(Boolean, default=True)

    candidate = relationship("CandidateProfile", back_populates="achievements")
