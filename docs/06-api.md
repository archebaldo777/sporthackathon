# 6. Описание API

Все методы описаны спецификацией **OpenAPI 3** — интерактивно: `/api/docs` (Swagger UI) и `/api/redoc`, файл: [`docs/openapi.json`](openapi.json).
Всего 119 операций.

## Общие правила

* Базовый путь: `/api/v1`. Формат — JSON, кодировка UTF-8. Даты — ISO 8601 (UTC).
* Аутентификация: `Authorization: Bearer <access_token>` (JWT RS256, 30 минут). Обновление — `POST /auth/refresh` с ротацией refresh-токена (14 дней).
* Роли: `candidate`, `employer`, `admin`. Доступ к кабинетам — только с подтверждённым e-mail. ATS-методы — по заголовку `X-API-Key`.
* Ошибки — единый формат с машиночитаемым кодом:

```json
{"error": {"code": "not_eligible", "message": "Смена грейда возможна не чаще одного раза в 90 дней", "details": {"available_at": "2027-01-03T10:00:00+00:00"}}}
```

| Код | Значение |
|---|---|
| 400 | некорректный запрос (`invalid_code`, `invalid_salary`, …) |
| 401 | нет или недействителен токен (`unauthorized`, `token_expired`, `invalid_credentials`) |
| 403 | нет прав (`forbidden`) или не подтверждён e-mail (`email_not_verified`) |
| 404 | объект не найден или принадлежит другому пользователю (`not_found`) |
| 409 | конфликт состояния (`already_invited`, `not_eligible`, `attempt_closed`, `stale_item`, `email_taken`) |
| 422 | ошибка валидации (`validation_error` со списком полей) или признаки мошенничества (`risky_content`) |
| 423 | учётная запись временно заблокирована после 5 неудачных входов |
| 429 | превышен лимит запросов или суточный лимит приглашений (`rate_limited`, `invite_limit`) |
| 503 | недоступен внешний сервис ФСП (`fsp_unavailable`) |

## Ключевые сценарии

```bash
# регистрация кандидата → письмо с кодом → подтверждение (возвращает токены)
curl -X POST /api/v1/auth/register -d '{"email":"a@b.ru","password":"Secret123","role":"candidate","consent_pd":true,"consent_publication":true}'
curl -X POST /api/v1/auth/verify-email -d '{"email":"a@b.ru","code":"354777"}'
# опрос → тест → ответы
curl -X POST /api/v1/candidate/survey -d '{"direction":"development","specialization":"backend","primary_lang":"python","stack":["Python","PostgreSQL"],"experience_years":4,"declared_grade":"middle"}'
curl -X POST /api/v1/candidate/assessment/attempts -d '{"target_grade":"middle"}'           # → attempt_id + первое задание
curl -X POST /api/v1/candidate/assessment/attempts/42/answer -d '{"item_id":901,"response":"3","time_ms":41000,"events":{"blur":0}}'
# работодатель: потребность → подборка → приглашение
curl -X POST /api/v1/employer/needs/parse -d '{"text":"Ищем Middle Python-разработчика… 220 000 – 300 000 ₽"}'
curl -X POST /api/v1/employer/needs -d '{"title":"Python в биллинг","specialization":"backend","grades":["middle"],"must_skills":["Python","PostgreSQL"],"salary_from":220000,"salary_to":300000}'
curl '/api/v1/employer/needs/1/shortlist?skills=PostgreSQL&verified_only=true&within_budget=true'
curl -X POST /api/v1/employer/invitations -d '{"candidate_ids":[57],"title":"Python-разработчик","description":"…","salary_from":250000,"salary_to":300000,"contact_method":"hr@company.ru","need_id":1}'
# кандидат: принять приглашение (контакты раскрываются работодателю)
curl -X POST /api/v1/candidate/invitations/15/accept -d '{"message":"Готов к созвону"}'
```

## Аутентификация

| Метод | Путь | Назначение | Успех | Ошибки |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Регистрация по e-mail | 201 | 409, 422 |
| `POST` | `/api/v1/auth/verify-email` | Подтверждение e-mail кодом или токеном из письма | 200 | 400, 422 |
| `POST` | `/api/v1/auth/resend-verification` | Повторно отправить письмо с кодом | 202 | 422 |
| `POST` | `/api/v1/auth/login` | Вход по e-mail и паролю | 200 | 401, 422, 423 |
| `POST` | `/api/v1/auth/refresh` | Обновить access-токен (ротация refresh-токена) | 200 | 401, 422 |
| `POST` | `/api/v1/auth/logout` | Выход (отзыв refresh-токена) | 204 | 422 |
| `GET` | `/api/v1/auth/me` | Текущий пользователь | 200 | 401, 403, 422 |
| `GET` | `/api/v1/auth/jwks` | Публичные ключи подписи токенов (JWKS) | 200 |  |
| `GET` | `/api/v1/auth/.well-known/openid-configuration` | OIDC discovery платформы (Keycloak-совместимые claims) | 200 |  |
| `GET` | `/api/v1/auth/fsp/login` | Начать вход/регистрацию кандидата через ФСП ID | 200 | 503 |
| `GET` | `/api/v1/auth/fsp/link` | Начать связывание профиля кандидата с ФСП ID | 200 | 401, 403, 422 |
| `POST` | `/api/v1/auth/fsp/callback` | Завершение OIDC-авторизации ФСП ID | 200 | 400, 409, 422 |

## Кандидат

| Метод | Путь | Назначение | Успех | Ошибки |
|---|---|---|---|---|
| `GET` | `/api/v1/candidate/me` | Профиль кандидата с категорией, статусом и шагами онбординга | 200 | 401, 403, 422 |
| `PUT` | `/api/v1/candidate/profile` | Сохранить профиль/резюме (ручное заполнение или подтверждение распознанного PDF) | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/resume/parse` | Загрузка PDF-резюме с автораспознаванием полей | 200 | 400, 401, 403, 413, 422 |
| `POST` | `/api/v1/candidate/resume/parse-text` | Распознавание резюме из текста (вставка из буфера) | 200 | 401, 403, 422 |
| `GET` | `/api/v1/candidate/profile/pdf` | Стандартизированный PDF-профиль с QR-кодом проверки | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/survey` | Опрос по отрасли и специализации (обязательный шаг перед тестом) | 200 | 401, 403, 409, 422 |
| `GET` | `/api/v1/candidate/categories` | Мои категории: основная и дополнительные | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/categories` | Добавить дополнительную категорию (грейд заявленный — подтверждается тестом) | 201 | 401, 403, 409, 422 |
| `POST` | `/api/v1/candidate/categories/{spec}/main` | Сделать дополнительную категорию основной — чтобы пройти по ней тест | 200 | 401, 403, 404, 409, 422 |
| `DELETE` | `/api/v1/candidate/categories/{spec}` | Удалить дополнительную категорию | 200 | 401, 403, 404, 422 |
| `GET` | `/api/v1/candidate/history` | История опросов, попыток тестирования и изменений грейда | 200 | 401, 403, 422 |
| `GET` | `/api/v1/candidate/insights` | Зарплатный радар и путь роста по данным категории (обезличенно) | 200 | 401, 403, 422 |
| `GET` | `/api/v1/candidate/invitations` | Входящие приглашения от работодателей (только свои) | 200 | 401, 403, 422 |
| `GET` | `/api/v1/candidate/invitations/{inv_id}` | Приглашение (при открытии отмечается как просмотренное) | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/invitations/{inv_id}/accept` | Принять приглашение — контакты раскрываются работодателю | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/invitations/{inv_id}/decline` | Отклонить приглашение с причиной (обратная связь работодателю) | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/invitations/{inv_id}/contacts` | Закрыть или снова открыть работодателю доступ к своим контактам | 200 | 401, 403, 409, 422 |
| `GET` | `/api/v1/candidate/invitations/{inv_id}/messages` | Переписка с работодателем по принятому приглашению | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/invitations/{inv_id}/messages` | Написать работодателю (после принятия приглашения) | 201 | 401, 403, 409, 422, 429 |
| `POST` | `/api/v1/candidate/invitations/{inv_id}/report` | Пожаловаться на приглашение (антифрод) | 201 | 401, 403, 422 |
| `GET` | `/api/v1/candidate/applications` | Мои отклики и их статусы | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/applications` | Откликнуться на вакансию (контакты раскрываются работодателю) | 201 | 401, 403, 404, 409, 422 |
| `DELETE` | `/api/v1/candidate/applications/{app_id}` | Отозвать отклик | 200 | 401, 403, 422 |
| `GET` | `/api/v1/candidate/tasks` | Текущая регулярная задача и история | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/tasks/request` | Получить новую задачу сейчас (если нет активной) | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/tasks/{assignment_id}/submit` | Отправить решение или подход к решению | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/tasks/{assignment_id}/skip` | Пропустить задачу | 200 | 401, 403, 422 |
| `PUT` | `/api/v1/candidate/settings/privacy` | Настройки приватности и видимости профиля | 200 | 401, 403, 409, 422 |
| `GET` | `/api/v1/candidate/consents` | Текущие согласия и журнал изменений | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/consents` | Дать или отозвать согласие | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/fsp/sync` | Обновить достижения из реестра ФСП (сервисный токен реестра) | 200 | 401, 403, 422, 503 |
| `DELETE` | `/api/v1/candidate/fsp` | Отвязать ФСП ID и удалить полученные достижения | 200 | 401, 403, 422 |
| `GET` | `/api/v1/candidate/export` | Выгрузка всех персональных данных (право субъекта ПДн, 152-ФЗ ст. 14) | 200 | 401, 403, 422 |
| `DELETE` | `/api/v1/candidate/account` | Удалить аккаунт и все персональные данные | 204 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/demo/reset` | Демо-стенд: начать путь заново (только newbie и expert1–5) | 200 | 401, 403, 422 |

## Тестирование

| Метод | Путь | Назначение | Успех | Ошибки |
|---|---|---|---|---|
| `GET` | `/api/v1/candidate/assessment/eligibility` | На какие грейды можно пройти тест сейчас (с учётом ограничений по частоте) | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/assessment/attempts` | Начать тест на выбранный грейд (возвращает первое задание) | 201 | 401, 403, 409, 422 |
| `GET` | `/api/v1/candidate/assessment/attempts/{attempt_id}` | Состояние попытки: текущее задание или итог | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/assessment/attempts/{attempt_id}/answer` | Ответ на текущее задание; возвращает следующее задание или итог | 200 | 401, 403, 409, 422 |
| `POST` | `/api/v1/candidate/assessment/attempts/{attempt_id}/expert/answer` | Режим эксперта (демо): ответить на текущее задание верно или неверно | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/assessment/attempts/{attempt_id}/expert/simulate` | Режим эксперта (демо): пройти оставшиеся задания как кандидат уровня θ (модель IRT 3PL) | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/assessment/attempts/{attempt_id}/finish` | Досрочно завершить попытку (оставшиеся задания не засчитываются) | 200 | 401, 403, 422 |
| `POST` | `/api/v1/candidate/assessment/attempts/{attempt_id}/upgrade` | Начать отдельный тест на грейд выше по предложению из результата (без ожидания 90 дней, вне лимита попыток) | 201 | 401, 403, 409, 422 |

## Работодатель

| Метод | Путь | Назначение | Успех | Ошибки |
|---|---|---|---|---|
| `GET` | `/api/v1/employer/company` | Профиль компании и индекс доверия | 200 | 401, 403, 422 |
| `PUT` | `/api/v1/employer/company` | Обновить профиль компании | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/dashboard` | Сводка: потребности, приглашения, отклики, задачи | 200 | 401, 403, 422 |
| `POST` | `/api/v1/employer/needs/parse` | Разбор текстового описания потребности (NLP): специализация, грейд, стек, вилка, формат | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/needs` | Мои потребности | 200 | 401, 403, 422 |
| `POST` | `/api/v1/employer/needs` | Описать потребность — система сформирует подборку кандидатов | 201 | 401, 403, 422 |
| `GET` | `/api/v1/employer/needs/{need_id}` | Потребность и рекомендованные категории | 200 | 401, 403, 422 |
| `PUT` | `/api/v1/employer/needs/{need_id}` | Изменить потребность (подборка пересчитывается, пометки сохраняются) | 200 | 401, 403, 422 |
| `DELETE` | `/api/v1/employer/needs/{need_id}` | Архивировать потребность | 200 | 401, 403, 422 |
| `POST` | `/api/v1/employer/needs/{need_id}/run` | Обновить подборку (новые кандидаты, свежие результаты) | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/needs/{need_id}/shortlist` | Подборка с уточняющими фильтрами (без потери исходной подборки) | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/needs/{need_id}/compare` | Сравнить 2–3 кандидатов по потребности: компоненты оценки и «почему A выше B» | 200 | 400, 401, 403, 422 |
| `PUT` | `/api/v1/employer/needs/{need_id}/shortlist/{candidate_id}` | Пометить кандидата в подборке (избранное/скрыть/заметка) | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/needs/{need_id}/test-plan` | Как система тестирует кандидатов под эту потребность: план и примеры заданий | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/categories` | Карта категорий: специализации × грейды, объём, доля ФСП, медианные ожидания | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/candidates` | Поиск по банку кандидатов с фильтрами | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/candidates/{candidate_id}` | Профиль кандидата (контакты — только после принятия приглашения/отклика) | 200 | 401, 403, 422 |
| `POST` | `/api/v1/employer/invitations` | Пригласить кандидата(ов): описание, вилка (обязательно), способ связи | 201 | 401, 403, 409, 422, 429 |
| `GET` | `/api/v1/employer/invitations` | Мои приглашения и их статусы | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/invitations/{inv_id}` | Приглашение | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/invitations/{inv_id}/messages` | Переписка с кандидатом по принятому приглашению | 200 | 401, 403, 422 |
| `POST` | `/api/v1/employer/invitations/{inv_id}/messages` | Написать кандидату (после принятия приглашения) | 201 | 401, 403, 409, 422, 429 |
| `POST` | `/api/v1/employer/invitations/{inv_id}/withdraw` | Отозвать неотвеченное приглашение | 200 | 401, 403, 422 |
| `PUT` | `/api/v1/employer/invitations/{inv_id}/stage` | Этап после принятия: знакомство → интервью → оффер → выход | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/analytics` | Аналитика приглашений: конверсия, причины отказов, воронка | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/vacancies` | Мои вакансии | 200 | 401, 403, 422 |
| `POST` | `/api/v1/employer/vacancies` | Опубликовать вакансию (зарплатная вилка обязательна) | 201 | 401, 403, 422 |
| `GET` | `/api/v1/employer/vacancies/{vid}` | Вакансия | 200 | 401, 403, 422 |
| `PUT` | `/api/v1/employer/vacancies/{vid}` | Редактировать вакансию | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/vacancies/{vid}/applications` | Отклики на вакансию (контакты откликнувшихся раскрыты) | 200 | 401, 403, 422 |
| `PUT` | `/api/v1/employer/applications/{app_id}` | Статус отклика: просмотрен, интервью, оффер, отказ | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/vacancies/{vid}/recommended` | Рекомендованные кандидаты под вакансию (пригласить напрямую) | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/vacancies/{vid}/test-plan` | План тестирования кандидатов под вакансию и примеры сгенерированных заданий | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/tasks` | Мои задачи для регулярных заданий | 200 | 401, 403, 422 |
| `POST` | `/api/v1/employer/tasks` | Создать короткую задачу (система будет предлагать её кандидатам категории) | 201 | 401, 403, 422 |
| `PUT` | `/api/v1/employer/tasks/{tid}` | Изменить задачу | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/tasks/{tid}` | Задача и решения кандидатов | 200 | 401, 403, 422 |
| `POST` | `/api/v1/employer/tasks/{tid}/submissions/{aid}/review` | Оценить решение (1–5) — влияет на актуальность профиля кандидата | 200 | 401, 403, 422 |
| `GET` | `/api/v1/employer/integrations` | API-ключи и вебхуки для интеграции с ATS | 200 | 401, 403, 422 |
| `POST` | `/api/v1/employer/api-keys` | Создать API-ключ (показывается один раз) | 201 | 401, 403, 422 |
| `DELETE` | `/api/v1/employer/api-keys/{kid}` | Отозвать API-ключ | 200 | 401, 403, 422 |
| `POST` | `/api/v1/employer/webhooks` | Подписать URL на события (подпись HMAC-SHA256) | 201 | 401, 403, 422 |
| `DELETE` | `/api/v1/employer/webhooks/{hid}` | Удалить вебхук | 200 | 401, 403, 422 |

## Справочники и публичные данные

| Метод | Путь | Назначение | Успех | Ошибки |
|---|---|---|---|---|
| `GET` | `/api/v1/catalog` | Справочник: направления, специализации, грейды, навыки, дисциплины ФСП | 200 |  |
| `GET` | `/api/v1/public/stats` | Статистика платформы для главной страницы | 200 |  |
| `GET` | `/api/v1/public/verify/{token}` | Проверка подлинности PDF-профиля по QR-коду | 200 | 404, 422 |
| `GET` | `/api/v1/vacancies` | Опубликованные вакансии; для кандидата — с оценкой соответствия | 200 | 422 |
| `GET` | `/api/v1/vacancies/{vid}` | Вакансия | 200 | 404, 422 |
| `GET` | `/api/v1/notifications` | Мои уведомления | 200 | 401, 403, 422 |
| `POST` | `/api/v1/notifications/read-all` | Отметить все как прочитанные | 200 | 401, 403, 422 |
| `GET` | `/api/v1/mechanics/bank` | Обзор банка шаблонов-генераторов | 200 |  |
| `GET` | `/api/v1/mechanics/preview` | Сгенерировать несколько вариантов одного шаблона (без ключей) | 200 | 422 |
| `GET` | `/api/v1/mechanics/simulate` | Симуляция адаптивного теста для «виртуального кандидата» | 200 | 422 |
| `GET` | `/api/v1/validation/report` | Результаты процедуры валидации тестирования и подбора | 200 |  |
| `POST` | `/api/v1/validation/external-eval` | Оценка подбора на своём размеченном наборе пар «вакансия — кандидат» | 200 | 400, 422, 429 |
| `GET` | `/api/v1/validation/external-eval/example` | Пример размеченного набора пар в формате проверки (из синтетической популяции, разметка по скрытой истине) | 200 |  |
| `GET` | `/api/health` | Проверка работоспособности | 200 |  |

## ATS-интеграция

| Метод | Путь | Назначение | Успех | Ошибки |
|---|---|---|---|---|
| `GET` | `/api/v1/ats/v1/candidates` | Кандидаты, принявшие приглашения (с контактами) — для импорта в ATS | 200 | 401, 422 |
| `GET` | `/api/v1/ats/v1/vacancies` | Вакансии компании на платформе (с идентификаторами ATS) | 200 | 401, 422 |
| `PUT` | `/api/v1/ats/v1/vacancies/{external_id}` | Создать или обновить вакансию из ATS (специализацию, грейд и навыки распознает разбор текста) | 200 | 401, 422 |
| `GET` | `/api/v1/ats/v1/applications` | Отклики на вакансии компании (с контактами откликнувшихся) — для импорта в ATS | 200 | 401, 422 |
| `PUT` | `/api/v1/ats/v1/applications/{app_id}/status` | Синхронизация статуса отклика из ATS (просмотрен, интервью, оффер, отказ) | 200 | 401, 404, 422 |
| `PUT` | `/api/v1/ats/v1/invitations/{inv_id}/stage` | Синхронизация этапа воронки из ATS | 200 | 401, 422 |

## Администрирование

| Метод | Путь | Назначение | Успех | Ошибки |
|---|---|---|---|---|
| `GET` | `/api/v1/admin/overview` | Сводка платформы и очереди модерации | 200 | 401, 403, 422 |
| `POST` | `/api/v1/admin/recalibrate` | Онлайн-калибровка трудности шаблонов и детекция дрейфа (признак утечки) | 200 | 401, 403, 422 |
