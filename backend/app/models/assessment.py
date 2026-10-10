from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow
from app.models.types import JSONType


class TestAttempt(Base):
    """Попытка адаптивного тестирования на заявленный грейд."""

    __test__ = False  # не путать pytest: это модель, а не тест-класс

    __tablename__ = "test_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.user_id", ondelete="CASCADE"), index=True)
    specialization: Mapped[str] = mapped_column(String(32))
    lang: Mapped[str | None] = mapped_column(String(32))
    target_grade: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="in_progress")  # in_progress | completed | abandoned
    seed: Mapped[int] = mapped_column(Integer)
    blueprint: Mapped[dict] = mapped_column(JSONType)

    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None]
    deadline_at: Mapped[datetime]

    theta: Mapped[float | None] = mapped_column(Float)
    se: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    decision: Mapped[str | None] = mapped_column(String(32))  # confirmed | failed
    p_target: Mapped[float | None] = mapped_column(Float)  # P(θ ≥ порог заявленного грейда)
    upgrade_grade: Mapped[str | None] = mapped_column(String(16))
    upgrade_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    suggested_grade: Mapped[str | None] = mapped_column(String(16))
    topic_scores: Mapped[dict] = mapped_column(JSONType, default=dict)
    flags: Mapped[dict] = mapped_column(JSONType, default=dict)
    trajectory: Mapped[list] = mapped_column(JSONType, default=list)
    items_count: Mapped[int] = mapped_column(Integer, default=0)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)

    items = relationship("TestItem", back_populates="attempt", cascade="all, delete-orphan", order_by="TestItem.position")


class TestItem(Base):
    """Конкретный экземпляр задания, сгенерированный из шаблона для этой попытки."""

    __test__ = False

    __tablename__ = "test_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("test_attempts.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    template_id: Mapped[str] = mapped_column(String(64), index=True)
    competency: Mapped[str] = mapped_column(String(32))
    level: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))
    a: Mapped[float] = mapped_column(Float)
    b: Mapped[float] = mapped_column(Float)
    c: Mapped[float] = mapped_column(Float)
    variant_seed: Mapped[int] = mapped_column(Integer)
    variant_hash: Mapped[str] = mapped_column(String(32), index=True)  # по нему сервер не выдаёт уже показанный вариант
    payload: Mapped[dict] = mapped_column(JSONType)  # то, что видит кандидат
    answer_key: Mapped[dict] = mapped_column(JSONType)  # хранится только на сервере
    response: Mapped[dict | None] = mapped_column(JSONType)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    time_limit_s: Mapped[int] = mapped_column(Integer)
    presented_at: Mapped[datetime] = mapped_column(default=utcnow)
    answered_at: Mapped[datetime | None]
    time_spent_ms: Mapped[int | None] = mapped_column(Integer)
    events: Mapped[dict] = mapped_column(JSONType, default=dict)  # уходы со вкладки, вставки и т.п.

    attempt = relationship("TestAttempt", back_populates="items")


class ItemStat(Base):
    """Статистика и калиброванные IRT-параметры шаблона (семейства изоморфных заданий)."""

    __tablename__ = "item_stats"

    template_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    administered: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    a: Mapped[float | None] = mapped_column(Float)
    b: Mapped[float | None] = mapped_column(Float)
    retired: Mapped[bool] = mapped_column(Boolean, default=False)
    drift_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    recent: Mapped[list] = mapped_column(JSONType, default=list)  # скользящее окно [theta, correct]
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
