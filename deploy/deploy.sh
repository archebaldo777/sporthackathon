#!/usr/bin/env bash
# Публичный демо-стенд «Драфт» на любом сервере с Docker (Ubuntu 22.04+, от 2 vCPU / 2 ГБ RAM, открыты порты 80 и 443).
#
#   git clone <репозиторий> draft && cd draft && ./deploy/deploy.sh
#
# Без своего домена адреса будут вида https://draft.<ip-через-дефисы>.sslip.io — публичный DNS sslip.io резолвит IP из имени,
# Caddy сам выпускает сертификаты Let's Encrypt. Со своим доменом: BASE_DOMAIN=example.ru ./deploy/deploy.sh
# (нужны A-записи draft., fsp. и mail. на IP сервера).
set -euo pipefail
cd "$(dirname "$0")/.."

command -v docker >/dev/null || { echo "Нужен Docker: curl -fsSL https://get.docker.com | sh"; exit 1; }
docker compose version >/dev/null || { echo "Нужен Docker Compose v2"; exit 1; }

IP="${PUBLIC_IP:-$(curl -fsS https://api.ipify.org || curl -fsS https://ifconfig.me)}"
BASE="${BASE_DOMAIN:-${IP//./-}.sslip.io}"
export APP_DOMAIN="${APP_DOMAIN:-draft.$BASE}" FSP_DOMAIN="${FSP_DOMAIN:-fsp.$BASE}" MAIL_DOMAIN="${MAIL_DOMAIN:-mail.$BASE}"

if [ ! -f .env ]; then
  rnd() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32; }
  cat > .env <<ENV
POSTGRES_PASSWORD=$(rnd)
SECRET_KEY=$(rnd)
FSP_CLIENT_SECRET=$(rnd)
DEMO_MODE=true
SEED_CANDIDATES=720
WEB_CONCURRENCY=2
ENV
  echo "Создан .env со случайными секретами."
fi

docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build

cat <<INFO

Стенд запускается (первый раз — 3–5 минут: сборка образов и заполнение демо-данных).
  Платформа:       https://$APP_DOMAIN
  API (Swagger):   https://$APP_DOMAIN/api/docs
  ФСП ID (мок):    https://$FSP_DOMAIN
  Демо-почта:      https://$MAIL_DOMAIN
Демо-аккаунты: candidate@draft.demo, newbie@draft.demo, employer@draft.demo — пароль Demo2026!
Статус: docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml ps
INFO
