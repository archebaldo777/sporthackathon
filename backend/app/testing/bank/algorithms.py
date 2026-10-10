"""Алгоритмы и структуры данных. Ответы вычисляются симуляцией алгоритма на сгенерированных данных."""
from __future__ import annotations

import heapq
import random
import string
from collections import deque

from app.testing.bank.base import (
    FUNC_NAMES,
    GenCtx,
    Variant,
    numeric_distractors,
    pick_distractors,
    scenario_single,
    single,
    statements_multi,
    template,
)

ALG_SPECS = ("backend", "frontend", "mobile", "ml")
COMPLEXITIES = ["O(1)", "O(log n)", "O(√n)", "O(n)", "O(n log n)", "O(n²)", "O(n³)", "O(2ⁿ)"]


def _body(rng):
    return rng.choice(["total += 1", "acc += x", "count += 1", "s += k", "ops += 1"])


@template("alg.bigo_basic", "Асимптотика простых циклов", "algorithms", ALG_SPECS, 2, "single", time_limit=120)
def bigo_basic(rng: random.Random, ctx: GenCtx) -> Variant:
    n = rng.choice(["n", "m", "size"])
    k = rng.randint(3, 50)
    shapes = [
        (f"for i in range({n}):\n    for j in range({n}):\n        {_body(rng)}", "O(n²)"),
        (f"i = 1\nwhile i < {n}:\n    i *= {rng.choice([2, 3])}\n    {_body(rng)}", "O(log n)"),
        (f"for i in range({n}):\n    for j in range(i):\n        {_body(rng)}", "O(n²)"),
        (f"for i in range({n}):\n    {_body(rng)}\nfor j in range({n}):\n    {_body(rng)}", "O(n)"),
        (f"for i in range({n}):\n    for j in range({k}):\n        {_body(rng)}", "O(n)"),
        (f"i = {n}\nwhile i > 0:\n    i //= 2\n    {_body(rng)}", "O(log n)"),
    ]
    code, ans = rng.choice(shapes)
    d = pick_distractors(rng, ans, COMPLEXITIES[:7], 3)
    return single(f"Какова временная сложность фрагмента в зависимости от `{n}`?", ans, d, code=code, code_lang="python")


@template("alg.bigo_advanced", "Асимптотика вложенных конструкций", "algorithms", ALG_SPECS, 3, "single", time_limit=150)
def bigo_advanced(rng: random.Random, ctx: GenCtx) -> Variant:
    n = rng.choice(["n", "size"])
    shapes = [
        (f"for i in range({n}):\n    j = 1\n    while j < {n}:\n        j *= 2", "O(n log n)"),
        (f"for i in range({n}):\n    for j in range({n}):\n        for k in range({n}):\n            pass", "O(n³)"),
        (f"i = 1\nwhile i * i <= {n}:\n    i += 1", "O(√n)"),
        (f"def f({n}):\n    if {n} <= 1:\n        return 1\n    return f({n} - 1) + f({n} - 1)", "O(2ⁿ)"),
        (f"for i in range({n}):\n    k = {n}\n    while k > 0:\n        k //= 2", "O(n log n)"),
        (f"for i in range({n}):\n    for j in range(i, i + 100):\n        pass", "O(n)"),
    ]
    code, ans = rng.choice(shapes)
    d = pick_distractors(rng, ans, COMPLEXITIES, 3)
    return single(f"Оцените временную сложность в зависимости от `{n}`:", ans, d, code=code, code_lang="python")


@template("alg.bigo_tricky", "Амортизированная и неочевидная сложность", "algorithms", ALG_SPECS, 4, "single", time_limit=180)
def bigo_tricky(rng: random.Random, ctx: GenCtx) -> Variant:
    n = rng.choice(["n", "size"])
    shapes = [
        (f"i = {n}\nwhile i > 0:\n    for j in range(i):\n        pass\n    i //= 2", "O(n)"),
        (f"for i in range(1, {n} + 1):\n    for j in range(0, {n}, i):\n        pass", "O(n log n)"),
        (f"left, right = 0, {n} - 1\nwhile left < right:\n    if a[left] + a[right] < target:\n        left += 1\n    else:\n        right -= 1", "O(n)"),
        (f"stack = []\nfor x in a:  # len(a) == {n}\n    while stack and stack[-1] < x:\n        stack.pop()\n    stack.append(x)", "O(n)"),
        (f"arr = []\nfor i in range({n}):\n    arr.append(i)  # динамический массив с удвоением ёмкости", "O(n)"),
    ]
    code, ans = rng.choice(shapes)
    d = pick_distractors(rng, ans, COMPLEXITIES, 3)
    return single(f"Какова итоговая (амортизированная) сложность всего фрагмента по `{n}`?", ans, d, code=code, code_lang="python")


@template("alg.binary_search_steps", "Трассировка бинарного поиска", "algorithms", ALG_SPECS, 3, "input", time_limit=180)
def binary_search_steps(rng: random.Random, ctx: GenCtx) -> Variant:
    size = rng.randint(9, 15)
    a = sorted(rng.sample(range(1, 99), size))
    target = rng.choice(a) if rng.random() < 0.6 else rng.choice([x for x in range(1, 99) if x not in a])
    lo, hi, steps = 0, len(a) - 1, 0
    while lo <= hi:
        mid = (lo + hi) // 2
        steps += 1
        if a[mid] == target:
            break
        if a[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    code = (
        f"a = {a}\ntarget = {target}\nlo, hi, steps = 0, len(a) - 1, 0\n"
        "while lo <= hi:\n    mid = (lo + hi) // 2\n    steps += 1\n    if a[mid] == target:\n        break\n"
        "    elif a[mid] < target:\n        lo = mid + 1\n    else:\n        hi = mid - 1\nprint(steps)"
    )
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=steps, code=code, code_lang="python")


@template("alg.stack_queue", "Операции со стеком и очередью", "algorithms", ALG_SPECS, 1, "input", time_limit=120)
def stack_queue(rng: random.Random, ctx: GenCtx) -> Variant:
    use_stack = rng.random() < 0.5
    ds: list[int] = []
    ops, popped = [], []
    for _ in range(rng.randint(7, 10)):
        if ds and rng.random() < 0.4:
            v = ds.pop() if use_stack else ds.pop(0)
            popped.append(v)
            ops.append("pop()" if use_stack else "dequeue()")
        else:
            x = rng.randint(1, 20)
            ds.append(x)
            ops.append(f"push({x})" if use_stack else f"enqueue({x})")
    if not popped:
        v = ds.pop() if use_stack else ds.pop(0)
        popped.append(v)
        ops.append("pop()" if use_stack else "dequeue()")
    name = "стек (LIFO)" if use_stack else "очередь (FIFO)"
    return Variant(
        text=f"Над пустой структурой «{name}» выполнили операции:\n\n`{'; '.join(ops)}`\n\nЧему равна сумма всех извлечённых значений?",
        kind="input",
        input_type="number",
        answer=sum(popped),
    )


def _rand_graph(rng: random.Random, n: int) -> dict[str, list[str]]:
    nodes = list(string.ascii_uppercase[:n])
    adj = {v: set() for v in nodes}
    rest = nodes[1:]
    rng.shuffle(rest)
    order = [nodes[0]] + rest
    for i in range(1, n):  # остовное дерево для связности
        u, v = order[i], order[rng.randrange(0, i)]
        adj[u].add(v)
        adj[v].add(u)
    for _ in range(rng.randint(1, 3)):
        u, v = rng.sample(nodes, 2)
        adj[u].add(v)
        adj[v].add(u)
    return {v: sorted(adj[v]) for v in nodes}


@template("alg.graph_traversal", "Порядок обхода графа (BFS/DFS)", "algorithms", ALG_SPECS, 3, "input", time_limit=210)
def graph_traversal(rng: random.Random, ctx: GenCtx) -> Variant:
    g = _rand_graph(rng, rng.randint(6, 7))
    bfs = rng.random() < 0.5
    order: list[str] = []
    if bfs:
        seen, q = {"A"}, deque(["A"])
        while q:
            v = q.popleft()
            order.append(v)
            for w in g[v]:
                if w not in seen:
                    seen.add(w)
                    q.append(w)
    else:
        seen = set()

        def dfs(v):
            seen.add(v)
            order.append(v)
            for w in g[v]:
                if w not in seen:
                    dfs(w)

        dfs("A")
    lines = "\n".join(f"{v}: {', '.join(ns)}" for v, ns in g.items())
    algo = "в ширину (BFS, очередь)" if bfs else "в глубину (рекурсивный DFS)"
    return Variant(
        text=f"Граф задан списками смежности (соседи перебираются по алфавиту). Выполните обход {algo} из вершины A. "
        "Введите вершины в порядке посещения через пробел.",
        kind="input",
        input_type="text",
        answer=[" ".join(order), "".join(order)],
        code=lines,
        code_lang="text",
    )


@template("alg.hash_probing", "Хеш-таблица с линейным пробированием", "algorithms", ALG_SPECS, 3, "input", time_limit=180)
def hash_probing(rng: random.Random, ctx: GenCtx) -> Variant:
    m = rng.choice([7, 11, 13])
    keys = []
    while len(keys) < rng.randint(5, 6):
        k = rng.randint(10, 99)
        if k not in keys:
            keys.append(k)
    # гарантируем хотя бы одну коллизию
    base = keys[0] % m
    extra = base + m * rng.randint(2, 6)
    if extra not in keys and extra < 120:
        keys.insert(rng.randint(1, len(keys)), extra)
    table: list[int | None] = [None] * m
    pos = {}
    for k in keys:
        i = k % m
        while table[i] is not None:
            i = (i + 1) % m
        table[i] = k
        pos[k] = i
    asked = keys[-1] if rng.random() < 0.5 else rng.choice(keys[1:])
    return Variant(
        text=f"В пустую хеш-таблицу размера {m} с функцией h(k) = k mod {m} и линейным пробированием (шаг +1) "
        f"по очереди вставили ключи: {', '.join(map(str, keys))}. В ячейку с каким индексом попал ключ {asked}?",
        kind="input",
        input_type="number",
        answer=pos[asked],
    )


@template("alg.bubble_pass", "Проход сортировки пузырьком", "algorithms", ALG_SPECS, 2, "single", time_limit=150)
def bubble_pass(rng: random.Random, ctx: GenCtx) -> Variant:
    a = rng.sample(range(1, 40), 6)

    def passes(arr, k):
        arr = arr[:]
        for p in range(k):
            for i in range(len(arr) - 1 - p):
                if arr[i] > arr[i + 1]:
                    arr[i], arr[i + 1] = arr[i + 1], arr[i]
        return arr

    one = passes(a, 1)
    if one == sorted(a):
        a = a[::-1]
        one = passes(a, 1)
    cands = [passes(a, 2), sorted(a), a[1:] + a[:1], list(reversed(one))]
    # «шаг выбором»: минимум переставлен в начало
    sel = a[:]
    j = sel.index(min(sel))
    sel[0], sel[j] = sel[j], sel[0]
    cands.append(sel)
    d = pick_distractors(rng, str(one), [str(c) for c in cands], 3)
    return single(
        f"Массив {a} сортируют по возрастанию пузырьком. Каким он станет после **первого полного прохода**?",
        str(one),
        d,
    )


@template("alg.grid_paths", "Динамическое программирование: пути в сетке", "algorithms", ALG_SPECS, 3, "input", time_limit=240)
def grid_paths(rng: random.Random, ctx: GenCtx) -> Variant:
    r, c = rng.randint(3, 4), rng.randint(4, 5)
    blocked = set()
    while len(blocked) < rng.randint(1, 2):
        cell = (rng.randrange(r), rng.randrange(c))
        if cell not in ((0, 0), (r - 1, c - 1)):
            blocked.add(cell)
    dp = [[0] * c for _ in range(r)]
    for i in range(r):
        for j in range(c):
            if (i, j) in blocked:
                continue
            if i == 0 and j == 0:
                dp[i][j] = 1
                continue
            dp[i][j] = (dp[i - 1][j] if i else 0) + (dp[i][j - 1] if j else 0)
    grid = "\n".join(" ".join("#" if (i, j) in blocked else "." for j in range(c)) for i in range(r))
    return Variant(
        text="Робот стоит в левой верхней клетке и может ходить только вправо или вниз. Клетки `#` заблокированы. "
        "Сколько существует различных путей до правой нижней клетки?",
        kind="input",
        input_type="number",
        answer=dp[r - 1][c - 1],
        code=grid,
        code_lang="text",
    )


@template("alg.min_heap", "Бинарная куча: представление массивом", "algorithms", ALG_SPECS, 3, "single", time_limit=210)
def min_heap(rng: random.Random, ctx: GenCtx) -> Variant:
    xs = rng.sample(range(1, 50), 6)
    h: list[int] = []
    for x in xs:
        heapq.heappush(h, x)  # стандартный sift-up, совпадает с учебным алгоритмом
    distractors = [str(sorted(xs)), str(xs)]
    alt = h[:]
    alt[1], alt[2] = alt[2], alt[1]
    distractors.append(str(alt))
    h2 = xs[:]
    heapq.heapify(h2)
    distractors.append(str(h2))
    d = pick_distractors(rng, str(h), distractors, 3)
    return single(
        f"В пустую min-кучу последовательно вставили (через просеивание вверх) элементы {xs}. "
        "Каким будет массив, хранящий кучу?",
        str(h),
        d,
    )


@template("alg.lru_misses", "Кэш LRU: число промахов", "algorithms", ALG_SPECS + ("devops",), 3, "input", time_limit=180)
def lru_misses(rng: random.Random, ctx: GenCtx) -> Variant:
    cap = rng.choice([2, 3])
    seq = [rng.choice("ABCDE"[: cap + 2]) for _ in range(rng.randint(9, 11))]
    cache: list[str] = []
    misses = 0
    for k in seq:
        if k in cache:
            cache.remove(k)
        else:
            misses += 1
            if len(cache) == cap:
                cache.pop(0)
        cache.append(k)
    return Variant(
        text=f"Кэш с политикой вытеснения LRU вмещает {cap} элемента(ов) и изначально пуст. "
        f"Последовательность обращений: {' '.join(seq)}. Сколько будет промахов (cache miss)?",
        kind="input",
        input_type="number",
        answer=misses,
    )


@template("alg.bit_ops", "Побитовые операции", "algorithms", ALG_SPECS + ("infosec",), 2, "input", time_limit=120)
def bit_ops(rng: random.Random, ctx: GenCtx) -> Variant:
    x, y = rng.randint(5, 60), rng.randint(3, 40)
    op = rng.choice(["&", "|", "^", "<<", ">>"])
    if op in ("<<", ">>"):
        y = rng.randint(1, 3)
    val = {"&": x & y, "|": x | y, "^": x ^ y, "<<": x << y, ">>": x >> y}[op]
    return Variant(text=f"Чему равно выражение `{x} {op} {y}` (целые числа, десятичная запись)?", kind="input", input_type="number", answer=val)


@template("alg.recursion_calls", "Число вызовов наивной рекурсии", "algorithms", ALG_SPECS, 3, "input", time_limit=180)
def recursion_calls(rng: random.Random, ctx: GenCtx) -> Variant:
    fn = rng.choice(FUNC_NAMES)
    d1, d2 = rng.choice([(1, 2), (1, 3), (2, 3)])
    base = rng.choice([2, 3])
    n = rng.randint(5, 9)
    memo: dict[int, int] = {}

    def calls(k):
        if k < base:
            return 1
        if k not in memo:
            memo[k] = 1 + calls(k - d1) + calls(k - d2)
        return memo[k]

    code = f"def {fn}(n):\n    if n < {base}:\n        return n\n    return {fn}(n - {d1}) + {fn}(n - {d2})\n\n{fn}({n})"
    return Variant(text=f"Сколько всего раз будет вызвана функция `{fn}` (включая первый вызов)?", kind="input", input_type="number",
                   answer=calls(n), code=code, code_lang="python")


@template("alg.knapsack", "Рюкзак 0/1", "algorithms", ALG_SPECS, 4, "input", time_limit=270)
def knapsack(rng: random.Random, ctx: GenCtx) -> Variant:
    items = [(rng.randint(2, 7), rng.randint(3, 15)) for _ in range(5)]
    cap = rng.randint(9, 14)
    dp = [0] * (cap + 1)
    for w, v in items:
        for c in range(cap, w - 1, -1):
            dp[c] = max(dp[c], dp[c - w] + v)
    greedy = 0
    rest = cap
    for w, v in sorted(items, key=lambda t: -t[1] / t[0]):
        if w <= rest:
            rest -= w
            greedy += v
    lines = "\n".join(f"предмет {i + 1}: вес {w}, ценность {v}" for i, (w, v) in enumerate(items))
    return Variant(
        text=f"Вместимость рюкзака — {cap}. Каждый предмет можно взять не более одного раза. "
        "Какую максимальную суммарную ценность можно унести?",
        kind="input",
        input_type="number",
        answer=dp[cap],
        code=lines,
        code_lang="text",
    )


@template("alg.dijkstra", "Кратчайший путь во взвешенном графе", "algorithms", ALG_SPECS, 3, "input", time_limit=240)
def dijkstra(rng: random.Random, ctx: GenCtx) -> Variant:
    nodes = list("ABCDEF")[: rng.randint(5, 6)]
    edges = {}
    for i in range(1, len(nodes)):
        edges[(nodes[rng.randrange(i)], nodes[i])] = rng.randint(1, 9)
    for _ in range(rng.randint(3, 4)):
        u, v = sorted(rng.sample(nodes, 2))
        edges.setdefault((u, v), rng.randint(1, 9))
    adj = {v: [] for v in nodes}
    for (u, v), w in edges.items():
        adj[u].append((v, w))
        adj[v].append((u, w))
    dist = {v: float("inf") for v in nodes}
    dist["A"] = 0
    pq = [(0, "A")]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            if d + w < dist[v]:
                dist[v] = d + w
                heapq.heappush(pq, (dist[v], v))
    target = nodes[-1]
    lines = "\n".join(f"{u} — {v}: {w}" for (u, v), w in edges.items())
    return Variant(
        text=f"Неориентированный граф задан рёбрами с весами. Найдите длину кратчайшего пути из A в {target}.",
        kind="input",
        input_type="number",
        answer=int(dist[target]),
        code=lines,
        code_lang="text",
    )


DS_SCENARIOS = [
    (["Нужно многократно проверять, встречался ли уже элемент, за O(1) в среднем.", "Требуется быстро отвечать на вопрос «есть ли элемент в коллекции» при частых вставках."], "Хеш-множество"),
    (["Задачи должны обрабатываться строго в порядке поступления.", "Реализуйте буфер, где первым извлекается самый ранний элемент."], "Очередь"),
    (["Нужно реализовать операцию «отменить последнее действие» (undo).", "Проверка правильности расстановки скобок в выражении."], "Стек"),
    (["Постоянно извлекается элемент с наименьшим приоритетом, вставки идут непрерывно.", "Нужно поддерживать k самых крупных значений из потока данных."], "Двоичная куча"),
    (["Автодополнение: быстро найти все слова с заданным префиксом.", "Поиск слов словаря по префиксу при наборе текста."], "Префиксное дерево (trie)"),
    (["Хранить упорядоченные ключи и быстро выполнять запросы по диапазону ключей.", "Нужны вставка, удаление и поиск следующего по величине ключа за O(log n)."], "Сбалансированное дерево поиска"),
    (["При добавлении рёбер в граф нужно быстро отвечать, связаны ли две вершины.", "Объединение множеств и проверка принадлежности одному множеству почти за O(1)."], "Система непересекающихся множеств (DSU)"),
    (["Кэш с вытеснением давно неиспользуемых элементов за O(1) на операцию.", "Реализация LRU-кэша с операциями get/put за O(1)."], "Хеш-таблица + двусвязный список"),
]


@template("alg.ds_choice", "Выбор структуры данных", "algorithms", ALG_SPECS, 2, "single", time_limit=120, method="pool")
def ds_choice(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, DS_SCENARIOS, [a for _, a in DS_SCENARIOS] + ["Связный список", "Массив фиксированного размера"],
                           prefix="Какая структура данных подходит лучше всего? ")


@template("alg.complexity_facts", "Сложность операций (утверждения)", "algorithms", ALG_SPECS, 3, "multi", time_limit=180, method="pool")
def complexity_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Поиск в хеш-таблице в среднем выполняется за O(1), в худшем случае — за O(n)",
        "Сортировка слиянием работает за O(n log n) в худшем случае",
        "Быстрая сортировка в худшем случае работает за O(n²)",
        "Вставка в начало динамического массива требует O(n)",
        "Извлечение минимума из бинарной кучи выполняется за O(log n)",
        "Любая сортировка сравнениями в худшем случае требует Ω(n log n) сравнений",
        "Добавление в конец динамического массива амортизированно выполняется за O(1)",
        "Обход в ширину графа со списками смежности работает за O(V + E)",
        "Доступ к элементу связного списка по индексу требует O(n)",
    ]
    false_pool = [
        "Быстрая сортировка всегда работает за O(n log n)",
        "Бинарный поиск в отсортированном массиве работает за O(n)",
        "Хеш-таблица хранит элементы в порядке вставки по определению",
        "Извлечение минимума из бинарной кучи выполняется за O(1)",
        "Алгоритм Дейкстры корректен на графах с отрицательными весами рёбер",
        "Обход в глубину гарантирует нахождение кратчайшего пути в невзвешенном графе",
        "Бинарный поиск корректно работает на неотсортированном массиве",
        "Сортировка подсчётом применима к любым данным и всегда работает за O(n)",
    ]
    return statements_multi(rng, ["Какие утверждения о сложности алгоритмов верны?", "Отметьте верные утверждения:"], true_pool, false_pool)
