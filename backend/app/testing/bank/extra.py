"""Дополнительные семейства, закрывающие пробелы покрытия «компетенция × уровень» (особенно Senior и Стажёр)."""
from __future__ import annotations

import ipaddress
import random
from datetime import datetime, timedelta

from app.testing.bank.base import GenCtx, Variant, pick_distractors, scenario_single, single, statements_multi, template
from app.testing.bank.code_trace import LANG_SPECS, _simulate_event_loop


# ================================================================== языки: Senior-ловушки
@template("csharp.linq_deferred", "C#: отложенное выполнение LINQ", "lang", LANG_SPECS, 4, "input", langs=("csharp",), time_limit=180)
def csharp_linq(rng: random.Random, ctx: GenCtx) -> Variant:
    xs = rng.sample(range(1, 20), 5)
    t = rng.randint(5, 12)
    add, rem = rng.randint(13, 30), rng.choice(xs)
    materialize = rng.random() < 0.4
    q = f"list.Where(x => x > {t}){'.ToList()' if materialize else ''}"
    code = (f"var list = new List<int> {{ {', '.join(map(str, xs))} }};\nvar query = {q};\nlist.Add({add});\nlist.Remove({rem});\n"
            "Console.WriteLine(query.Count());")
    cur = xs + [add]
    cur.remove(rem)
    ans = sum(1 for x in xs if x > t) if materialize else sum(1 for x in cur if x > t)
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang="csharp")


@template("php.foreach_ref", "PHP: foreach по ссылке", "lang", LANG_SPECS, 4, "input", langs=("php",), time_limit=180)
def php_foreach_ref(rng: random.Random, ctx: GenCtx) -> Variant:
    a = rng.sample(range(1, 20), 3)
    unset = rng.random() < 0.35
    code = f"$a = [{', '.join(map(str, a))}];\nforeach ($a as &$v) {{}}\n{'unset($v);' + chr(10) if unset else ''}foreach ($a as $v) {{}}\necho array_sum($a);"
    ans = sum(a) if unset else a[0] + a[1] + a[1]
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang="php")


@template("swift.capture_list", "Swift: списки захвата в замыканиях", "lang", LANG_SPECS, 4, "input", langs=("swift",), time_limit=180,
          b_offset=-0.3)
def swift_capture(rng: random.Random, ctx: GenCtx) -> Variant:
    A, B, K = rng.randint(1, 9), rng.randint(10, 30), rng.randint(2, 5)
    order = rng.sample(["f", "g"], 2)
    code = (f"var x = {A}\nlet f = {{ [x] in print(x * {K}) }}\nlet g = {{ print(x * {K}) }}\nx = {B}\n" + "\n".join(f"{n}()" for n in order))
    vals = {"f": A * K, "g": B * K}
    return Variant(text="Что выведет программа? Введите числа через пробел.", kind="input", input_type="text",
                   answer=[" ".join(str(vals[n]) for n in order)], code=code, code_lang="swift")


@template("dart.event_loop", "Dart: микрозадачи и очередь событий", "lang", LANG_SPECS, 4, "input", langs=("dart",), time_limit=240)
def dart_event_loop(rng: random.Random, ctx: GenCtx) -> Variant:
    labels = iter(rng.sample(range(1, 10), 9))
    parts, lines = [], []
    kinds = ["sync", "event", "micro", "event_nested", "micro_then", "async"]
    chosen = ["sync", "event", "micro"] + rng.sample(kinds, 3)
    rng.shuffle(chosen)
    for k in chosen:
        a = next(labels)
        if k == "sync":
            parts.append(("sync", a))
            lines.append(f"  print({a});")
        elif k == "event":
            parts.append(("timeout", ("log", a)))
            lines.append(f"  Future(() => print({a}));")
        elif k == "micro":
            parts.append(("micro", ("log", a)))
            lines.append(f"  scheduleMicrotask(() => print({a}));")
        elif k == "micro_then":
            parts.append(("micro", ("log", a)))
            lines.append(f"  Future.value(0).then((_) => print({a}));")
        elif k == "event_nested":
            b = next(labels)
            parts.append(("timeout", ("log_then_micro", a, b)))
            lines.append(f"  Future(() {{\n    print({a});\n    scheduleMicrotask(() => print({b}));\n  }});")
        else:
            b = next(labels)
            parts.append(("async", (a, b)))
            lines.append(f"  () async {{\n    print({a});\n    await null;\n    print({b});\n  }}();")
    out = [str(x) for x in _simulate_event_loop(parts)]
    code = "import 'dart:async';\n\nvoid main() {\n" + "\n".join(lines) + "\n}"
    return Variant(text="В каком порядке будут выведены числа? Введите через пробел.", kind="input", input_type="text",
                   answer=[" ".join(out), "".join(out)], code=code, code_lang="dart")


# ================================================================== архитектура: базовый уровень
@template("arch.scaling_basics", "Масштабирование и базовые архитектурные решения", "architecture", ("backend", "mobile"), 2, "multi",
          time_limit=150, method="pool")
def arch_scaling_basics(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Горизонтальное масштабирование — добавление новых экземпляров сервиса",
        "Stateless-сервисы проще масштабировать горизонтально",
        "Балансировщик нагрузки распределяет запросы между экземплярами сервиса",
        "Кэширование снижает нагрузку на базу данных при частых одинаковых чтениях",
        "Асинхронная очередь позволяет сгладить пики нагрузки",
    ]
    false_pool = [
        "Вертикальное масштабирование не имеет физических пределов",
        "Микросервисы всегда проще в эксплуатации, чем монолит",
        "Хранение сессий в памяти конкретного экземпляра упрощает горизонтальное масштабирование",
        "Кэш всегда содержит актуальные данные без стратегии инвалидации",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


# ================================================================== frontend
DOM_BASICS = [
    (["Как найти первый элемент на странице по CSS-селектору?"], "document.querySelector()"),
    (["Как получить все элементы, подходящие под CSS-селектор?"], "document.querySelectorAll()"),
    (["Как подписаться на событие клика по элементу?"], "element.addEventListener()"),
    (["Как отменить переход по ссылке при клике?"], "event.preventDefault()"),
    (["Как безопасно вставить в элемент пользовательский текст (без интерпретации HTML)?"], "element.textContent = ..."),
    (["Какое событие сигнализирует, что HTML разобран и DOM построен?"], "DOMContentLoaded"),
]


@template("browser.dom_basics", "DOM: базовые операции", "browser", ("frontend",), 1, "single", time_limit=90, method="pool")
def browser_dom_basics(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, DOM_BASICS, [a for _, a in DOM_BASICS] + ["element.innerHTML = ...", "window.onload()", "event.stopPropagation()"])


@template("browser.cors_credentials", "CORS с учётными данными и CSP", "browser", ("frontend",), 4, "multi", time_limit=210, method="pool")
def browser_cors_credentials(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "При запросе с credentials: 'include' сервер не может ответить Access-Control-Allow-Origin: *",
        "Для передачи cookie в кросс-доменном fetch сервер должен вернуть Access-Control-Allow-Credentials: true",
        "Результат preflight можно кэшировать с помощью Access-Control-Max-Age",
        "Cookie с SameSite=None должна иметь флаг Secure",
        "CSP с директивой script-src без 'unsafe-inline' блокирует inline-обработчики вида onclick=\"...\"",
        "Заголовок Vary: Origin нужен, если сервер отражает Origin в Access-Control-Allow-Origin при кэшировании",
    ]
    false_pool = [
        "Access-Control-Allow-Origin: * разрешает передачу cookie с любого сайта",
        "CORS-ошибка означает, что запрос не дошёл до сервера",
        "Preflight отправляется для любого GET-запроса",
        "CSP настраивается только через JavaScript на клиенте",
        "SameSite=Strict отправляет cookie при переходе по ссылке с другого сайта",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


@template("react.memo_renders", "React: memo, useMemo и useCallback", "framework", ("frontend",), 4, "input", frameworks=("react",),
          time_limit=210)
def react_memo(rng: random.Random, ctx: GenCtx) -> Variant:
    use_memo = rng.random() < 0.75
    value_count = rng.random() < 0.25
    style_inline = rng.random() < 0.4
    handler_inline = rng.random() < 0.4
    k = rng.randint(2, 9)
    child_def = "const Child = memo(function Child({ value, style, onSelect }) {" if use_memo else "function Child({ value, style, onSelect }) {"
    child_end = "});" if use_memo else "}"
    code = (
        f"{child_def}\n  console.log('render');\n  return <div style={{style}} onClick={{onSelect}}>{{value}}</div>;\n{child_end}\n\n"
        "function Parent() {\n  const [count, setCount] = useState(0);\n"
        + ("" if style_inline else "  const style = useMemo(() => ({ color: 'red' }), []);\n")
        + ("" if handler_inline else "  const onSelect = useCallback(() => {}, []);\n")
        + "  return (\n    <>\n      <button onClick={() => setCount(count + 1)}>+</button>\n"
        + f"      <Child\n        value={{{'count' if value_count else '42'}}}\n"
        + f"        style={{{'{ color: ' + chr(39) + 'red' + chr(39) + ' }' if style_inline else 'style'}}}\n"
        + f"        onSelect={{{'() => {}' if handler_inline else 'onSelect'}}}\n      />\n    </>\n  );\n}}"
    )
    rerender = (not use_memo) or value_count or style_inline or handler_inline
    ans = 1 + (k if rerender else 0)
    return Variant(text=f"Сколько раз в консоли появится 'render' после монтирования Parent и {k} кликов по кнопке? (без StrictMode)",
                   kind="input", input_type="number", answer=ans, code=code, code_lang="jsx")


FW_BASICS = [
    (["Как называются данные, которые родительский компонент передаёт дочернему?"], "Пропсы (входные параметры)"),
    (["Как называются внутренние изменяемые данные компонента, при изменении которых он перерисовывается?"], "Состояние (state)"),
    (["Какой атрибут нужен элементам, отрисованным в цикле по списку?"], "key"),
    (["Как называется подход, при котором данные идут сверху вниз от родителя к детям?"], "Однонаправленный поток данных"),
]


@template("framework.basics", "UI-фреймворки: базовые понятия", "framework", ("frontend",), 1, "single", time_limit=90, method="pool")
def framework_basics(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, FW_BASICS, [a for _, a in FW_BASICS] + ["Глобальные переменные", "id", "Двусторонний DOM-биндинг"])


@template("css.cascade", "CSS: каскад, !important и inline-стили", "css", ("frontend",), 4, "single", time_limit=210)
def css_cascade(rng: random.Random, ctx: GenCtx) -> Variant:
    colors = rng.sample(["red", "green", "blue", "orange", "purple", "teal"], 4)
    decls = []
    sels = [("#card .title", (1, 1, 0)), (".title", (0, 1, 0)), ("div p.title", (0, 1, 2)), ("p", (0, 0, 1)), ("#card p", (1, 0, 1))]
    chosen = rng.sample(sels, 3)
    for i, (sel, sp) in enumerate(chosen):
        imp = rng.random() < 0.35
        decls.append({"sel": sel, "spec": sp, "imp": imp, "inline": False, "order": i, "color": colors[i]})
    inline_imp = rng.random() < 0.2
    decls.append({"sel": "style=\"…\"", "spec": (9, 9, 9), "imp": inline_imp, "inline": True, "order": 9, "color": colors[3]})
    win = max(decls, key=lambda d: (d["imp"], d["inline"], d["spec"], d["order"]))
    css = "\n".join(f"{d['sel']} {{ color: {d['color']}{' !important' if d['imp'] else ''}; }}" for d in decls if not d["inline"])
    html = (f'<div id="card">\n  <p class="title" style="color: {colors[3]}{" !important" if inline_imp else ""}">Заголовок</p>\n</div>')
    return single("Каким цветом будет текст «Заголовок»?", win["color"], [c for c in colors if c != win["color"]],
                  code=f"<style>\n{css}\n</style>\n\n{html}", code_lang="html")


# ================================================================== ML
@template("ml.roc_auc", "ROC-AUC по попарным сравнениям", "ml_math", ("ml",), 4, "input", time_limit=240)
def ml_roc_auc(rng: random.Random, ctx: GenCtx) -> Variant:
    scores = rng.sample([x / 100 for x in range(5, 96)], 8)
    labels = [1] * rng.randint(3, 4)
    labels += [0] * (8 - len(labels))
    rng.shuffle(labels)
    pos = [s for s, l in zip(scores, labels) if l]
    neg = [s for s, l in zip(scores, labels) if not l]
    auc = sum(1 for p in pos for n in neg if p > n) / (len(pos) * len(neg))
    table = [{"name": "Предсказания", "columns": ["score", "y"], "rows": [[s, l] for s, l in zip(scores, labels)]}]
    return Variant(text="Вычислите ROC-AUC (до сотых), используя то, что AUC равен доле пар (положительный, отрицательный), "
                   "в которых положительный объект получил больший score.", kind="input", input_type="number", answer=round(auc, 2),
                   tolerance=0.011, tables=table)


TASK_TYPES = [
    (["Предсказать, уйдёт ли клиент в следующем месяце (да/нет)."], "Классификация"),
    (["Спрогнозировать стоимость квартиры в рублях."], "Регрессия"),
    (["Разбить клиентов на группы со схожим поведением без разметки."], "Кластеризация"),
    (["Упорядочить товары в выдаче по вероятности покупки."], "Ранжирование"),
    (["Найти нетипичные транзакции, когда размеченных мошеннических почти нет."], "Обнаружение аномалий"),
]


@template("ml.task_type", "Тип задачи машинного обучения", "ml_theory", ("ml",), 1, "single", time_limit=90, method="pool")
def ml_task_type(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, TASK_TYPES, [a for _, a in TASK_TYPES], prefix="К какому типу относится задача? ")


# ================================================================== визуализация
MISLEADING = [
    (["Столбчатая диаграмма выручки по месяцам, ось Y начинается с 95 млн, рост на 2% выглядит как рост в 3 раза."], "Обрезанная ось Y искажает масштаб"),
    (["Круговая диаграмма из 14 секторов близких размеров."], "Слишком много близких категорий для круговой диаграммы"),
    (["Две линии на графике с разными осями Y слева и справа, линии «пересекаются» в важной точке."], "Двойная ось создаёт ложную связь"),
    (["Объёмная 3D-диаграмма, где дальние столбцы кажутся меньше ближних."], "3D-перспектива искажает восприятие величин"),
]


@template("viz.misleading", "Ошибки визуализации", "visualization", ("data_analyst",), 3, "single", time_limit=120, method="pool")
def viz_misleading(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, MISLEADING, [a for _, a in MISLEADING] + ["Недостаточно цветов в палитре"], prefix="В чём главная проблема графика? ")


# ================================================================== DevOps / сети
@template("linux.namespaces", "Linux: namespaces и cgroups", "linux", ("devops", "infosec"), 4, "multi", time_limit=210, method="pool")
def linux_namespaces(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Namespaces изолируют видимость ресурсов (PID, сеть, точки монтирования), cgroups ограничивают их потребление",
        "Процесс с PID 1 в контейнере должен корректно обрабатывать сигналы и «пожинать» зомби",
        "Привилегированный контейнер (--privileged) фактически даёт доступ к устройствам хоста",
        "Capabilities позволяют выдать процессу часть привилегий root, например CAP_NET_BIND_SERVICE",
        "User namespace позволяет отображать root в контейнере на непривилегированного пользователя хоста",
    ]
    false_pool = [
        "cgroups обеспечивают изоляцию сетевых интерфейсов",
        "Контейнер с --privileged изолирован от хоста так же, как обычный",
        "PID 1 в контейнере автоматически перенаправляет сигналы всем дочерним процессам",
        "Capabilities существуют только в Kubernetes, а не в ядре Linux",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


@template("net.subnet_split", "Сети: разбиение на подсети", "networking", ("devops", "infosec"), 4, "input", time_limit=210)
def net_subnet_split(rng: random.Random, ctx: GenCtx) -> Variant:
    p = rng.choice([20, 22, 23, 24])
    net = ipaddress.ip_network(f"10.{rng.randint(0, 200)}.{rng.randrange(0, 256, 16)}.0/{p}", strict=False)
    k = rng.choice([2, 3, 4])
    subs = list(net.subnets(prefixlen_diff=k))
    m = rng.randint(2, len(subs))
    return Variant(text=f"Сеть {net} разбили на {2 ** k} равные подсети. Какой адрес сети у {m}-й подсети по порядку? (в формате a.b.c.d)",
                   kind="input", input_type="text", answer=[str(subs[m - 1].network_address), str(subs[m - 1])])


@template("ci.pipeline_dag", "CI: критический путь пайплайна", "ci_cd", ("devops",), 4, "input", time_limit=210)
def ci_pipeline_dag(rng: random.Random, ctx: GenCtx) -> Variant:
    d = {j: rng.randint(1, 9) for j in ["lint", "build", "unit", "integration", "security_scan", "package", "deploy"]}
    deps = {"lint": [], "build": [], "unit": ["build"], "integration": ["build"], "security_scan": rng.choice([[], ["build"]]),
            "package": ["unit", "integration"], "deploy": ["package", "lint", "security_scan"]}
    finish = {}

    def f(j):
        if j not in finish:
            finish[j] = max((f(x) for x in deps[j]), default=0) + d[j]
        return finish[j]

    total = f("deploy")
    lines = "\n".join(f"{j:<14} {d[j]} мин  needs: {', '.join(deps[j]) or '—'}" for j in d)
    return Variant(text="Джобы пайплайна, их длительность и зависимости. Раннеров неограниченно, джоба стартует сразу после завершения "
                   "всех зависимостей. За сколько минут завершится deploy?", kind="input", input_type="number", answer=total, code=lines,
                   code_lang="text")


# ================================================================== QA
@template("qa.mcdc", "Критерии покрытия условий (MC/DC)", "test_design", ("qa",), 4, "single", time_limit=150)
def qa_mcdc(rng: random.Random, ctx: GenCtx) -> Variant:
    n = rng.randint(2, 5)
    crit = rng.choice(["MC/DC", "покрытия всех комбинаций условий (MCC)", "покрытия решений (decision coverage)"])
    ans = {"MC/DC": n + 1, "покрытия всех комбинаций условий (MCC)": 2**n, "покрытия решений (decision coverage)": 2}[crit]
    cands = [str(x) for x in (n + 1, 2**n, 2, n, 2 * n)]
    return single(f"Решение в коде состоит из {n} независимых булевых условий. Какое минимальное число тестов нужно для критерия {crit}?",
                  str(ans), pick_distractors(rng, str(ans), cands, 3))


@template("qa.dre", "Эффективность устранения дефектов (DRE)", "qa_process", ("qa",), 3, "input", time_limit=150)
def qa_dre(rng: random.Random, ctx: GenCtx) -> Variant:
    x, y = rng.randint(40, 300), rng.randint(3, 60)
    return Variant(text=f"До релиза команда нашла {x} дефектов, после релиза пользователи сообщили ещё о {y}. "
                   "Вычислите DRE (Defect Removal Efficiency) в процентах (до десятых).", kind="input", input_type="number",
                   answer=round(x / (x + y) * 100, 1), tolerance=0.11)


@template("qa.test_strategy", "Стратегия тестирования", "qa_process", ("qa",), 4, "multi", time_limit=210, method="pool")
def qa_test_strategy(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Контрактное тестирование (consumer-driven contracts) снижает потребность в сквозных тестах между микросервисами",
        "Риск-ориентированное тестирование распределяет усилия по вероятности и тяжести последствий отказа",
        "Мутационное тестирование оценивает качество набора тестов, а не только покрытие строк",
        "Тестовые данные должны быть изолированы и воспроизводимы для стабильных автотестов",
        "Высокое покрытие кода не гарантирует отсутствия дефектов в бизнес-логике",
    ]
    false_pool = [
        "100% покрытие строк кода гарантирует отсутствие ошибок",
        "Сквозные тесты дешевле и быстрее модульных",
        "Мутационное тестирование изменяет тестовые данные в продакшене",
        "При риск-ориентированном подходе все функции тестируются одинаково глубоко",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


# ================================================================== ИБ: Senior
@template("sec.ip_decimal", "Обход фильтров SSRF: формы записи IP", "web_security", ("infosec",), 4, "input", time_limit=180)
def sec_ip_decimal(rng: random.Random, ctx: GenCtx) -> Variant:
    ip = ipaddress.ip_address(rng.choice([f"127.0.{rng.randint(0, 9)}.{rng.randint(1, 254)}", f"169.254.169.254",
                                          f"10.{rng.randint(0, 20)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}",
                                          f"192.168.{rng.randint(0, 9)}.{rng.randint(1, 254)}"]))
    if rng.random() < 0.5:
        return Variant(text=f"Фильтр SSRF блокирует строки вида «a.b.c.d» для внутренних сетей, но пропускает URL http://{int(ip)}/. "
                       "На какой IP-адрес (в точечной записи) уйдёт запрос?", kind="input", input_type="text", answer=[str(ip)])
    return Variant(text=f"Запишите адрес {ip} одним десятичным числом (как его поймёт большинство HTTP-клиентов).", kind="input",
                   input_type="number", answer=int(ip))


@template("sec.diffie_hellman", "Протокол Диффи — Хеллмана", "crypto", ("infosec",), 4, "input", time_limit=210)
def sec_dh(rng: random.Random, ctx: GenCtx) -> Variant:
    p, g = rng.choice([(23, 5), (29, 2), (31, 3), (37, 2), (41, 6), (43, 3), (47, 5)])
    a, b = rng.randint(3, 12), rng.randint(3, 12)
    B = pow(g, b, p)
    s = pow(B, a, p)
    return Variant(text=f"Параметры DH: p = {p}, g = {g}. Секрет Алисы a = {a}, Боб прислал B = {B}. Каков общий секрет (B^a mod p)?",
                   kind="input", input_type="number", answer=s)


@template("sec.rsa_small", "RSA на малых числах", "crypto", ("infosec",), 4, "input", time_limit=240)
def sec_rsa(rng: random.Random, ctx: GenCtx) -> Variant:
    import math

    while True:
        p, q = rng.sample([11, 13, 17, 19, 23, 29], 2)
        phi = (p - 1) * (q - 1)
        e = rng.choice([3, 5, 7, 11, 13, 17])
        if math.gcd(e, phi) == 1:
            break
    d = pow(e, -1, phi)
    return Variant(text=f"RSA: p = {p}, q = {q}, открытая экспонента e = {e}. Найдите закрытую экспоненту d (наименьшее положительное, "
                   "e·d ≡ 1 mod φ(n)).", kind="input", input_type="number", answer=d)


@template("forensics.beaconing", "Обнаружение C2-beaconing по журналу соединений", "forensics", ("infosec",), 4, "input", time_limit=240)
def forensics_beaconing(rng: random.Random, ctx: GenCtx) -> Variant:
    interval = rng.choice([30, 60, 90, 120, 300])
    t = datetime(2026, 10, 5, 3, rng.randint(0, 50), rng.randint(0, 59))
    c2 = f"185.{rng.randint(10, 250)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"
    events = []
    for _ in range(8):
        t = t + timedelta(seconds=interval + rng.randint(-3, 3))
        events.append((t, c2, rng.randint(180, 260)))
    for _ in range(4):
        noise = events[0][0] + timedelta(seconds=rng.randint(0, interval * 8))
        events.append((noise, f"93.{rng.randint(10, 250)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}", rng.randint(500, 90000)))
    events.sort()
    lines = "\n".join(f"{e[0]:%H:%M:%S}  host-17 -> {e[1]}:443  bytes={e[2]}" for e in events)
    return Variant(text="В журнале соединений хоста виден регулярный исходящий трафик к одному адресу (подозрение на C2-маяк). "
                   "Каков период маяка в секундах (с точностью до ±5 с)?", kind="input", input_type="number", answer=interval, tolerance=5,
                   code=lines, code_lang="text")
