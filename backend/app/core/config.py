"""Конфигурация приложения. Все параметры переопределяются переменными окружения (см. .env.example)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Драфт — ИТ-найм с верифицированным профилем ФСП"
    environment: str = "dev"  # dev | prod | test
    demo_mode: bool = True  # показывает демо-подсказки (демо-аккаунты, ссылка на почтовый ящик)

    database_url: str = "postgresql+psycopg://localhost/draft"

    # Публичный адрес фронтенда — используется в письмах, PDF (QR) и OIDC redirect
    public_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # JWT (RS256, совместимо по структуре claims с Keycloak)
    jwt_issuer: str = "http://localhost:8000/realms/draft"
    jwt_audience: str = "draft-web"
    access_token_ttl_min: int = 30
    refresh_token_ttl_days: int = 14
    jwt_private_key_path: str = str(BASE_DIR / "var" / "jwt_private.pem")
    secret_key: str = "dev-secret-change-me"  # HMAC для подписи PDF-профилей и webhooks
    field_encryption_key: str | None = None  # base64, 32 байта; по умолчанию — производный от SECRET_KEY

    # Почта (по умолчанию — Mailpit из docker-compose)
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False
    mail_from: str = "Драфт <no-reply@draft.local>"
    demo_mailbox_url: str = "http://localhost:8025"

    # ФСП ID (Keycloak-совместимый OIDC-провайдер) и реестр достижений
    fsp_oidc_public_base: str = "http://localhost:8081"  # адрес, который видит браузер
    fsp_oidc_internal_base: str = "http://localhost:8081"  # адрес, который видит backend
    fsp_realm: str = "fsp"
    fsp_client_id: str = "draft-platform"
    fsp_client_secret: str = "draft-secret"
    fsp_registry_api: str = "http://localhost:8081/api/v1"
    fsp_seed_registry_path: str = str(BASE_DIR.parent / "fsp-mock" / "data" / "registry.json")

    # Механика тестирования
    test_min_items: int = 8
    test_max_items: int = 22
    test_coverage_items: int = 14
    test_decision_confidence: float = 0.85
    grade_change_cooldown_days: int = 90
    retake_same_grade_cooldown_days: int = 14
    max_attempts_per_30_days: int = 4

    # Регулярные задачи
    task_assign_interval_days: int = 7
    task_due_days: int = 7

    # Антифрод
    invitations_daily_limit_low: int = 15
    invitations_daily_limit_mid: int = 40
    invitations_daily_limit_high: int = 120

    seed_on_start: bool = True
    seed_candidates: int = 720

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def fsp_issuer_public(self) -> str:
        return f"{self.fsp_oidc_public_base}/realms/{self.fsp_realm}"

    @property
    def fsp_issuer_internal(self) -> str:
        return f"{self.fsp_oidc_internal_base}/realms/{self.fsp_realm}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
