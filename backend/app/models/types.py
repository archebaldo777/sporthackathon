from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# JSONB в PostgreSQL, JSON в остальных СУБД
JSONType = JSON().with_variant(JSONB(), "postgresql")


# ---------------------------------------------------------------- шифрование персональных данных в БД
import base64  # noqa: E402
import hashlib  # noqa: E402
import os  # noqa: E402
from functools import lru_cache  # noqa: E402

from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: E402
from sqlalchemy import Text  # noqa: E402
from sqlalchemy.types import TypeDecorator  # noqa: E402

ENC_PREFIX = "enc:v1:"


@lru_cache
def _aead() -> AESGCM:
    """Ключ: FIELD_ENCRYPTION_KEY (base64, 32 байта) или производный от SECRET_KEY (HKDF-подобно, SHA-256 с доменом)."""
    from app.core.config import settings

    raw = settings.field_encryption_key
    key = base64.b64decode(raw) if raw else hashlib.sha256(b"draft:field-encryption:" + settings.secret_key.encode()).digest()
    return AESGCM(key)


class EncryptedText(TypeDecorator):
    """Строка, хранящаяся в БД зашифрованной (AES-256-GCM, случайный nonce, связь с именем поля как AAD).

    Значения без префикса читаются как есть — старые записи расшифровывать не нужно, при следующем сохранении
    они будут зашифрованы. Поиск по таким полям в SQL невозможен — и не нужен: по ним не фильтруют.
    """

    impl = Text
    cache_ok = True

    def __init__(self, field: str):
        super().__init__()
        self.field = field

    def process_bind_param(self, value, dialect):
        if value is None or value == "":
            return value
        nonce = os.urandom(12)
        ct = _aead().encrypt(nonce, str(value).encode(), self.field.encode())
        return ENC_PREFIX + base64.b64encode(nonce + ct).decode()

    def process_result_value(self, value, dialect):
        if not value or not value.startswith(ENC_PREFIX):
            return value
        data = base64.b64decode(value[len(ENC_PREFIX):])
        return _aead().decrypt(data[:12], data[12:], self.field.encode()).decode()
