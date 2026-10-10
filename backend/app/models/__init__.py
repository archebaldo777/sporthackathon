"""ORM-модели. Импорт всех модулей нужен, чтобы метаданные были полными (Alembic / create_all)."""
from app.models.user import AuditLog, Consent, Notification, OidcState, RefreshToken, User  # noqa: F401
from app.models.candidate import CandidateCategory, CandidateProfile, FspAchievement, GradeChange, SurveyResponse  # noqa: F401
from app.models.assessment import ItemStat, TestAttempt, TestItem  # noqa: F401
from app.models.employer import (  # noqa: F401
    ApiKey,
    Application,
    Company,
    EmployerTask,
    HiringNeed,
    Invitation,
    Message,
    Report,
    ShortlistEntry,
    TaskAssignment,
    Vacancy,
    Webhook,
    WebhookDelivery,
)
