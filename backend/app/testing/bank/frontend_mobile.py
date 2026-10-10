"""Frontend (CSS, DOM, фреймворки) и мобильная разработка."""
from __future__ import annotations

import random

from app.testing.bank.base import GenCtx, Variant, pick_distractors, scenario_single, single, statements_multi, template

FE = ("frontend",)


# ================================================================== CSS
def _selector(rng: random.Random):
    ids = rng.randint(0, 1) if rng.random() < 0.6 else 0
    classes = rng.randint(0, 3)
    elems = rng.randint(0, 3)
    parts = []
    tags = ["div", "ul", "li", "a", "span", "p", "section", "button", "nav"]
    cls = [".card", ".active", ".btn", ".title", ".item", ".menu", ":hover", "[type=\"text\"]", ":first-child"]
    idn = ["#app", "#main", "#nav", "#header"]
    for _ in range(elems):
        parts.append(rng.choice(tags))
    for _ in range(classes):
        if parts and rng.random() < 0.5:
            parts[-1] += rng.choice(cls)
        else:
            parts.append(rng.choice(cls))
    for _ in range(ids):
        parts.insert(rng.randint(0, len(parts)), rng.choice(idn))
    if not parts:
        parts = [rng.choice(tags)]
    sel = " ".join(parts)
    # подсчёт специфичности (a, b, c)
    import re

    a = len(re.findall(r"#[\w-]+", sel))
    b = len(re.findall(r"\.[\w-]+", sel)) + len(re.findall(r"\[[^\]]+\]", sel)) + len(re.findall(r"(?<!:):[\w-]+", sel))
    c = len(re.findall(r"(?:^|\s)([a-z]+)", sel))
    return sel, (a, b, c)


@template("css.specificity", "CSS: специфичность селекторов", "css", FE, 2, "single", time_limit=150)
def css_specificity(rng: random.Random, ctx: GenCtx) -> Variant:
    for _ in range(50):
        sels = [_selector(rng) for _ in range(4)]
        specs = [s for _, s in sels]
        if len({s for s, _ in sels}) == 4 and specs.count(max(specs)) == 1:
            break
    best = max(sels, key=lambda t: t[1])[0]
    return single("Все селекторы задают `color` одному и тому же элементу. Правило с каким селектором победит?", best,
                  [s for s, _ in sels if s != best])


@template("css.box_model", "CSS: блочная модель и box-sizing", "css", FE, 1, "input", time_limit=120)
def css_box_model(rng: random.Random, ctx: GenCtx) -> Variant:
    w, p, b, m = rng.randrange(100, 400, 10), rng.randrange(4, 32, 2), rng.randint(1, 5), rng.randrange(0, 40, 5)
    sizing = rng.choice(["content-box", "border-box"])
    ask_content = sizing == "border-box" and rng.random() < 0.5
    css = f".box {{\n  box-sizing: {sizing};\n  width: {w}px;\n  padding: 0 {p}px;\n  border: {b}px solid;\n  margin: 0 {m}px;\n}}"
    if ask_content:
        ans, q = w - 2 * p - 2 * b, "Какова ширина области содержимого (content) в пикселях?"
    else:
        ans = w if sizing == "border-box" else w + 2 * p + 2 * b
        q = "Какую ширину в пикселях займёт элемент от внешнего края левой рамки до внешнего края правой (без margin)?"
    return Variant(text=q, kind="input", input_type="number", answer=ans, code=css, code_lang="css")


@template("css.flex_grow", "CSS: распределение места во flex-контейнере", "css", FE, 3, "input", time_limit=210)
def css_flex_grow(rng: random.Random, ctx: GenCtx) -> Variant:
    n = rng.randint(2, 3)
    bases = [rng.randrange(40, 160, 20) for _ in range(n)]
    grows = [rng.randint(0, 3) for _ in range(n)]
    if sum(grows) == 0:
        grows[0] = 1
    gap = rng.choice([0, 10, 20])
    unit = rng.randrange(10, 60, 10)
    free = unit * sum(grows)
    W = sum(bases) + gap * (n - 1) + free
    k = rng.randrange(n)
    items = "\n".join(f".item{i + 1} {{ flex: {g} 0 {bb}px; }}" for i, (g, bb) in enumerate(zip(grows, bases)))
    css = f".row {{ display: flex; width: {W}px; gap: {gap}px; }}\n{items}"
    ans = bases[k] + free * grows[k] // sum(grows)
    return Variant(text=f"Какой будет итоговая ширина `.item{k + 1}` в пикселях? (рамок и паддингов нет)", kind="input", input_type="number",
                   answer=ans, code=css, code_lang="css")


@template("css.units", "CSS: относительные единицы em/rem", "css", FE, 2, "input", time_limit=150)
def css_units(rng: random.Random, ctx: GenCtx) -> Variant:
    root, parent = rng.choice([10, 16, 20]), rng.choice([12, 14, 18, 20])
    fs = rng.choice([1.5, 2, 0.5, 1.25])
    prop = rng.choice(["padding-rem", "width-em", "font"])
    css = f"html {{ font-size: {root}px; }}\n.parent {{ font-size: {parent}px; }}\n.child {{\n  font-size: {fs}em;\n"
    if prop == "padding-rem":
        k = rng.choice([1, 1.5, 2, 3])
        css += f"  padding-left: {k}rem;\n}}"
        ans, q = root * k, "Чему равен вычисленный padding-left у `.child` в пикселях?"
    elif prop == "width-em":
        k = rng.choice([2, 3, 10])
        css += f"  width: {k}em;\n}}"
        ans, q = parent * fs * k, "Чему равна вычисленная ширина `.child` в пикселях?"
    else:
        css += "}"
        ans, q = parent * fs, "Чему равен вычисленный font-size у `.child` в пикселях?"
    return Variant(text=q + " (`.child` вложен в `.parent`)", kind="input", input_type="number", answer=ans, tolerance=0.01, code=css,
                   code_lang="css")


@template("css.layout_facts", "CSS: позиционирование и отображение", "css", FE, 2, "multi", time_limit=150, method="pool")
def css_layout_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Элемент с position: absolute позиционируется относительно ближайшего предка с position, отличным от static",
        "display: none убирает элемент из потока, а visibility: hidden — сохраняет занимаемое место",
        "Вертикальные внешние отступы соседних блоков могут схлопываться (margin collapsing)",
        "Свойство transform у предка создаёт новый контекст наложения (stacking context)",
        "Для строчных (inline) элементов свойства width и height не применяются",
        "position: sticky работает относительно ближайшего прокручиваемого предка",
    ]
    false_pool = [
        "z-index работает для любых элементов, включая position: static вне flex/grid",
        "position: fixed всегда позиционируется относительно body",
        "Горизонтальные margin соседних inline-block элементов схлопываются",
        "opacity: 0 убирает элемент из потока документа",
        "Единица rem вычисляется от font-size родителя",
    ]
    return statements_multi(rng, ["Какие утверждения о CSS верны?"], true_pool, false_pool)


# ================================================================== DOM и браузер
@template("dom.event_propagation", "DOM: погружение и всплытие событий", "browser", FE, 3, "input", time_limit=210)
def dom_event_propagation(rng: random.Random, ctx: GenCtx) -> Variant:
    els = ["outer", "middle", "inner"]
    labels = iter(rng.sample(range(1, 10), 6))
    listeners = []  # (element, capture, label)
    for el in els:
        for capture in (True, False):
            if rng.random() < 0.65:
                listeners.append((el, capture, next(labels)))
    if len(listeners) < 3:
        listeners = [("outer", True, 1), ("inner", False, 2), ("middle", False, 3)]
    stop = rng.random() < 0.4 and any(el == "middle" and not cap for el, cap, _ in listeners)
    rng.shuffle(listeners)  # порядок регистрации не влияет: на элемент максимум один слушатель на фазу
    code_lines = []
    for el, cap, lab in listeners:
        body = f"console.log({lab})" + ("; e.stopPropagation()" if stop and el == "middle" and not cap else "")
        opt = ", true" if cap else ""
        code_lines.append(f"{el}.addEventListener('click', (e) => {{ {body}; }}{opt});")
    html = '<div id="outer">\n  <div id="middle">\n    <button id="inner">OK</button>\n  </div>\n</div>'
    get = {(el, cap): lab for el, cap, lab in listeners}
    order = []
    for el in ("outer", "middle"):
        if (el, True) in get:
            order.append(get[(el, True)])
    for cap in (True, False):  # на целевом элементе: сначала capture-, затем bubble-слушатели
        if ("inner", cap) in get:
            order.append(get[("inner", cap)])
    for el in ("middle", "outer"):
        if (el, False) in get:
            order.append(get[(el, False)])
            if stop and el == "middle":
                break
    out = [str(x) for x in order]
    return Variant(
        text="Пользователь кликает по кнопке `#inner`. В каком порядке будут выведены числа? Введите через пробел.",
        kind="input",
        input_type="text",
        answer=[" ".join(out), "".join(out)],
        code=html + "\n\n<script>\n" + "\n".join(code_lines) + "\n</script>",
        code_lang="html",
    )


@template("browser.security_storage", "Браузер: хранилища и безопасность", "browser", ("frontend", "infosec"), 2, "multi", time_limit=150,
          method="pool")
def browser_security(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Cookie с флагом HttpOnly недоступна из JavaScript через document.cookie",
        "SameSite=Lax не отправляет cookie в большинстве кросс-сайтовых POST-запросов",
        "localStorage доступен всем скриптам того же origin, поэтому XSS может украсть хранящийся там токен",
        "sessionStorage изолирован для каждой вкладки",
        "Content-Security-Policy позволяет ограничить источники выполняемых скриптов",
        "Same-origin policy определяет origin как схему, хост и порт",
    ]
    false_pool = [
        "CORS защищает сервер от запросов злоумышленника из curl",
        "localStorage автоматически отправляется на сервер с каждым запросом",
        "Флаг Secure запрещает чтение cookie из JavaScript",
        "Origin https://site.ru и https://site.ru:8443 считаются одинаковыми",
        "sessionStorage общий для всех вкладок одного сайта",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


@template("browser.rendering", "Браузер: рендеринг и производительность", "browser", FE, 3, "multi", time_limit=180, method="pool")
def browser_rendering(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Изменение transform и opacity обычно не вызывает перерасчёт layout",
        "Скрипт с атрибутом defer выполняется после разбора HTML в порядке подключения",
        "Чтение offsetHeight сразу после изменения стилей может вызвать принудительный синхронный layout",
        "LCP измеряет время отрисовки самого крупного видимого элемента",
        "CLS отражает неожиданные сдвиги макета при загрузке",
        "requestAnimationFrame вызывает колбэк перед следующей перерисовкой",
    ]
    false_pool = [
        "Скрипты с атрибутом async всегда выполняются в порядке подключения",
        "Изменение width никогда не вызывает reflow",
        "INP измеряет время до первого байта ответа сервера",
        "Web Worker имеет прямой доступ к DOM",
        "Блокирующий CSS не влияет на время первой отрисовки",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


# ================================================================== фреймворки
@template("react.state_updates", "React: очередь обновлений состояния", "framework", FE, 3, "input", frameworks=("react",), time_limit=180)
def react_state(rng: random.Random, ctx: GenCtx) -> Variant:
    c0 = rng.randint(0, 5)
    ops = []
    for _ in range(rng.randint(3, 4)):
        x = rng.randint(1, 5)
        ops.append(("replace", x) if rng.random() < 0.5 else ("update", x))
    if all(k == "replace" for k, _ in ops):
        ops[-1] = ("update", ops[-1][1])
    state = c0
    for kind, x in ops:
        state = c0 + x if kind == "replace" else state + x
    lines = "\n".join(f"    setCount(count + {x});" if k == "replace" else f"    setCount((c) => c + {x});" for k, x in ops)
    code = (f"function Counter() {{\n  const [count, setCount] = useState({c0});\n\n  function handleClick() {{\n{lines}\n  }}\n\n"
            "  return <button onClick={handleClick}>{count}</button>;\n}")
    return Variant(text="Какое число будет на кнопке после одного клика?", kind="input", input_type="number", answer=state, code=code,
                   code_lang="jsx")


@template("react.effects_order", "React: порядок рендера и эффектов", "framework", FE, 3, "input", frameworks=("react",), time_limit=180)
def react_effects(rng: random.Random, ctx: GenCtx) -> Variant:
    p_r, p_e, c_r, c_e = rng.sample(range(1, 10), 4)
    code = (
        f"function Child() {{\n  console.log({c_r});\n  useEffect(() => {{ console.log({c_e}); }}, []);\n  return null;\n}}\n\n"
        f"function Parent() {{\n  console.log({p_r});\n  useEffect(() => {{ console.log({p_e}); }}, []);\n  return <Child />;\n}}"
    )
    out = [str(x) for x in (p_r, c_r, c_e, p_e)]
    return Variant(text="Компонент `Parent` монтируется впервые (без StrictMode). В каком порядке будут выведены числа?",
                   kind="input", input_type="text", answer=[" ".join(out), "".join(out)], code=code, code_lang="jsx")


@template("react.facts", "React: хуки и рендеринг", "framework", FE, 2, "multi", frameworks=("react",), time_limit=150, method="pool")
def react_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Хуки нельзя вызывать внутри условий и циклов",
        "Ключи (key) в списках помогают React сопоставлять элементы между рендерами",
        "Эффект с пустым массивом зависимостей выполняется после первого монтирования",
        "В React 18 обновления состояния автоматически батчатся, в том числе в setTimeout и промисах",
        "useMemo кэширует результат вычисления между рендерами при неизменных зависимостях",
        "В StrictMode в режиме разработки компоненты могут рендериться дважды",
    ]
    false_pool = [
        "Индекс массива — всегда лучший key для динамических списков",
        "setState мгновенно изменяет значение переменной состояния в текущем рендере",
        "useEffect выполняется синхронно до отрисовки в браузере",
        "useCallback предотвращает повторный рендер самого компонента",
        "Мутация объекта состояния напрямую гарантированно вызывает перерисовку",
    ]
    return statements_multi(rng, ["Какие утверждения о React верны?"], true_pool, false_pool)


@template("vue.facts", "Vue: реактивность и шаблоны", "framework", FE, 2, "multi", frameworks=("vue",), time_limit=150, method="pool")
def vue_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "computed-свойства кэшируются и пересчитываются только при изменении зависимостей",
        "v-show переключает CSS display, а v-if создаёт и удаляет элементы",
        "Пропсы передаются однонаправленно: дочерний компонент не должен их изменять",
        "ref() требует обращения к .value в скриптах Composition API",
        "Атрибут key в v-for нужен для корректного переиспользования элементов",
    ]
    false_pool = [
        "watch и computed полностью взаимозаменяемы",
        "v-if и v-show одинаково влияют на жизненный цикл компонента",
        "Изменение пропса в дочернем компоненте — рекомендуемый способ передать данные родителю",
        "reactive() работает с примитивами так же, как ref()",
    ]
    return statements_multi(rng, ["Какие утверждения о Vue верны?"], true_pool, false_pool)


@template("angular.facts", "Angular: архитектура и RxJS", "framework", FE, 2, "multi", frameworks=("angular",), time_limit=150, method="pool")
def angular_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Стратегия OnPush проверяет компонент при смене ссылок во входных данных, событиях и async pipe",
        "switchMap отменяет предыдущий внутренний Observable при новом значении",
        "Сервисы с providedIn: 'root' — синглтоны в пределах приложения",
        "async pipe автоматически отписывается при уничтожении компонента",
        "Standalone-компоненты можно использовать без NgModule",
    ]
    false_pool = [
        "mergeMap гарантирует порядок завершения внутренних Observable",
        "ngOnInit вызывается до установки входных свойств @Input",
        "Подписки на Observable в компонентах всегда освобождаются автоматически",
        "Default change detection проверяет только компоненты с OnPush",
    ]
    return statements_multi(rng, ["Какие утверждения об Angular верны?"], true_pool, false_pool)


# ================================================================== мобильная разработка
MOB = ("mobile",)
PLATFORM = {"kotlin": "Android", "swift": "iOS", "dart": "Flutter"}


@template("mobile.density", "Плотность экрана: dp/pt → px", "mobile_platform", MOB, 1, "input", time_limit=120)
def mobile_density(rng: random.Random, ctx: GenCtx) -> Variant:
    plat = PLATFORM.get(ctx.lang or "kotlin", "Android")
    v = rng.choice(range(4, 100, 2))
    if plat == "Android":
        name, f = rng.choice([("mdpi", 1), ("hdpi", 1.5), ("xhdpi", 2), ("xxhdpi", 3), ("xxxhdpi", 4)])
        what = rng.choice(["Отступ", "Высота кнопки", "Размер иконки", "Ширина разделителя"])
        text = f"{what} задан(а) как {v}dp. Сколько физических пикселей это займёт на экране плотности {name}?"
    elif plat == "iOS":
        name, f = rng.choice([("@2x", 2), ("@3x", 3)])
        text = f"Элемент высотой {v} pt. Сколько физических пикселей по высоте он займёт на устройстве с масштабом {name}?"
    else:
        f = rng.choice([1.5, 2.0, 2.25, 2.5, 2.625, 2.75, 3.0, 3.5])
        text = f"Виджет шириной {v} логических пикселей. Сколько физических пикселей он займёт при devicePixelRatio = {f}?"
    return Variant(text=text, kind="input", input_type="number", answer=v * f, tolerance=0.01)


LIFECYCLE = {
    "kotlin": [
        (["Какие колбэки Activity вызываются при повороте экрана (без configChanges) — по порядку?"],
         "onPause → onStop → onDestroy → onCreate → onStart → onResume"),
        (["Что переживает смену конфигурации Activity без ручного сохранения состояния?"], "ViewModel"),
        (["Какой компонент гарантированно выполнит отложенную фоновую работу даже после перезапуска устройства?"], "WorkManager"),
    ],
    "swift": [
        (["Какой метод UIViewController вызывается один раз после загрузки view в память?"], "viewDidLoad"),
        (["Какой property wrapper SwiftUI используют, чтобы View владела жизненным циклом ObservableObject?"], "@StateObject"),
        (["Где должны выполняться обновления UI в iOS?"], "На главном потоке (MainActor)"),
    ],
    "dart": [
        (["Какой метод State вызывается один раз при вставке виджета в дерево?"], "initState"),
        (["Как сообщить фреймворку, что внутреннее состояние StatefulWidget изменилось?"], "Вызвать setState"),
        (["Где нужно освобождать контроллеры анимаций и подписки на стримы?"], "В методе dispose"),
    ],
}
LIFECYCLE_SPACE = {
    "kotlin": ["onPause → onStop → onDestroy → onCreate → onStart → onResume", "onStop → onPause → onCreate → onResume",
               "ViewModel", "WorkManager", "AsyncTask", "Service без foreground-уведомления", "onSaveInstanceState → onResume", "Fragment"],
    "swift": ["viewDidLoad", "viewWillAppear", "loadView", "@StateObject", "@ObservedObject", "@State", "На главном потоке (MainActor)",
              "В любом фоновом потоке", "В отдельном OperationQueue"],
    "dart": ["initState", "build", "didUpdateWidget", "Вызвать setState", "Перезапустить приложение", "Вызвать build вручную",
             "В методе dispose", "В методе build", "В конструкторе виджета"],
}


@template("mobile.lifecycle", "Жизненный цикл экрана", "mobile_platform", MOB, 2, "single", time_limit=120, method="pool")
def mobile_lifecycle(rng: random.Random, ctx: GenCtx) -> Variant:
    lang = ctx.lang if ctx.lang in LIFECYCLE else "kotlin"
    return scenario_single(rng, LIFECYCLE[lang], LIFECYCLE_SPACE[lang])


MOBILE_FACTS = {
    "kotlin": (
        ["Длительная блокировка главного потока Android приводит к ANR",
         "Dispatchers.IO предназначен для блокирующих операций ввода-вывода",
         "Room проверяет SQL-запросы на этапе компиляции",
         "remember в Compose хранит значение между рекомпозициями, но не переживает смену конфигурации без rememberSaveable",
         "Отмена родительской корутины отменяет дочерние (structured concurrency)"],
        ["Сетевые запросы на главном потоке разрешены по умолчанию",
         "GlobalScope — рекомендуемый способ запуска корутин в ViewModel",
         "remember сохраняет значение после смерти процесса",
         "Activity можно безопасно хранить в статическом поле синглтона"],
    ),
    "swift": (
        ["Сильные ссылки в замыкании на self могут создать цикл удержания (retain cycle)",
         "weak-ссылка становится nil после освобождения объекта",
         "Структуры в Swift — типы-значения",
         "async/await в Swift выполняет код на акторах; обновлять UI нужно на MainActor",
         "@State предназначен для локального состояния самой View"],
        ["ARC — это сборщик мусора с периодической трассировкой",
         "unowned-ссылка безопасна после освобождения объекта",
         "@ObservedObject гарантирует владение жизненным циклом объекта",
         "Обновлять UIKit из фонового потока безопасно"],
    ),
    "dart": (
        ["Метод build должен быть быстрым и без побочных эффектов",
         "const-конструкторы позволяют Flutter переиспользовать виджеты",
         "Изоляты (isolates) не разделяют память и общаются сообщениями",
         "Keys помогают сохранять состояние при перестановке виджетов в списке",
         "Hot reload сохраняет состояние приложения"],
        ["StatelessWidget может хранить изменяемое состояние между перестроениями",
         "Future выполняется в отдельном потоке ОС по умолчанию",
         "setState можно вызывать после dispose без последствий",
         "Каждый вызов build пересоздаёт объекты State всех дочерних виджетов"],
    ),
}


@template("mobile.platform_facts", "Платформа: потоки, память, UI", "mobile_platform", MOB, 3, "multi", time_limit=180, method="pool")
def mobile_platform_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    lang = ctx.lang if ctx.lang in MOBILE_FACTS else "kotlin"
    t, f = MOBILE_FACTS[lang]
    return statements_multi(rng, [f"Какие утверждения о разработке под {PLATFORM[lang]} верны?"], t, f, n=5)


@template("mobile.release", "Публикация и релизы мобильных приложений", "mobile_platform", MOB, 2, "multi", time_limit=150, method="pool")
def mobile_release(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Поэтапная раскатка (staged rollout) позволяет выпустить версию сначала на часть пользователей",
        "Обновление приложения в сторе должно быть подписано тем же ключом/сертификатом",
        "Номер сборки (versionCode / build number) должен увеличиваться с каждой публикацией",
        "Feature flags позволяют отключить функциональность без выпуска новой версии",
    ]
    false_pool = [
        "Пользователи мгновенно получают новую версию сразу после публикации",
        "Удалить уже установленную версию у пользователей можно одной кнопкой в консоли",
        "Номер сборки можно переиспользовать при повторной загрузке",
        "Обфускация кода гарантирует невозможность реверс-инжиниринга",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool, n=5)


MEMORY_SCEN = {
    "kotlin": [(["Синглтон-менеджер хранит ссылку на Activity, переданную при инициализации. Что произойдёт после поворота экрана?"],
                "Старая Activity не будет освобождена — утечка памяти")],
    "swift": [(["Класс ViewModel хранит замыкание onUpdate, внутри которого используется self без [weak self]. View держит ViewModel. Что произойдёт?"],
               "Возникнет цикл сильных ссылок — объекты не освободятся")],
    "dart": [(["В State создаётся StreamSubscription в initState, но не отменяется в dispose. Что произойдёт после ухода с экрана?"],
              "Подписка продолжит работать и удерживать State — утечка и вызовы setState после dispose")],
}


@template("mobile.memory", "Утечки памяти в мобильных приложениях", "mobile_platform", MOB, 4, "single", time_limit=150, method="pool")
def mobile_memory(rng: random.Random, ctx: GenCtx) -> Variant:
    lang = ctx.lang if ctx.lang in MEMORY_SCEN else "kotlin"
    texts, correct = rng.choice(MEMORY_SCEN[lang])
    wrong = ["Сборщик мусора/ARC освободит всё автоматически, проблем нет", "Приложение упадёт с ошибкой компиляции",
             "Объект будет пересоздан с нуля при каждом обращении", "Система заморозит процесс до перезапуска"]
    return single(texts[0], correct, rng.sample(wrong, 3))
