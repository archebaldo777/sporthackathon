# 8. Сборка, развёртывание и локальный запуск

## 8.1. Docker Compose (рекомендуется)

Требования: Docker 24+ и Docker Compose v2; 2 CPU, 2 ГБ RAM (стек потребляет < 1 ГБ); свободные порты 8080, 8000, 8081, 8025.

```bash
git clone https://github.com/archebaldo777/sporthackathon.git draft && cd draft
cp .env.example .env            # при необходимости поменять секреты и адреса
docker compose up --build -d
docker compose ps               # все сервисы — Up / healthy
```

| Сервис | Порт | Назначение |
|---|---|---|
| frontend (nginx) | 8080 | веб-приложение, прокси `/api` → backend |
| backend | 8000 | API; Swagger — http://localhost:8080/api/docs |
| fsp-mock | 8081 | демо ФСП ID (OIDC) и реестр достижений |
| mailpit | 8025 | веб-почта демо-стенда (письма подтверждения e-mail) |
| db | — | PostgreSQL 16, том `pgdata` |

Первый старт: `start.sh` в контейнере backend генерирует ключ подписи JWT (том `backend-var`), создаёт схему БД и
заполняет синтетическими данными (под advisory-lock PostgreSQL), затем запускает 2 воркера uvicorn.

Сброс данных: `docker compose down -v && docker compose up -d`.

### Переменные окружения (основные)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://draft:draft@db:5432/draft` | строка подключения |
| `PUBLIC_URL` | `http://localhost:8080` | публичный адрес фронтенда (ссылки в письмах, QR в PDF, OIDC redirect) |
| `SECRET_KEY` | — | HMAC для подписи PDF-профилей и вебхуков — **заменить** |
| `JWT_ISSUER`, `ACCESS_TOKEN_TTL_MIN`, `REFRESH_TOKEN_TTL_DAYS` | `…/realms/draft`, 30, 14 | параметры токенов |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS`, `MAIL_FROM` | mailpit:1025 | почта |
| `DEMO_MODE`, `DEMO_MAILBOX_URL` | true, http://localhost:8025 | демо-подсказки на страницах |
| `FSP_OIDC_PUBLIC_BASE`, `FSP_OIDC_INTERNAL_BASE`, `FSP_REALM`, `FSP_CLIENT_ID`, `FSP_CLIENT_SECRET`, `FSP_REGISTRY_API` | см. compose | ФСП ID и реестр (п. 5.5) |
| `TEST_MIN_ITEMS`, `TEST_MAX_ITEMS`, `TEST_SE_TARGET` | 10, 16, 0.35 | длина и точность адаптивного теста |
| `GRADE_CHANGE_COOLDOWN_DAYS`, `RETAKE_SAME_GRADE_COOLDOWN_DAYS`, `MAX_ATTEMPTS_PER_30_DAYS` | 90, 14, 4 | ограничения пересдач |
| `TASK_ASSIGN_INTERVAL_DAYS`, `TASK_DUE_DAYS` | 7, 7 | регулярные задачи |
| `SEED_ON_START`, `SEED_CANDIDATES` | true, 720 | синтетические данные |
| `WEB_CONCURRENCY` | по числу ядер, до 4 | число воркеров uvicorn |
| `FIELD_ENCRYPTION_KEY` | производный от `SECRET_KEY` | ключ шифрования ФИО и контактов в БД (base64, 32 байта) |

### Публичный стенд одной командой

Нужен сервер с Docker (Ubuntu 22.04+, от 2 vCPU / 2 ГБ RAM) с открытыми портами 80 и 443. Домен не обязателен.

```bash
git clone https://github.com/archebaldo777/sporthackathon.git draft && cd draft
./deploy/deploy.sh                          # адреса вида https://draft.<ip>.sslip.io
BASE_DOMAIN=example.ru ./deploy/deploy.sh   # свой домен: A-записи draft., fsp., mail. → IP сервера
```

Скрипт генерирует `.env` со случайными секретами и поднимает стек с наложением `deploy/docker-compose.prod.yml`:
перед сервисами встаёт Caddy (`deploy/Caddyfile`) с автоматическими сертификатами Let's Encrypt, наружу открыты только
80/443, база, backend, мок ФСП ID и почта доступны лишь внутри сети Docker. Публичные адреса платформы и ФСП ID
прописываются в `PUBLIC_URL`, `FSP_OIDC_PUBLIC_BASE`, `JWT_ISSUER` и в список разрешённых адресов возврата OIDC.
Конфигурация проверена локально на доменах `*.localhost` (внутренний центр сертификации Caddy): HTTPS на всех
адресах, редирект HTTP → HTTPS, вход через ФСП ID через публичные адреса, аудит требований ТЗ — 73/73.

Для боевого режима: адрес Keycloak ФСП вместо мока (`FSP_OIDC_PUBLIC_BASE`, `FSP_OIDC_INTERNAL_BASE`), реальный
SMTP и `DEMO_MODE=false`, резервное копирование тома `pgdata` (`pg_dump` по расписанию).

### Если порт 443 уже занят другим сервисом

Так развёрнут демо-стенд: на сервере уже работает VPN (ocserv) на 443. Порт делится по имени без расшифровки трафика:
HAProxy (`deploy/haproxy-sni.cfg`, отдельный контейнер в сети хоста) смотрит на имя в TLS ClientHello — домены стенда
уходят в Caddy, всё остальное (другие домены и подключения по IP) — прежнему сервису, перенесённому на внутренний порт.
Оба получают реальный IP клиента через PROXY protocol, UDP 443 у VPN не меняется, клиентам VPN ничего перенастраивать не нужно.
Порт 80 занимает Caddy; сертификаты других сервисов хоста продлеваются через `certbot --webroot` (Caddy отдаёт файлы проверки
из `/var/www/acme`, список доменов — `ACME_WEBROOT_SITES`). На слабом сервере фронтенд собирается заранее (`npm run build`),
образ — из готового `dist` (`frontend/Dockerfile.prebuilt`).
Стенд работает на домене `sporthackathon.ru` (`APP_DOMAIN`, `FSP_DOMAIN=fsp.…`, `MAIL_DOMAIN=mail.…` в `.env`); дополнительные
имена (`www`, прежний технический адрес на sslip.io) перечислены в `APP_REDIRECT_FROM` — Caddy выпускает для них сертификаты
и переадресует на основной домен. HAProxy пропускает в стенд сам домен и все его поддомены (`DRAFT_SNI_DOMAIN`).

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.sni.yml up -d --build
docker run -d --name sni-proxy --network host --restart always --user root \
  -e DRAFT_SNI_SUFFIX=.46-29-164-196.sslip.io -e DRAFT_SNI_DOMAIN=sporthackathon.ru -e EXISTING_TLS_BACKEND=127.0.0.1:4443 \
  -v /etc/haproxy-sni/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro haproxy:2.8-alpine
```

### Демо-видео

`docs/demo/draft-demo.mp4` (4 минуты 20 секунд, 1440×900): сквозные сценарии кандидата и работодателя, механика тестирования,
валидация и вход через ФСП ID. Видео записывается автоматически сценарием `docs/demo_video.py` (headless Chrome +
DevTools Protocol, подписи на экране), поэтому его можно перезаписать после любых изменений интерфейса:

```bash
backend/.venv/bin/pip install imageio-ffmpeg && backend/.venv/bin/python docs/demo_video.py
```

## 8.2. Локальный запуск без Docker (разработка)

Требования: Python 3.12+ (проверено на 3.13), Node.js 20+ (проверено на 22), PostgreSQL 14+.

```bash
createdb draft
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cat > .env <<'EOF'
DATABASE_URL=postgresql+psycopg://localhost/draft
PUBLIC_URL=http://localhost:5173
EOF
.venv/bin/uvicorn app.main:app --port 8000 --reload
```

```bash
cd fsp-mock
../backend/.venv/bin/pip install -r requirements.txt
../backend/.venv/bin/uvicorn app.main:app --port 8081
```

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, прокси /api → localhost:8000
```

Без SMTP-сервера письма не отправляются, а код подтверждения выводится в лог backend (строка «SMTP недоступен…»).
Для локальной почты можно запустить только Mailpit: `docker run -p 1025:1025 -p 8025:8025 axllent/mailpit`.

## 8.3. Проверки

```bash
cd backend
createdb draft_test                                  # отдельная БД для тестов
.venv/bin/python -m pytest -q                        # 282 теста
.venv/bin/python -m app.validation.run_all           # процедура валидации → validation_results/ и docs/04-validation.md
.venv/bin/python -m app.validation.tune_matching     # подстройка весов подбора на отдельных наборах → app/matching/tuned_params.json
.venv/bin/python -m app.validation.code_exec --docker  # ключи ответов: исполнение кода на 9 языках в Docker-образах
cd ../frontend && npm test                           # 14 тестов компонентов (Vitest)
npm run build                                        # проверка типов и сборка
npx playwright test                                  # 7 браузерных сценариев на запущенном стенде (E2E_BASE_URL)
```

CI (`.github/workflows/ci.yml`) на каждую загрузку: автотесты бэкенда с компиляторами 9 языков, тесты и сборка фронтенда,
поиск секретов в истории (gitleaks), запуск всего стенда в Docker, сквозная проверка API и браузерные сценарии.

## 8.4. Частые проблемы

| Симптом | Решение |
|---|---|
| Не приходит письмо с кодом | открыть Mailpit http://localhost:8025; локально без SMTP — код в логе backend |
| «ФСП ID временно недоступен» | проверить, что запущен fsp-mock (порт 8081) и совпадают `FSP_OIDC_*` |
| Ошибка `invalid_state` при входе через ФСП ID | сессия авторизации старше 10 минут — повторить вход |
| Порт занят | изменить левую часть маппинга портов в `docker-compose.yml` |
| Нужно сбросить демо-данные | `docker compose down -v` (локально — пересоздать БД) |
