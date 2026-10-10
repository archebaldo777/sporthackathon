"""Базы данных и SQL. Для SQL-заданий генерируются случайные таблицы, а эталонный ответ получается
исполнением запроса во встроенной SQLite — ключ невозможно «заучить», только вычислить."""
from __future__ import annotations

import random
import sqlite3

from app.testing.bank.base import GenCtx, Variant, scenario_single, statements_multi, template

DB_SPECS = ("backend", "ml", "data_analyst", "qa")
NAMES = ["Анна", "Борис", "Вера", "Глеб", "Дина", "Егор", "Жанна", "Злата", "Илья", "Кира", "Лев", "Мира", "Никита", "Ольга", "Пётр", "Роза"]
DEPTS = ["IT", "Sales", "HR", "Ops"]
CITIES = ["Москва", "Казань", "Пермь", "Томск", "Самара"]
STATUSES = ["paid", "new", "cancelled"]


def _run(tables: dict[str, tuple[list[str], list[list]]], query: str):
    con = sqlite3.connect(":memory:")
    for name, (cols, rows) in tables.items():
        con.execute(f"CREATE TABLE {name} ({', '.join(cols)})")
        if rows:
            con.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})", rows)
    res = con.execute(query).fetchall()
    con.close()
    return res


def _view(tables: dict) -> list[dict]:
    return [{"name": n, "columns": c, "rows": r} for n, (c, r) in tables.items()]


def _employees(rng: random.Random, n: int | None = None, with_null_bonus=False, ties=False, managers=False):
    n = n or rng.randint(7, 9)
    names = rng.sample(NAMES, n)
    salary_pool = [rng.randrange(80, 300, 10) for _ in range(4)] if ties else None
    rows = []
    for i, nm in enumerate(names, start=1):
        salary = rng.choice(salary_pool) if ties else rng.randrange(60, 320, 10)
        row = [i, nm, rng.choice(DEPTS[:3]), salary]
        if managers:
            row.append(None if i <= 2 else rng.randint(1, min(i - 1, 3)))
        if with_null_bonus:
            row.append(None if rng.random() < 0.35 else rng.choice([5, 10, 15, 20]))
        rows.append(row)
    cols = ["id", "name", "dept", "salary"] + (["manager_id"] if managers else []) + (["bonus"] if with_null_bonus else [])
    return cols, rows


def _shop(rng: random.Random, null_customer=False):
    nc = rng.randint(5, 6)
    customers = [[i, rng.choice(NAMES), rng.choice(CITIES[:3])] for i in range(1, nc + 1)]
    orders = []
    for i in range(1, rng.randint(7, 9) + 1):
        cid = rng.randint(1, nc - 1)  # хотя бы один клиент без заказов
        orders.append([100 + i, cid, rng.randrange(500, 5000, 100), rng.choice(STATUSES)])
    if null_customer:
        orders.append([100 + len(orders) + 1, None, rng.randrange(500, 5000, 100), "new"])
    return {"customers": (["id", "name", "city"], customers), "orders": (["id", "customer_id", "amount", "status"], orders)}


@template("sql.where_count", "SQL: фильтрация WHERE", "databases", DB_SPECS, 1, "input", time_limit=150)
def sql_where_count(rng: random.Random, ctx: GenCtx) -> Variant:
    t = {"employees": _employees(rng)}
    dept = rng.choice([r[2] for r in t["employees"][1]])
    thr = rng.randrange(100, 250, 10)
    op = rng.choice([">", ">=", "<"])
    q = f"SELECT COUNT(*) FROM employees\nWHERE dept = '{dept}' OR salary {op} {thr};" if rng.random() < 0.4 else \
        f"SELECT COUNT(*) FROM employees\nWHERE dept = '{dept}' AND salary {op} {thr};"
    ans = _run(t, q)[0][0]
    return Variant(text="Что вернёт запрос?", kind="input", input_type="number", answer=ans, code=q, code_lang="sql", tables=_view(t))


@template("sql.order_limit", "SQL: сортировка и LIMIT/OFFSET", "databases", DB_SPECS, 2, "input", time_limit=150)
def sql_order_limit(rng: random.Random, ctx: GenCtx) -> Variant:
    t = {"employees": _employees(rng, ties=True)}
    off = rng.randint(1, 3)
    direction = rng.choice(["DESC", "ASC"])
    q = f"SELECT name FROM employees\nORDER BY salary {direction}, name ASC\nLIMIT 1 OFFSET {off};"
    ans = _run(t, q)[0][0]
    return Variant(text="Какое имя вернёт запрос? (сортировка строк по алфавиту)", kind="input", input_type="text", answer=[ans], code=q,
                   code_lang="sql", tables=_view(t))


@template("sql.group_having", "SQL: GROUP BY и HAVING", "databases", DB_SPECS, 2, "input", time_limit=180)
def sql_group_having(rng: random.Random, ctx: GenCtx) -> Variant:
    t = {"employees": _employees(rng, n=rng.randint(8, 10))}
    form = rng.random()
    if form < 0.5:
        k = rng.randint(2, 3)
        q = f"SELECT dept, AVG(salary)\nFROM employees\nGROUP BY dept\nHAVING COUNT(*) >= {k};"
        ans = len(_run(t, q))
        text = "Сколько строк вернёт запрос?"
    else:
        dept = rng.choice(DEPTS[:3])
        q = f"SELECT dept, SUM(salary) AS total\nFROM employees\nWHERE salary > 100\nGROUP BY dept\nHAVING dept = '{dept}';"
        rows = _run(t, q)
        ans = rows[0][1] if rows else 0
        text = "Какое значение будет в колонке total? (если строк нет — введите 0)"
    return Variant(text=text, kind="input", input_type="number", answer=ans, code=q, code_lang="sql", tables=_view(t))


@template("sql.left_join", "SQL: LEFT JOIN", "databases", DB_SPECS, 2, "input", time_limit=180)
def sql_left_join(rng: random.Random, ctx: GenCtx) -> Variant:
    t = _shop(rng)
    if rng.random() < 0.5:
        q = "SELECT COUNT(*)\nFROM customers c\nLEFT JOIN orders o ON o.customer_id = c.id;"
    else:
        q = "SELECT COUNT(*)\nFROM customers c\nLEFT JOIN orders o ON o.customer_id = c.id\nWHERE o.id IS NULL;"
    ans = _run(t, q)[0][0]
    return Variant(text="Что вернёт запрос?", kind="input", input_type="number", answer=ans, code=q, code_lang="sql", tables=_view(t))


@template("sql.join_agg", "SQL: JOIN с агрегацией", "databases", DB_SPECS, 2, "input", time_limit=180)
def sql_join_agg(rng: random.Random, ctx: GenCtx) -> Variant:
    t = _shop(rng)
    city = rng.choice(CITIES[:3])
    status = rng.choice(["paid", "new"])
    q = f"SELECT COALESCE(SUM(o.amount), 0)\nFROM orders o\nJOIN customers c ON c.id = o.customer_id\nWHERE c.city = '{city}' AND o.status = '{status}';"
    ans = _run(t, q)[0][0]
    return Variant(text="Что вернёт запрос?", kind="input", input_type="number", answer=ans, code=q, code_lang="sql", tables=_view(t))


@template("sql.null_agg", "SQL: NULL в агрегатах и условиях", "databases", DB_SPECS, 3, "input", time_limit=180)
def sql_null_agg(rng: random.Random, ctx: GenCtx) -> Variant:
    t = {"employees": _employees(rng, with_null_bonus=True)}
    rows = t["employees"][1]
    if all(r[-1] is not None for r in rows):
        rows[0][-1] = None
    if all(r[-1] is None for r in rows):
        rows[1][-1] = 10
    form = rng.choice(["count", "avg", "neq", "sumdiv"])
    if form == "count":
        q = "SELECT COUNT(*) - COUNT(bonus) FROM employees;"
    elif form == "avg":
        q = "SELECT AVG(bonus) FROM employees;"
    elif form == "neq":
        v = rng.choice([5, 10, 15, 20])
        q = f"SELECT COUNT(*) FROM employees WHERE bonus <> {v};"
    else:
        q = "SELECT SUM(bonus) * 1.0 / COUNT(*) FROM employees;"
    ans = _run(t, q)[0][0]
    return Variant(text="Что вернёт запрос? (дробные значения округлите до сотых)", kind="input", input_type="number",
                   answer=round(float(ans), 2), tolerance=0.01, code=q, code_lang="sql", tables=_view(t))


@template("sql.window_rank", "SQL: оконные функции RANK/DENSE_RANK", "databases", DB_SPECS, 3, "input", time_limit=180)
def sql_window_rank(rng: random.Random, ctx: GenCtx) -> Variant:
    t = {"employees": _employees(rng, ties=True)}
    fn = rng.choice(["RANK", "DENSE_RANK"])
    q = f"SELECT name, salary,\n       {fn}() OVER (ORDER BY salary DESC) AS r\nFROM employees;"
    res = _run(t, q)
    # выбираем строку после блока одинаковых зарплат — там RANK и DENSE_RANK различаются
    pick = max(res, key=lambda r: (r[2], rng.random()))
    name = pick[0]
    return Variant(text=f"Какое значение r будет у сотрудника {name}?", kind="input", input_type="number", answer=pick[2], code=q,
                   code_lang="sql", tables=_view(t))


@template("sql.window_partition", "SQL: ROW_NUMBER по группам", "databases", DB_SPECS, 3, "input", time_limit=210)
def sql_window_partition(rng: random.Random, ctx: GenCtx) -> Variant:
    t = {"employees": _employees(rng, n=rng.randint(8, 10))}
    k = rng.randint(1, 2)
    thr = rng.randrange(120, 220, 10)
    q = (
        "SELECT COUNT(*) FROM (\n  SELECT name, salary,\n         ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC, id) AS rn\n"
        f"  FROM employees\n) t\nWHERE rn <= {k} AND salary > {thr};"
    )
    ans = _run(t, q)[0][0]
    return Variant(text="Что вернёт запрос?", kind="input", input_type="number", answer=ans, code=q, code_lang="sql", tables=_view(t))


@template("sql.not_in_null", "SQL: NOT IN и NULL в подзапросе", "databases", DB_SPECS, 4, "input", time_limit=180)
def sql_not_in_null(rng: random.Random, ctx: GenCtx) -> Variant:
    with_null = rng.random() < 0.6
    t = _shop(rng, null_customer=with_null)
    if rng.random() < 0.75:
        q = "SELECT COUNT(*) FROM customers\nWHERE id NOT IN (SELECT customer_id FROM orders);"
    else:
        q = "SELECT COUNT(*) FROM customers c\nWHERE NOT EXISTS (\n  SELECT 1 FROM orders o WHERE o.customer_id = c.id\n);"
    ans = _run(t, q)[0][0]
    return Variant(text="Что вернёт запрос?", kind="input", input_type="number", answer=ans, code=q, code_lang="sql", tables=_view(t))


@template("sql.self_join", "SQL: самосоединение (сотрудник и руководитель)", "databases", DB_SPECS, 3, "input", time_limit=180)
def sql_self_join(rng: random.Random, ctx: GenCtx) -> Variant:
    t = {"employees": _employees(rng, managers=True)}
    q = "SELECT COUNT(*)\nFROM employees e\nJOIN employees m ON e.manager_id = m.id\nWHERE e.salary > m.salary;"
    ans = _run(t, q)[0][0]
    return Variant(text="Что вернёт запрос?", kind="input", input_type="number", answer=ans, code=q, code_lang="sql", tables=_view(t))


@template("sql.running_total", "SQL: накопительный итог и рамка окна", "databases", DB_SPECS, 4, "input", time_limit=210)
def sql_running_total(rng: random.Random, ctx: GenCtx) -> Variant:
    days = sorted(rng.choice([1, 2, 3, 4]) for _ in range(6))
    rows = [[i + 1, d, rng.randrange(100, 900, 50)] for i, d in enumerate(days)]
    t = {"payments": (["id", "day", "amount"], rows)}
    if rng.random() < 0.5:
        q = "SELECT id, SUM(amount) OVER (ORDER BY day) AS s\nFROM payments;"  # RANGE: включает «равных» по day
    else:
        q = "SELECT id, SUM(amount) OVER (ORDER BY id ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS s\nFROM payments;"
    res = dict(_run(t, q))
    pid = rng.choice([r[0] for r in rows[1:4]])
    return Variant(text=f"Какое значение s будет в строке с id = {pid}?", kind="input", input_type="number", answer=res[pid], code=q,
                   code_lang="sql", tables=_view(t))


@template("sql.case_when", "SQL: условная агрегация CASE", "databases", DB_SPECS, 2, "input", time_limit=150)
def sql_case_when(rng: random.Random, ctx: GenCtx) -> Variant:
    t = _shop(rng)
    st = rng.choice(STATUSES)
    q = f"SELECT SUM(CASE WHEN status = '{st}' THEN amount ELSE 0 END)\n     - SUM(CASE WHEN status <> '{st}' THEN 1 ELSE 0 END) * 100\nFROM orders;"
    ans = _run(t, q)[0][0]
    return Variant(text="Что вернёт запрос?", kind="input", input_type="number", answer=ans, code=q, code_lang="sql", tables=_view(t))


@template("sql.distinct", "SQL: DISTINCT и NULL", "databases", DB_SPECS, 2, "input", time_limit=120)
def sql_distinct(rng: random.Random, ctx: GenCtx) -> Variant:
    rows = [[i, rng.choice(NAMES), rng.choice(CITIES + [None])] for i in range(1, rng.randint(7, 9))]
    t = {"customers": (["id", "name", "city"], rows)}
    q = rng.choice(["SELECT COUNT(DISTINCT city) FROM customers;", "SELECT COUNT(city) FROM customers;"])
    ans = _run(t, q)[0][0]
    return Variant(text="Что вернёт запрос?", kind="input", input_type="number", answer=ans, code=q, code_lang="sql", tables=_view(t))


# ---------------------------------------------------------------- концепции
@template("db.isolation", "Уровни изоляции транзакций", "databases", ("backend", "data_analyst", "qa"), 3, "multi", time_limit=180,
          method="pool")
def db_isolation(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "READ COMMITTED не допускает «грязного» чтения",
        "Фантомное чтение — появление новых строк, удовлетворяющих условию, при повторном запросе в той же транзакции",
        "SERIALIZABLE гарантирует результат, эквивалентный некоторому последовательному выполнению транзакций",
        "В PostgreSQL уровень READ UNCOMMITTED фактически работает как READ COMMITTED",
        "Потерянное обновление можно предотвратить блокировкой строки через SELECT ... FOR UPDATE",
        "На уровне SERIALIZABLE приложение должно быть готово повторять транзакции после ошибок сериализации",
    ]
    false_pool = [
        "SERIALIZABLE никогда не приводит к откату транзакций",
        "REPEATABLE READ допускает «грязное» чтение",
        "Неповторяющееся чтение — это чтение данных незафиксированной транзакции",
        "Чем выше уровень изоляции, тем выше пропускная способность системы",
        "Уровень изоляции влияет только на операции записи",
        "READ COMMITTED гарантирует, что два одинаковых SELECT в одной транзакции вернут одинаковые данные",
    ]
    return statements_multi(rng, ["Какие утверждения об изоляции транзакций верны?"], true_pool, false_pool)


@template("db.indexes", "Индексы и планы запросов", "databases", DB_SPECS, 3, "multi", time_limit=180, method="pool")
def db_indexes(rng: random.Random, ctx: GenCtx) -> Variant:
    col_a, col_b = rng.choice([("user_id", "created_at"), ("city", "age"), ("status", "updated_at"), ("tenant_id", "email")])
    true_pool = [
        f"Составной индекс ({col_a}, {col_b}) может использоваться для условия WHERE {col_a} = ?",
        f"Индекс ({col_a}, {col_b}) обычно не помогает запросу только с условием WHERE {col_b} = ?",
        "Условие LIKE 'abc%' может использовать B-tree индекс (при подходящей сортировке/опклассе)",
        "Условие WHERE lower(email) = ? не использует обычный индекс по email без функционального индекса",
        "Индексы ускоряют чтение, но замедляют вставку и обновление",
        "EXPLAIN ANALYZE выполняет запрос и показывает фактический план и время",
    ]
    false_pool = [
        "Условие LIKE '%abc' эффективно использует обычный B-tree индекс",
        "Индекс всегда ускоряет любой запрос к таблице",
        "Чем больше индексов на таблице, тем быстрее вставка",
        f"Индекс ({col_a}, {col_b}) полностью эквивалентен двум отдельным индексам по {col_a} и по {col_b}",
        "B-tree индекс не может использоваться для ORDER BY",
        "Первичный ключ в PostgreSQL не создаёт индекс",
    ]
    return statements_multi(rng, ["Какие утверждения об индексах верны?"], true_pool, false_pool)


ACID_QA = [
    (["Что означает буква «I» в ACID?", "Какое свойство транзакций обозначено буквой «I» в ACID?"], "Изолированность"),
    (["Какое свойство ACID гарантирует, что зафиксированные данные не потеряются при сбое?", "Что означает буква «D» в ACID?"], "Долговечность"),
    (["Какое свойство ACID гарантирует «всё или ничего» при выполнении транзакции?", "Что означает буква «A» в ACID?"], "Атомарность"),
    (["Какое свойство ACID гарантирует соблюдение ограничений целостности после транзакции?", "Что означает буква «C» в ACID?"], "Согласованность"),
]


@template("db.acid", "Свойства транзакций ACID", "databases", DB_SPECS, 1, "single", time_limit=90, method="pool")
def db_acid(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, ACID_QA, ["Изолированность", "Долговечность", "Атомарность", "Согласованность", "Индексируемость", "Идемпотентность"])


STORE_SCENARIOS = [
    (["Кэш пользовательских сессий с автоматическим истечением по TTL", "Хранение счётчиков rate limiting с истечением ключей"], "Redis"),
    (["Аналитика по миллиардам событий с агрегациями по нескольким колонкам", "Отчёты по кликстриму объёмом в терабайты"], "ClickHouse"),
    (["Полнотекстовый поиск по товарам с учётом морфологии и опечаток", "Поиск по логам и документам с релевантностью"], "Elasticsearch / OpenSearch"),
    (["Платёжные операции, где важны транзакции и целостность данных", "Учёт заказов с внешними ключами и строгими ограничениями"], "PostgreSQL"),
    (["Журнал событий, который читают несколько независимых сервисов", "Надёжная асинхронная передача событий между микросервисами с хранением истории"], "Kafka"),
    (["Граф связей пользователей для рекомендаций «друзья друзей»", "Поиск путей в сети связей между объектами"], "Графовая СУБД (Neo4j)"),
]


@template("db.store_choice", "Выбор хранилища под задачу", "databases", ("backend", "data_analyst"), 3, "single", time_limit=120, method="pool")
def db_store_choice(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, STORE_SCENARIOS, [a for _, a in STORE_SCENARIOS] + ["SQLite", "Memcached"],
                           prefix="Какое хранилище подходит лучше всего? ")


@template("db.lost_update", "Конкурентные транзакции: потерянное обновление", "databases", ("backend", "qa"), 4, "input", time_limit=210)
def db_lost_update(rng: random.Random, ctx: GenCtx) -> Variant:
    B, x, y = rng.randrange(1000, 5000, 100), rng.randrange(100, 900, 50), rng.randrange(100, 900, 50)
    atomic = rng.random() < 0.4
    t2_write = f"UPDATE accounts SET balance = balance - {y} WHERE id = 1;" if atomic else \
        f"-- приложение вычисляет {B} - {y}\nUPDATE accounts SET balance = {B - y} WHERE id = 1;"
    code = (
        "-- READ COMMITTED, начальный баланс = " + str(B) + "\n"
        "T1: BEGIN; SELECT balance FROM accounts WHERE id = 1;  -- " + str(B) + "\n"
        "T2: BEGIN; SELECT balance FROM accounts WHERE id = 1;  -- " + str(B) + "\n"
        f"T1: UPDATE accounts SET balance = {B + x} WHERE id = 1;  -- приложение вычислило {B} + {x}\n"
        "T1: COMMIT;\n"
        f"T2: {t2_write}\n"
        "T2: COMMIT;"
    )
    ans = (B + x - y) if atomic else (B - y)
    return Variant(text="Каким будет итоговый баланс после обеих транзакций?", kind="input", input_type="number", answer=ans, code=code,
                   code_lang="sql")
