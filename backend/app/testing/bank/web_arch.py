"""HTTP/API, архитектура и проектирование, базовые инструменты разработчика (Git, Docker)."""
from __future__ import annotations

import math
import random

from app.testing.bank.base import GenCtx, Variant, pick_distractors, scenario_single, single, statements_multi, template

WEB_SPECS = ("backend", "frontend", "mobile", "qa")

STATUS_SCENARIOS = [
    (["Ресурс успешно создан в результате POST-запроса.", "Сервер создал новую запись и вернул её адрес в заголовке Location."], "201 Created"),
    (["Ресурс удалён, тело ответа пустое.", "PUT успешно выполнен, возвращать тело не требуется."], "204 No Content"),
    (["Запрос без токена к защищённому эндпоинту.", "Срок действия access-токена истёк, клиент должен заново аутентифицироваться."], "401 Unauthorized"),
    (["Пользователь аутентифицирован, но не имеет прав на ресурс.", "Обычный пользователь обращается к админскому API с валидным токеном."], "403 Forbidden"),
    (["Клиент превысил лимит запросов в минуту.", "Сработал rate limiter на стороне API."], "429 Too Many Requests"),
    (["Попытка зарегистрировать пользователя с уже занятым email.", "Конфликт версий при оптимистичной блокировке ресурса."], "409 Conflict"),
    (["JSON синтаксически корректен, но поле age отрицательное.", "Тело запроса корректно по формату, но не проходит бизнес-валидацию."], "422 Unprocessable Content"),
    (["Прокси получил некорректный ответ от вышестоящего сервиса.", "Nginx не смог получить валидный ответ от upstream."], "502 Bad Gateway"),
    (["Шлюз не дождался ответа от upstream-сервера.", "Балансировщик прервал запрос по таймауту ожидания бэкенда."], "504 Gateway Timeout"),
    (["Сервис временно недоступен из-за планового обслуживания.", "Сервер перегружен и просит повторить позже (Retry-After)."], "503 Service Unavailable"),
    (["На эндпоинт, поддерживающий только GET, пришёл DELETE.", "Метод запроса не поддерживается для данного ресурса."], "405 Method Not Allowed"),
    (["Условный запрос с If-None-Match, ресурс не изменился.", "ETag совпал, клиент может использовать кэшированную версию."], "304 Not Modified"),
]
STATUS_SPACE = [a for _, a in STATUS_SCENARIOS] + ["200 OK", "400 Bad Request", "404 Not Found", "500 Internal Server Error", "302 Found"]


@template("http.status", "HTTP: коды ответа", "web", WEB_SPECS, 1, "single", time_limit=90, method="pool")
def http_status(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, STATUS_SCENARIOS, STATUS_SPACE, prefix="Какой код ответа наиболее уместен? ")


@template("http.methods", "HTTP: семантика методов", "web", WEB_SPECS, 2, "multi", time_limit=150, method="pool")
def http_methods(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "GET — безопасный и идемпотентный метод",
        "PUT идемпотентен: повторный запрос приводит к тому же состоянию ресурса",
        "DELETE идемпотентен",
        "POST по спецификации не является идемпотентным",
        "HEAD возвращает те же заголовки, что и GET, но без тела ответа",
        "OPTIONS используется в CORS preflight-запросах",
        "PATCH в общем случае не является идемпотентным",
    ]
    false_pool = [
        "POST идемпотентен по спецификации HTTP",
        "PUT предназначен только для частичного обновления ресурса",
        "DELETE не идемпотентен, потому что изменяет состояние сервера",
        "GET-запрос не может содержать query-параметры",
        "Код 401 означает, что у аутентифицированного пользователя нет прав",
        "HTTP/2 требует отдельного TCP-соединения на каждый запрос",
    ]
    return statements_multi(rng, ["Какие утверждения о методах HTTP верны?"], true_pool, false_pool)


@template("http.cors_preflight", "CORS: когда браузер отправляет preflight", "web", ("backend", "frontend", "qa", "infosec"), 3, "multi",
          time_limit=180)
def cors_preflight(rng: random.Random, ctx: GenCtx) -> Variant:
    methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    ctypes = ["application/json", "text/plain", "application/x-www-form-urlencoded", "multipart/form-data"]
    headers_pool = [None, "Authorization: Bearer …", "X-Request-Id: 42", None]
    opts = []
    seen = set()
    while len(opts) < 5:
        m = rng.choice(methods)
        ct = rng.choice(ctypes) if m != "GET" else None
        h = rng.choice(headers_pool)
        key = (m, ct, h)
        if key in seen:
            continue
        seen.add(key)
        simple = m in ("GET", "HEAD", "POST") and (ct is None or ct != "application/json") and h is None
        desc = f"fetch с другого origin: {m}" + (f", Content-Type: {ct}" if ct else "") + (f", заголовок {h}" if h else "")
        opts.append((desc, not simple))
    if not any(ok for _, ok in opts):
        opts[0] = ("fetch с другого origin: PUT, Content-Type: application/json", True)
    return Variant(text="Для каких запросов браузер отправит preflight-запрос OPTIONS?", kind="multi", options=opts,
                   hint="Отметьте все подходящие")


@template("http.caching", "HTTP-кэширование", "web", ("backend", "frontend", "mobile"), 3, "single", time_limit=150)
def http_caching(rng: random.Random, ctx: GenCtx) -> Variant:
    max_age = rng.choice([60, 300, 600, 3600])
    t = rng.choice([max_age // 2, max_age + rng.randint(10, 300)])
    directive = rng.choice(["max-age", "max-age", "no-cache", "no-store"])
    etag = rng.random() < 0.6
    header = {"max-age": f"Cache-Control: max-age={max_age}", "no-cache": "Cache-Control: no-cache", "no-store": "Cache-Control: no-store"}[directive]
    header += '\nETag: "a1b2c3"' if etag else ""
    A = "Ответ берётся из кэша без обращения к серверу"
    B = "Отправляется условный запрос с If-None-Match, возможен ответ 304"
    C = "Отправляется обычный (безусловный) запрос за ресурсом"
    D = "Отправляется условный запрос с If-Modified-Since по дате Expires"
    if directive == "no-store":
        ans = C
    elif directive == "no-cache":
        ans = B if etag else C
    else:
        ans = A if t < max_age else (B if etag else C)
    return single(f"Ответ сервера содержал заголовки:\n\n```\n{header}\n```\n\nЧто произойдёт при повторном запросе того же ресурса через {t} с?",
                  ans, [x for x in (A, B, C, D) if x != ans])


REST_SCENARIOS = [
    (["Получить список заказов пользователя 42."], "GET /users/42/orders"),
    (["Создать новый заказ."], "POST /orders"),
    (["Полностью заменить данные заказа 7."], "PUT /orders/7"),
    (["Частично обновить статус заказа 7."], "PATCH /orders/7"),
    (["Удалить комментарий 15 к статье 3."], "DELETE /articles/3/comments/15"),
    (["Получить вторую страницу товаров по 20 штук."], "GET /products?page=2&size=20"),
]


@template("http.rest_design", "Проектирование REST API", "web", WEB_SPECS, 2, "single", time_limit=90, method="pool")
def rest_design(rng: random.Random, ctx: GenCtx) -> Variant:
    texts, correct = rng.choice(REST_SCENARIOS)
    wrong = ["POST /getUserOrders?id=42", "GET /orders/create", "POST /orders/7/update", "GET /deleteComment?id=15",
             "PUT /orders", "GET /products/page/2/size/20/list", "POST /users/42/orders/get"]
    others = [a for _, a in REST_SCENARIOS if a != correct]
    return single("Какой запрос лучше соответствует принципам REST? " + texts[0], correct, rng.sample(wrong, 2) + rng.sample(others, 1))


@template("http.api_reliability", "Надёжность API: идемпотентность, пагинация, версии", "web", ("backend", "mobile", "qa"), 3, "multi",
          time_limit=180, method="pool")
def api_reliability(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Заголовок Idempotency-Key позволяет безопасно повторять POST-запрос создания платежа",
        "Курсорная пагинация устойчивее offset-пагинации при вставке новых записей",
        "Повторные попытки (retry) имеет смысл делать с экспоненциальной задержкой и джиттером",
        "Таймаут на клиенте должен быть задан явно, иначе запрос может висеть неопределённо долго",
        "Обратно несовместимые изменения API принято выпускать в новой версии (например, /v2)",
        "Ответ 429 может содержать заголовок Retry-After",
    ]
    false_pool = [
        "Любой запрос можно безопасно повторять сколько угодно раз",
        "Offset-пагинация гарантирует отсутствие дублей при вставке данных во время листания",
        "Удаление поля из ответа API — обратно совместимое изменение",
        "Повторять запросы стоит без задержки, чтобы быстрее получить ответ",
        "Код 500 означает ошибку клиента в формате запроса",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


# ================================================================== архитектура
ARCH_SPECS = ("backend",)


@template("arch.capacity", "Оценка мощности: закон Литтла", "architecture", ARCH_SPECS, 3, "input", time_limit=210)
def arch_capacity(rng: random.Random, ctx: GenCtx) -> Variant:
    rps = rng.choice([800, 1200, 1500, 2000, 3000, 4500])
    lat = rng.choice([40, 50, 80, 100, 120, 200])
    workers = rng.choice([8, 16, 32])
    util = rng.choice([0.5, 0.6, 0.7, 0.8])
    concurrency = rps * lat / 1000
    ans = math.ceil(concurrency / (workers * util))
    return Variant(
        text=f"Сервис должен обрабатывать {rps} RPS, среднее время обработки запроса — {lat} мс. Один инстанс обслуживает "
        f"одновременно {workers} запросов. Чтобы выдерживать всплески, целевая загрузка инстанса — не выше {int(util * 100)}%. "
        "Какое минимальное число инстансов нужно?",
        kind="input",
        input_type="number",
        answer=ans,
    )


@template("arch.token_bucket", "Rate limiting: token bucket", "architecture", ARCH_SPECS, 4, "input", time_limit=240)
def token_bucket(rng: random.Random, ctx: GenCtx) -> Variant:
    cap, rate = rng.choice([5, 8, 10]), rng.choice([1, 2, 3])
    timeline = []
    for t in range(4):
        timeline.append((t, rng.randint(0, cap + 3)))
    tokens = cap
    rejected = 0
    prev_t = 0
    for t, n in timeline:
        tokens = min(cap, tokens + (t - prev_t) * rate)
        prev_t = t
        served = min(tokens, n)
        tokens -= served
        rejected += n - served
    tl = "\n".join(f"t = {t} c: {n} запросов" for t, n in timeline)
    return Variant(
        text=f"Rate limiter — token bucket ёмкостью {cap} токенов, пополнение {rate} токен(а) в секунду (дискретно, в начале каждой "
        "секунды, не выше ёмкости). В момент t = 0 ведро полное. Каждый запрос забирает 1 токен, при отсутствии токенов — отклоняется. "
        "Сколько запросов будет отклонено?",
        kind="input",
        input_type="number",
        answer=rejected,
        code=tl,
        code_lang="text",
    )


@template("arch.backoff", "Повторные попытки с экспоненциальной задержкой", "architecture", ("backend", "mobile", "devops"), 3, "input",
          time_limit=150)
def backoff(rng: random.Random, ctx: GenCtx) -> Variant:
    base, factor, k = rng.randrange(50, 1050, 50), rng.choice([2, 3]), rng.randint(3, 6)
    cap = rng.choice([None, None, base * factor ** rng.randint(1, k - 1)])
    delays = [base * factor**i for i in range(k)]
    if cap:
        delays = [min(d, cap) for d in delays]
    cap_txt = f", но не более {cap} мс" if cap else ""
    return Variant(
        text=f"Клиент повторяет неудачный запрос до {k} раз. Задержка перед i-й повторной попыткой (i = 0, 1, …) равна "
        f"{base} × {factor}^i мс{cap_txt}, без джиттера. Сколько миллисекунд суммарно клиент проведёт в ожидании, если все попытки неудачны?",
        kind="input", input_type="number", answer=sum(delays),
    )


@template("arch.availability", "Доступность системы из нескольких компонентов", "architecture", ("backend", "devops"), 3, "input",
          time_limit=180)
def availability(rng: random.Random, ctx: GenCtx) -> Variant:
    a = round(rng.uniform(99.0, 99.98), 2)
    b = round(rng.uniform(98.5, 99.95), 2)
    c = round(rng.uniform(99.5, 99.99), 2)
    form = rng.choice(["series", "redundant", "three"])
    if form == "redundant":
        total = a / 100 * (1 - (1 - b / 100) ** 2) * 100
        text = f"Запрос проходит через API (доступность {a}%) и затем через БД. БД развёрнута в двух независимых репликах, каждая с доступностью {b}%; достаточно одной живой."
    elif form == "three":
        total = a / 100 * b / 100 * c / 100 * 100
        text = f"Запрос последовательно проходит через балансировщик ({c}%), API ({a}%) и БД ({b}%). Отказы независимы."
    else:
        total = a / 100 * b / 100 * 100
        text = f"Запрос последовательно проходит через API (доступность {a}%) и БД (доступность {b}%). Отказы независимы."
    return Variant(text=text + " Какова итоговая доступность, % (до сотых)?", kind="input", input_type="number", answer=round(total, 2),
                   tolerance=0.011)


PATTERN_SCENARIOS = [
    (["Нужно согласованно провести бизнес-операцию в нескольких сервисах без распределённой транзакции.",
      "Оформление заказа затрагивает склад, оплату и доставку; при сбое нужно выполнить компенсирующие действия."], "Saga"),
    (["Зависимый сервис периодически «падает», нужно перестать слать ему запросы и быстро возвращать ошибку.",
      "Изолировать отказ медленной внешней зависимости, чтобы не исчерпать пулы потоков."], "Circuit Breaker"),
    (["Надёжно опубликовать событие в брокер вместе с изменением в БД, не теряя сообщений.",
      "Гарантировать, что событие отправится, только если транзакция в БД закоммичена."], "Transactional Outbox"),
    (["Разделить модели для записи и для сложных чтений с разными хранилищами.",
      "Нагрузка на чтение в сотни раз выше записи, нужны денормализованные представления."], "CQRS"),
    (["Единая точка входа для внешних клиентов: маршрутизация, аутентификация, rate limiting.",
      "Скрыть внутреннюю структуру микросервисов от мобильного приложения."], "API Gateway"),
    (["Постепенно заменить монолит новыми сервисами, перенаправляя часть функциональности.",
      "Мигрировать легаси-систему по частям без «большого взрыва»."], "Strangler Fig"),
]


@template("arch.patterns", "Архитектурные паттерны", "architecture", ARCH_SPECS, 3, "single", time_limit=120, method="pool")
def arch_patterns(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, PATTERN_SCENARIOS, [a for _, a in PATTERN_SCENARIOS] + ["Singleton", "Active Record"],
                           prefix="Какой паттерн подходит? ")


@template("arch.distributed", "Распределённые системы: согласованность и очереди", "architecture", ARCH_SPECS, 4, "multi",
          time_limit=210, method="pool")
def arch_distributed(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "При доставке «at-least-once» потребитель должен быть идемпотентным",
        "Kafka гарантирует порядок сообщений только в пределах одной партиции",
        "Согласно теореме CAP, при сетевом разделении приходится выбирать между согласованностью и доступностью",
        "Консистентное хеширование при добавлении узла перемещает лишь часть ключей, а не почти все",
        "Кворум чтения и записи с R + W > N обеспечивает чтение последней записанной версии",
        "Кэш-лавина (cache stampede) возникает, когда много запросов одновременно промахиваются по истёкшему ключу",
    ]
    false_pool = [
        "Exactly-once доставка между произвольными системами достигается без дедупликации и транзакций",
        "Kafka гарантирует глобальный порядок сообщений во всём топике при любом числе партиций",
        "Eventual consistency означает, что данные никогда не станут согласованными",
        "При хешировании по модулю числа узлов добавление узла перемещает лишь малую долю ключей",
        "Двухфазный коммит устойчив к отказу координатора без блокировок участников",
        "Горизонтальное масштабирование всегда проще для stateful-сервисов, чем для stateless",
    ]
    return statements_multi(rng, ["Какие утверждения о распределённых системах верны?"], true_pool, false_pool)


@template("arch.caching", "Стратегии кэширования", "architecture", ("backend", "frontend", "mobile"), 3, "single", time_limit=120,
          method="pool")
def arch_caching(rng: random.Random, ctx: GenCtx) -> Variant:
    scen = [
        (["Приложение сначала читает из кэша, при промахе — из БД и само кладёт результат в кэш."], "Cache-aside (lazy loading)"),
        (["Запись идёт одновременно в кэш и в БД синхронно, кэш всегда актуален."], "Write-through"),
        (["Запись сначала попадает в кэш, а в БД сбрасывается асинхронно пачками."], "Write-back (write-behind)"),
        (["Перед истечением TTL популярного ключа он обновляется заранее в фоне."], "Refresh-ahead"),
    ]
    return scenario_single(rng, scen, [a for _, a in scen] + ["Read-repair"], prefix="Как называется стратегия? ")


MOBILE_ARCH = [
    (["UI подписывается на поток состояния, а пользовательские действия отправляются как намерения в единый редьюсер."], "MVI"),
    (["View наблюдает за состоянием, которое хранит и переживает смену конфигурации отдельный объект с логикой представления."], "MVVM"),
    (["Бизнес-правила изолированы в слое use case и не зависят от фреймворков и UI."], "Clean Architecture"),
    (["Данные сначала показываются из локальной БД, затем синхронизируются с сервером в фоне."], "Offline-first с локальным кэшем"),
]


@template("mobile.arch", "Архитектура мобильных приложений", "architecture", ("mobile",), 3, "single", time_limit=120, method="pool")
def mobile_arch(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, MOBILE_ARCH, [a for _, a in MOBILE_ARCH] + ["MVC с толстым контроллером", "Singleton"],
                           prefix="О каком подходе идёт речь? ")


# ================================================================== Git, Docker (базовые инструменты)
GIT_SCENARIOS = [
    (["Отменить последний локальный коммит, сохранив изменения в индексе.", "Откатить последний коммит, но оставить изменения подготовленными к коммиту."], "git reset --soft HEAD~1"),
    (["Временно убрать незакоммиченные изменения, чтобы переключиться на другую ветку.", "Отложить текущую работу и получить чистую рабочую копию."], "git stash"),
    (["Перенести один конкретный коммит из другой ветки.", "Применить исправление из ветки hotfix в текущую ветку, не сливая всю ветку."], "git cherry-pick <sha>"),
    (["Безопасно отменить уже опубликованный (push) коммит в общей ветке.", "Создать коммит, отменяющий изменения ошибочного коммита в main."], "git revert <sha>"),
    (["Исправить сообщение последнего (ещё не опубликованного) коммита.", "Добавить забытый файл в последний локальный коммит."], "git commit --amend"),
    (["Найти коммит, в котором появился баг, бинарным поиском по истории.", "Автоматически найти коммит, сломавший тесты, между двумя версиями."], "git bisect"),
    (["Узнать, кто и в каком коммите последним менял строку файла.", "Посмотреть авторство каждой строки файла."], "git blame"),
]


@template("git.scenarios", "Git: команды для типовых ситуаций", "devops_basics", ("backend",), 2, "single", time_limit=90, method="pool")
def git_scenarios(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, GIT_SCENARIOS, [a for _, a in GIT_SCENARIOS] + ["git reset --hard origin/main", "git push --force"],
                           prefix="Какая команда подходит? ")


@template("ci.git_scenarios", "Git: команды для типовых ситуаций", "ci_cd", ("devops",), 2, "single", time_limit=90, method="pool")
def ci_git_scenarios(rng: random.Random, ctx: GenCtx) -> Variant:
    return git_scenarios(rng, ctx)


STACKS = {
    "python": ("python:3.12-slim", "requirements.txt", "RUN pip install --no-cache-dir -r requirements.txt", ["src/main.py", "src/api/routes.py"],
               'CMD ["python", "-m", "src.main"]'),
    "node": ("node:20-alpine", "package.json", "RUN npm ci", ["src/index.ts", "src/routes/users.ts"], 'CMD ["node", "dist/index.js"]'),
    "go": ("golang:1.23", "go.mod", "RUN go mod download", ["cmd/server/main.go", "internal/api/handler.go"], 'CMD ["./server"]'),
    "java": ("eclipse-temurin:21", "pom.xml", "RUN mvn -q dependency:go-offline", ["src/main/java/App.java", "src/main/java/Api.java"],
             'CMD ["java", "-jar", "app.jar"]'),
}
EXTRA = ['ENV TZ=Europe/Moscow', 'LABEL team="platform"', "RUN apt-get update && apt-get install -y curl", "ARG BUILD_ID", "EXPOSE 8080"]


def _dockerfile(rng: random.Random):
    stack = rng.choice(list(STACKS))
    base, deps_file, deps_cmd, code_files, cmd = STACKS[stack]
    steps = [(f"FROM {base}", None), ("WORKDIR /app", None)]
    for e in rng.sample(EXTRA, rng.randint(0, 2)):
        steps.append((e, None))
    if rng.random() < 0.3:  # «антипаттерн»: копирование всего проекта до установки зависимостей
        steps += [("COPY . .", "*"), (deps_cmd, None)]
    else:
        steps += [(f"COPY {deps_file} .", deps_file), (deps_cmd, None)]
        tail = [("COPY config/ ./config", "config/settings.yaml"), (f"COPY {code_files[0].split('/')[0]}/ ./{code_files[0].split('/')[0]}", code_files[0])]
        rng.shuffle(tail)
        for e in rng.sample(EXTRA, rng.randint(0, 1)):
            tail.insert(rng.randint(0, len(tail)), (e, None))
        steps += tail
    steps.append((cmd, None))
    return steps, deps_file, code_files[0]


@template("docker.layer_cache", "Docker: кэш слоёв при сборке", "devops_basics", ("backend", "devops"), 3, "input", time_limit=180)
def docker_layer_cache(rng: random.Random, ctx: GenCtx) -> Variant:
    steps, deps_file, code_file = _dockerfile(rng)
    changed = rng.choice([deps_file, code_file, "config/settings.yaml"])
    first = None
    for i, (_, f) in enumerate(steps, start=1):
        if f and (f == "*" or f == changed):
            first = i
            break
    if first is None:  # изменённый файл не копируется в образ — кэш не инвалидируется
        changed = deps_file
        first = next(i for i, (_, f) in enumerate(steps, start=1) if f in ("*", deps_file))
    code = "\n".join(f"{i:>2}  {s}" for i, (s, _) in enumerate(steps, start=1))
    return Variant(
        text=f"Образ уже собирался ранее, кэш слоёв сохранён. Разработчик изменил только файл `{changed}`. "
        "С какой по номеру инструкции Docker перестанет использовать кэш и начнёт выполнять шаги заново?",
        kind="input", input_type="number", answer=first, code=code, code_lang="dockerfile",
    )


@template("docker.facts", "Docker: основы контейнеризации", "devops_basics", ("backend", "qa"), 2, "multi", time_limit=150, method="pool")
def docker_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Каждая инструкция RUN, COPY, ADD создаёт новый слой образа",
        "Multi-stage сборка позволяет не тащить компиляторы и исходники в финальный образ",
        "Данные, записанные в файловую систему контейнера без volume, теряются при удалении контейнера",
        "Контейнеры используют ядро хост-системы",
        "Файл .dockerignore уменьшает контекст сборки",
    ]
    false_pool = [
        "Контейнер — это полноценная виртуальная машина со своим ядром",
        "EXPOSE в Dockerfile автоматически публикует порт на хосте",
        "Образ можно изменить внутри запущенного контейнера, и изменения сохранятся в исходном образе",
        "Тег latest всегда указывает на самую свежую стабильную версию по семантике версий",
        "CMD и ENTRYPOINT полностью взаимозаменяемы и не влияют друг на друга",
    ]
    return statements_multi(rng, ["Какие утверждения о Docker верны?"], true_pool, false_pool)
