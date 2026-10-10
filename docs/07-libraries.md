# 7. Используемые библиотеки и компоненты

Весь код открыт, не скомпилирован и не обфусцирован. Все зависимости — открытое ПО с разрешительными лицензиями
(MIT, BSD, Apache-2.0, ISC, PostgreSQL License, OFL для шрифтов).

## Backend (Python 3.13)

| Библиотека | Версия | Лицензия | Для чего |
|---|---|---|---|
| FastAPI | 0.142.2 | MIT | HTTP API, OpenAPI/Swagger |
| Starlette | 1.7.0 | BSD-3 | ASGI-основа FastAPI |
| Uvicorn (standard) | 0.54.0 | BSD-3 | ASGI-сервер |
| SQLAlchemy | 2.1.3 | MIT | ORM, слой хранения |
| psycopg (binary) | 3.3.6 | LGPL-3.0 (динамическая линковка) | драйвер PostgreSQL |
| Pydantic / pydantic-settings | 2.13.5 / 2.15.0 | MIT | схемы, валидация, конфигурация |
| email-validator | 2.3.0 | Unlicense | проверка e-mail |
| PyJWT (crypto) | 2.15.1 | MIT | JWT RS256, проверка id_token ФСП ID |
| cryptography | 50.0.2 | Apache-2.0 / BSD | RSA-ключи, JWKS |
| argon2-cffi | 25.1.0 | MIT | хеширование паролей Argon2id |
| httpx | 0.28.1 | BSD-3 | OIDC-клиент, реестр ФСП, вебхуки |
| python-multipart | 0.0.32 | Apache-2.0 | загрузка PDF-резюме |
| pypdf | 6.19.0 | BSD-3 | извлечение текста из PDF |
| ReportLab | 5.0.1 | BSD | генерация PDF-профиля, QR-код |
| RapidFuzz | 3.14.6 | MIT | нечёткое сопоставление навыков, автопроверка задач |
| NumPy | 2.5.3 | BSD-3 | IRT, EAP, калибровка |
| pytest | 9.1.1 | MIT | автотесты (dev) |
| matplotlib | 3.11.2 | PSF | графики валидации (dev) |
| sqlite3 (стандартная библиотека) | — | PSF | вычисление эталонных ответов SQL-заданий |

Свои реализации (без внешних ML-зависимостей, чтобы укладываться в скромные ресурсы): IRT 3PL, EAP, person-fit lz,
адаптивный алгоритм, онлайн-калибровка, TF-IDF по псевдоосновам слов, разбор резюме и потребностей, логистическая модель
вероятности принятия приглашения.

## Сервис fsp-mock

FastAPI 0.142.2, Uvicorn 0.54.0, PyJWT 2.15.1, cryptography 50.0.2, python-multipart 0.0.32.

## Frontend (Node.js 22)

| Библиотека | Версия | Лицензия | Для чего |
|---|---|---|---|
| React / React DOM | 18.3.1 | MIT | UI |
| React Router | 6.30.6 | MIT | маршрутизация |
| TanStack Query | 5.104.1 | MIT | запросы, кэш |
| Recharts | 3.10.1 | MIT | графики (радар компетенций, траектория CAT, валидация) |
| lucide-react | 1.52.0 | ISC | иконки |
| sonner | 2.0.8 | MIT | уведомления |
| clsx | 2.1.1 | MIT | классы |
| Tailwind CSS | 3.4.19 | MIT | стили |
| Vite | 5.4.21 | MIT | сборка, dev-сервер |
| TypeScript | 5.9.3 | Apache-2.0 | типизация |
| PostCSS / Autoprefixer | 8.5.28 / 10.6.1 | MIT | CSS-обработка |

Шрифты — из фирменного стиля ФСП, раздаются с собственного сервера (без внешних CDN, лицензии лежат рядом с файлами): JetBrains Mono (основной шрифт ФСП, OFL 1.1), TDAText (акцентный шрифт ФСП, OFL 1.1), Inter (основной шрифт флагманских проектов ФСП, OFL 1.1). Файлы урезаны до латиницы, кириллицы и нужных символов (`fontTools`) и сохранены в WOFF. В PDF-профиле кандидата — JetBrains Mono и TDAText из `backend/app/assets/fonts`, текст — DejaVu Sans.

## Инфраструктура

| Компонент | Версия | Лицензия |
|---|---|---|
| PostgreSQL | 16 (alpine) | PostgreSQL License |
| nginx | 1.27 (alpine) | BSD-2 |
| Mailpit | 1.21 | MIT |
| Docker / Docker Compose | 24+ / v2 | Apache-2.0 |
| Базовые образы | python:3.13-slim, node:22-alpine | — |
