#!/bin/sh
# Однократная подготовка (ключи JWT, схема БД, синтетические данные) до запуска воркеров,
# чтобы несколько процессов uvicorn использовали один ключ подписи и не заполняли БД параллельно.
set -e
python -c "from app.core.security import key_id; key_id()"
python -c "from app.seed.bootstrap import bootstrap; bootstrap()"
# за обратным прокси (nginx/Caddy) реальный IP клиента берётся из X-Forwarded-For — иначе лимиты запросов были бы общими на всех
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-$(python -c "import os; print(min(4, os.cpu_count() or 2))")}" --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}"
