"""Схемы запросов/ответов API (Pydantic v2). Описания полей попадают в OpenAPI."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Role = Literal["candidate", "employer"]
GradeCode = Literal["intern", "junior", "middle", "senior"]
SpecCode = Literal["backend", "frontend", "mobile", "ml", "data_analyst", "devops", "qa", "infosec"]
FormatCode = Literal["office", "hybrid", "remote"]


class Flexible(BaseModel):
    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------- auth
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="Не короче 8 символов, буквы и цифры")
    role: Role
    company_name: str | None = Field(None, max_length=200, description="Обязательно для работодателя")
    consent_pd: bool = Field(description="Согласие на обработку персональных данных (152-ФЗ)")
    consent_publication: bool = Field(False, description="Согласие на публикацию профиля для работодателей (кандидат)")
    age_group: Literal["adult", "minor"] = Field("adult", description="Кандидат: adult — 18+, minor — 15–17 лет (младше 15 регистрация недоступна)")
    guardian_consent: bool = Field(False, description="Для 15–17 лет: согласие законного представителя на обработку ПДн получено")

    @field_validator("password")
    @classmethod
    def strong(cls, v: str) -> str:
        if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
            raise ValueError("Пароль должен содержать буквы и цифры")
        return v

    @model_validator(mode="after")
    def check(self):
        if not self.consent_pd:
            raise ValueError("Необходимо согласие на обработку персональных данных")
        if self.role == "employer" and not (self.company_name or "").strip():
            raise ValueError("Укажите название компании")
        if self.role == "candidate" and self.age_group == "minor" and not self.guardian_consent:
            raise ValueError("Для кандидатов 15–17 лет нужно согласие законного представителя на обработку персональных данных")
        return self


class VerifyIn(BaseModel):
    email: EmailStr | None = None
    code: str | None = Field(None, min_length=6, max_length=6)
    token: str | None = Field(None, description="Токен из ссылки в письме (альтернатива коду)")


class EmailIn(BaseModel):
    email: EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    email_verified: bool
    fsp_linked: bool
    display_name: str | None = None


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserOut


class RegisterOut(BaseModel):
    user_id: int
    email: str
    verification_sent: bool
    demo_mailbox_url: str | None = None


class FspAuthorizeOut(BaseModel):
    authorize_url: str


class FspCallbackIn(BaseModel):
    code: str
    state: str


class FspCallbackOut(BaseModel):
    intent: str
    tokens: TokenOut | None = None
    linked: bool = False
    fsp_id: str | None = None
    achievements: int = 0


# ---------------------------------------------------------------- кандидат
class Experience(BaseModel):
    company: str | None = None
    title: str | None = None
    start: str | None = None
    end: str | None = None
    description: str | None = None


class ProfileIn(BaseModel):
    full_name: str | None = Field(None, max_length=200)
    headline: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=32)
    telegram: str | None = Field(None, max_length=64)
    github: str | None = Field(None, max_length=200)
    city: str | None = Field(None, max_length=100)
    relocation: bool | None = None
    about: str | None = Field(None, max_length=4000)
    experience_years: float | None = Field(None, ge=0, le=60)
    work_formats: list[FormatCode] | None = None
    salary_from: int | None = Field(None, ge=0, le=5_000_000)
    salary_to: int | None = Field(None, ge=0, le=5_000_000)
    search_status: Literal["active", "open", "not_looking"] | None = None
    skills: list[str] | None = None
    roles: list[str] | None = None
    soft_skills: list[str] | None = None
    domains: list[str] | None = None
    experience: list[Experience] | None = None
    education: list[dict] | None = None


class SurveyIn(BaseModel):
    direction: str
    specialization: SpecCode
    primary_lang: str | None = None
    framework: str | None = None
    stack: list[str] = Field(default_factory=list, description="Основной стек (навыки из онтологии)")
    experience_years: float = Field(ge=0, le=60)
    declared_grade: GradeCode
    team_role: str | None = None
    domains: list[str] = Field(default_factory=list)
    work_formats: list[FormatCode] = Field(default_factory=list)
    motivation: str | None = Field(None, max_length=1000)


class CategoryIn(BaseModel):
    specialization: SpecCode
    declared_grade: GradeCode = Field(description="Заявленный грейд: подтверждается только тестом")
    primary_lang: str | None = None
    framework: str | None = None


class PrivacyIn(BaseModel):
    hide_name: bool | None = None
    hide_current_company: bool | None = None
    show_salary: bool | None = None
    show_fsp: bool | None = None
    show_tasks: bool | None = None
    visible: bool | None = Field(None, description="Публиковать профиль в базе для работодателей (требует согласия)")


class ConsentIn(BaseModel):
    kind: Literal["pd_processing", "profile_publication", "fsp_data", "marketing"]
    granted: bool


class StartAttemptIn(BaseModel):
    target_grade: GradeCode


class AnswerIn(BaseModel):
    item_id: int
    response: Any = Field(description="Индекс варианта (single), список индексов (multi) или строка/число (input)")
    time_ms: int | None = Field(None, ge=0)
    events: dict | None = Field(None, description="Клиентские события: blur (уходы со вкладки), paste (вставки)")


class DeclineIn(BaseModel):
    reason: Literal["salary", "format", "domain", "stack", "timing", "company", "other"]
    comment: str | None = Field(None, max_length=1000)


class AcceptIn(BaseModel):
    message: str | None = Field(None, max_length=1000, description="Сообщение работодателю")


class ReportIn(BaseModel):
    reason: Literal["fake", "spam", "payment", "rude", "other"]
    comment: str | None = Field(None, max_length=1000)


class ApplyIn(BaseModel):
    vacancy_id: int
    cover_letter: str | None = Field(None, max_length=3000)


class TaskSubmitIn(BaseModel):
    answer: str = Field(min_length=1, max_length=10000)


# ---------------------------------------------------------------- работодатель
class CompanyIn(BaseModel):
    name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=4000)
    industry: str | None = None
    website: str | None = Field(None, max_length=200)
    size: str | None = None
    city: str | None = None
    contact_name: str | None = Field(None, max_length=200)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(None, max_length=32)
    telegram: str | None = Field(None, max_length=64)
    inn: str | None = Field(None, pattern=r"^\d{10}$|^\d{12}$")


class ParseTextIn(BaseModel):
    text: str = Field(min_length=10, max_length=8000)


class NeedIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(None, max_length=8000, description="Чем занимается команда, задачи, контекст")
    specialization: SpecCode
    grades: list[GradeCode] = Field(min_length=1)
    must_skills: list[str] = Field(default_factory=list)
    nice_skills: list[str] = Field(default_factory=list)
    work_formats: list[FormatCode] = Field(default_factory=list)
    city: str | None = None
    salary_from: int = Field(gt=0, le=5_000_000, description="Нижняя граница вилки, ₽ в месяц до вычета НДФЛ (gross), обязательно")
    salary_to: int = Field(gt=0, le=5_000_000, description="Верхняя граница вилки, ₽ в месяц до вычета НДФЛ (gross), обязательно")
    fsp_weight: float = Field(0.5, ge=0, le=1, description="Насколько важны достижения ФСП (0–1)")
    domains: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def salary(self):
        if self.salary_from > self.salary_to:
            raise ValueError("Нижняя граница вилки больше верхней")
        return self


class MarkIn(BaseModel):
    mark: Literal["new", "starred", "hidden"]
    note: str | None = Field(None, max_length=500)


class InviteIn(BaseModel):
    candidate_ids: list[int] = Field(min_length=1, max_length=50)
    title: str = Field(min_length=3, max_length=200, description="Позиция / суть предложения")
    description: str = Field(min_length=20, max_length=5000, description="Описание предложения")
    salary_from: int = Field(gt=0, le=5_000_000, description="Зарплата от, ₽ в месяц до вычета НДФЛ (gross), обязательно")
    salary_to: int = Field(gt=0, le=5_000_000, description="Зарплата до, ₽ в месяц до вычета НДФЛ (gross), обязательно")
    work_format: FormatCode | None = None
    city: str | None = None
    contact_method: str = Field(min_length=3, max_length=300, description="Как связаться: e-mail, Telegram, телефон рекрутера")
    need_id: int | None = Field(None, description="Привязка к потребности (необязательно)")
    vacancy_id: int | None = Field(None, description="Привязка к вакансии (необязательно)")
    expires_in_days: int = Field(10, ge=1, le=30)


class StageIn(BaseModel):
    stage: Literal["contact", "interview", "offer", "hired", "closed"]


class AtsVacancyIn(BaseModel):
    """Вакансия из ATS работодателя. Специализацию, грейд и навыки можно не передавать — их распознает разбор текста."""

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=20, max_length=10000)
    salary_from: int = Field(gt=0, le=5_000_000, description="Вилка обязательна, gross в месяц")
    salary_to: int = Field(gt=0, le=5_000_000)
    specialization: SpecCode | None = None
    grade: GradeCode | None = None
    must_skills: list[str] | None = None
    nice_skills: list[str] | None = None
    work_formats: list[FormatCode] | None = None
    city: str | None = None
    status: Literal["draft", "published", "closed"] = "published"


class VacancyIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=20, max_length=10000)
    specialization: SpecCode
    grade: GradeCode
    must_skills: list[str] = Field(default_factory=list)
    nice_skills: list[str] = Field(default_factory=list)
    work_formats: list[FormatCode] = Field(default_factory=list)
    city: str | None = None
    salary_from: int = Field(gt=0, le=5_000_000)
    salary_to: int = Field(gt=0, le=5_000_000)
    status: Literal["draft", "published", "closed"] = "published"

    @model_validator(mode="after")
    def salary(self):
        if self.salary_from > self.salary_to:
            raise ValueError("Нижняя граница вилки больше верхней")
        return self


class ApplicationStatusIn(BaseModel):
    status: Literal["viewed", "interview", "offer", "rejected"]
    comment: str | None = Field(None, max_length=2000)


class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=20, max_length=8000)
    specialization: SpecCode
    grades: list[GradeCode] = Field(min_length=1)
    kind: Literal["solution", "approach"] = "approach"
    est_minutes: int = Field(30, ge=5, le=240)
    key_points: list[str] = Field(default_factory=list, description="Скрытая рубрика для автопроверки")
    skills: list[str] = Field(default_factory=list)
    active: bool = True


class ReviewIn(BaseModel):
    score: int = Field(ge=1, le=5)
    feedback: str | None = Field(None, max_length=3000)


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class WebhookIn(BaseModel):
    url: str = Field(pattern=r"^https?://", max_length=500)
    events: list[str] = Field(min_length=1)


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000, description="Текст сообщения")


class ContactsAccessIn(BaseModel):
    revoked: bool = Field(description="true — закрыть доступ к контактам, false — снова открыть")


class ExpertAnswerIn(BaseModel):
    item_id: int
    correct: bool


class ExpertSimulateIn(BaseModel):
    theta: float = Field(ge=-3, le=3, description="Уровень синтетического кандидата по шкале теста")
    seed: int | None = Field(None, description="Зерно для воспроизводимости ответов")
