"""Data Science / ML, статистика, продуктовая аналитика, визуализация."""
from __future__ import annotations

import math
import random

from app.testing.bank.base import GenCtx, Variant, pick_distractors, scenario_single, single, statements_multi, template

ML = ("ml",)
STAT = ("ml", "data_analyst")
DA = ("data_analyst",)


def _r2(x: float) -> float:
    return round(x + 1e-12, 2)


# ================================================================== метрики классификации
def _confusion(rng):
    return rng.randint(20, 90), rng.randint(5, 40), rng.randint(5, 40), rng.randint(40, 200)


def _cm_table(tp, fp, fn, tn):
    return [{"name": "Матрица ошибок", "columns": ["", "Предсказано: 1", "Предсказано: 0"],
             "rows": [["Факт: 1", tp, fn], ["Факт: 0", fp, tn]]}]


@template("ml.confusion_basic", "Метрики по матрице ошибок", "ml_math", ML, 1, "input", time_limit=150)
def ml_confusion_basic(rng: random.Random, ctx: GenCtx) -> Variant:
    tp, fp, fn, tn = _confusion(rng)
    metric = rng.choice(["accuracy", "precision", "recall"])
    val = {"accuracy": (tp + tn) / (tp + fp + fn + tn), "precision": tp / (tp + fp), "recall": tp / (tp + fn)}[metric]
    return Variant(text=f"Вычислите {metric} модели (доля, округлите до сотых).", kind="input", input_type="number", answer=_r2(val),
                   tolerance=0.011, tables=_cm_table(tp, fp, fn, tn))


@template("ml.confusion_f1", "F1, специфичность, FPR", "ml_math", ML, 2, "input", time_limit=180)
def ml_confusion_f1(rng: random.Random, ctx: GenCtx) -> Variant:
    tp, fp, fn, tn = _confusion(rng)
    metric = rng.choice(["F1-мера", "специфичность (TNR)", "FPR"])
    p, r = tp / (tp + fp), tp / (tp + fn)
    val = {"F1-мера": 2 * p * r / (p + r), "специфичность (TNR)": tn / (tn + fp), "FPR": fp / (fp + tn)}[metric]
    return Variant(text=f"Вычислите {metric} (доля, до сотых).", kind="input", input_type="number", answer=_r2(val), tolerance=0.011,
                   tables=_cm_table(tp, fp, fn, tn))


@template("ml.threshold", "Порог классификации и метрики", "ml_math", ML, 3, "input", time_limit=210)
def ml_threshold(rng: random.Random, ctx: GenCtx) -> Variant:
    n = 10
    scores = sorted({round(rng.uniform(0.05, 0.95), 2) for _ in range(n + 4)})[:n]
    rng.shuffle(scores)
    labels = [1 if rng.random() < 0.5 + (s - 0.5) * 0.8 else 0 for s in scores]
    if sum(labels) == 0:
        labels[0] = 1
    thr = rng.choice([0.4, 0.5, 0.6])
    pred = [1 if s >= thr else 0 for s in scores]
    tp = sum(p and l for p, l in zip(pred, labels))
    fp = sum(p and not l for p, l in zip(pred, labels))
    fn = sum((not p) and l for p, l in zip(pred, labels))
    metric = rng.choice(["precision", "recall"])
    if metric == "precision" and tp + fp == 0:
        metric = "recall"
    val = tp / (tp + fp) if metric == "precision" else tp / (tp + fn)
    table = [{"name": "Объекты", "columns": ["score", "y"], "rows": [[s, l] for s, l in zip(scores, labels)]}]
    return Variant(text=f"Объект относится к классу 1, если score ≥ {thr}. Чему равен {metric} (до сотых)?", kind="input", input_type="number",
                   answer=_r2(val), tolerance=0.011, tables=table)


@template("ml.impurity", "Энтропия и индекс Джини", "ml_theory", ML, 3, "input", time_limit=180)
def ml_impurity(rng: random.Random, ctx: GenCtx) -> Variant:
    counts = [rng.randint(1, 12) for _ in range(rng.choice([2, 3]))]
    total = sum(counts)
    ps = [c / total for c in counts]
    if rng.random() < 0.5:
        val, name = 1 - sum(p * p for p in ps), "индекс Джини"
    else:
        val, name = -sum(p * math.log2(p) for p in ps), "энтропию Шеннона (log₂, в битах)"
    return Variant(text=f"В узле дерева {total} объектов, распределение по классам: {', '.join(map(str, counts))}. Вычислите {name} (до сотых).",
                   kind="input", input_type="number", answer=_r2(val), tolerance=0.011)


@template("ml.gd_step", "Шаг градиентного спуска", "ml_math", ML, 3, "input", time_limit=210)
def ml_gd_step(rng: random.Random, ctx: GenCtx) -> Variant:
    xs = [rng.randint(1, 4) for _ in range(3)]
    w_true = rng.choice([2, 3])
    ys = [w_true * x + rng.choice([-1, 0, 1]) for x in xs]
    w0, lr = rng.choice([0, 1]), rng.choice([0.01, 0.05, 0.1])
    n = len(xs)
    grad = 2 / n * sum((w0 * x - y) * x for x, y in zip(xs, ys))
    w1 = w0 - lr * grad
    pts = ", ".join(f"({x}, {y})" for x, y in zip(xs, ys))
    return Variant(text=f"Модель ŷ = w·x без свободного члена, функция потерь — MSE = (1/n)·Σ(ŷ − y)². Данные (x, y): {pts}. "
                   f"Начальное w = {w0}, скорость обучения {lr}. Каким станет w после одного шага градиентного спуска (до сотых)?",
                   kind="input", input_type="number", answer=_r2(w1), tolerance=0.011)


@template("ml.kmeans_step", "Итерация k-means", "ml_theory", ML, 3, "input", time_limit=180)
def ml_kmeans(rng: random.Random, ctx: GenCtx) -> Variant:
    pts = sorted(rng.sample(range(0, 30), 7))
    c1, c2 = rng.sample(pts, 2)
    c1, c2 = min(c1, c2), max(c1, c2)
    if c1 == c2:
        c2 += 5
    g1 = [p for p in pts if abs(p - c1) <= abs(p - c2)]
    g2 = [p for p in pts if abs(p - c1) > abs(p - c2)]
    which = rng.choice([1, 2]) if g2 else 1
    g = g1 if which == 1 else g2
    return Variant(text=f"Одномерные точки: {pts}. Начальные центроиды: c₁ = {c1}, c₂ = {c2} (при равенстве расстояний точка идёт к c₁). "
                   f"Каким станет c{'₁' if which == 1 else '₂'} после одной итерации k-means (до сотых)?",
                   kind="input", input_type="number", answer=_r2(sum(g) / len(g)), tolerance=0.011)


@template("ml.knn", "Классификация методом k ближайших соседей", "ml_theory", ML, 2, "single", time_limit=150)
def ml_knn(rng: random.Random, ctx: GenCtx) -> Variant:
    for _ in range(100):
        pts = [((rng.randint(0, 9), rng.randint(0, 9)), rng.choice("AB")) for _ in range(7)]
        q = (rng.randint(0, 9), rng.randint(0, 9))
        d = sorted(((abs(p[0] - q[0]) + abs(p[1] - q[1]), lab) for p, lab in pts))
        if len({x for x, _ in d}) == len(d) and d[2][0] != d[3][0]:
            break
    k3 = [lab for _, lab in d[:3]]
    ans = max(set(k3), key=k3.count)
    table = [{"name": "Обучающая выборка", "columns": ["x", "y", "класс"], "rows": [[p[0], p[1], lab] for p, lab in pts]}]
    return single(f"Метрика — манхэттенское расстояние, k = 3, голосование большинством. Какой класс получит точка {q}?",
                  f"Класс {ans}", [f"Класс {'B' if ans == 'A' else 'A'}", "Ничья, класс не определён", "Зависит от порядка точек"], tables=table)


@template("ml.bias_variance", "Переобучение, смещение и разброс", "ml_theory", ML, 2, "multi", time_limit=150, method="pool")
def ml_bias_variance(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Большой разрыв между качеством на обучении и валидации — признак переобучения",
        "L2-регуляризация штрафует большие веса и уменьшает разброс модели",
        "L1-регуляризация может обнулять веса и выполнять отбор признаков",
        "Увеличение объёма обучающих данных обычно снижает переобучение",
        "Слишком простая модель имеет высокое смещение (недообучение)",
        "Early stopping — способ регуляризации нейросетей",
    ]
    false_pool = [
        "Высокое качество на обучающей выборке гарантирует высокое качество на новых данных",
        "Регуляризация всегда увеличивает разброс модели",
        "Увеличение глубины решающего дерева снижает риск переобучения",
        "L2-регуляризация зануляет большинство весов",
        "Недообученная модель хорошо работает на обучении, но плохо на тесте",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


@template("ml.validation", "Валидация моделей и утечки данных", "ml_theory", ML, 3, "multi", time_limit=180, method="pool")
def ml_validation(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Для временных рядов кросс-валидацию делают с разбиением по времени, а не случайно",
        "Масштабирование признаков нужно обучать только на обучающей части фолда",
        "Признак, рассчитанный с использованием будущих данных, приводит к утечке",
        "Стратифицированное разбиение сохраняет пропорции классов в фолдах",
        "Подбор гиперпараметров по тестовой выборке завышает оценку качества",
        "Если в данных несколько записей одного пользователя, разбивать нужно по пользователям (group k-fold)",
    ]
    false_pool = [
        "Нормализацию можно обучать на всём датасете до разбиения — это не влияет на оценку",
        "Случайное перемешивание временного ряда перед кросс-валидацией повышает надёжность оценки",
        "Accuracy — надёжная метрика при сильном дисбалансе классов",
        "Чем больше фолдов в кросс-валидации, тем меньше вычислительная стоимость",
        "Тестовую выборку стоит использовать для ранней остановки",
    ]
    return statements_multi(rng, ["Какие утверждения о валидации моделей верны?"], true_pool, false_pool)


METRIC_SCENARIOS = [
    (["Антифрод: мошеннических транзакций 0.1%, важно находить как можно больше мошенников при приемлемой точности.",
      "Сильный дисбаланс классов, интересует качество на редком положительном классе."], "PR-AUC"),
    (["Ранжирование поисковой выдачи с градацией релевантности документов.", "Качество порядка рекомендаций в топе списка с учётом позиций."], "nDCG@k"),
    (["Регрессия цены квартир, в данных много выбросов, нужна устойчивая метрика.", "Прогноз спроса, где крупные ошибки не должны доминировать."], "MAE"),
    (["Нужна оценка качества вероятностей классификатора, а не только порядка.", "Важно, чтобы предсказанные вероятности были откалиброваны."], "Log-loss"),
    (["Сравнение моделей ранжирования объектов по вероятности без выбора порога.", "Качество разделения классов при всех порогах сразу (умеренный дисбаланс)."], "ROC-AUC"),
]


@template("ml.metric_choice", "Выбор метрики под задачу", "ml_theory", ML, 2, "single", time_limit=120, method="pool")
def ml_metric_choice(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, METRIC_SCENARIOS, [a for _, a in METRIC_SCENARIOS] + ["Accuracy", "R²"], prefix="Какая метрика подходит лучше? ")


@template("ml.ensembles", "Ансамбли и бустинг", "ml_theory", ML, 3, "multi", time_limit=180, method="pool")
def ml_ensembles(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Случайный лес уменьшает разброс за счёт усреднения деревьев на бутстрэп-выборках",
        "Градиентный бустинг строит деревья последовательно, исправляя ошибки предыдущих",
        "Уменьшение learning rate в бустинге обычно требует большего числа деревьев",
        "CatBoost умеет работать с категориальными признаками без ручного one-hot",
        "В случайном лесу признаки для разбиения выбираются из случайного подмножества",
    ]
    false_pool = [
        "Бустинг строит деревья полностью независимо друг от друга",
        "Случайный лес нельзя переобучить ни при каких параметрах",
        "Увеличение числа деревьев в бустинге никогда не приводит к переобучению",
        "Бэггинг уменьшает смещение, но увеличивает разброс",
    ]
    return statements_multi(rng, ["Какие утверждения об ансамблях верны?"], true_pool, false_pool)


@template("ml.deep_learning", "Глубокое обучение", "ml_theory", ML, 4, "multi", time_limit=210, method="pool")
def ml_deep(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Self-attention в трансформере имеет квадратичную сложность по длине последовательности",
        "Dropout отключается на этапе инференса",
        "Batch normalization на инференсе использует накопленные скользящие статистики",
        "Residual-связи облегчают обучение очень глубоких сетей",
        "Adam адаптирует шаг обучения для каждого параметра по моментам градиента",
        "Затухание градиентов особенно характерно для глубоких сетей с сигмоидальными активациями",
    ]
    false_pool = [
        "Dropout на инференсе применяется с той же вероятностью, что и при обучении",
        "Увеличение batch size всегда улучшает обобщающую способность",
        "Функция активации ReLU страдает от затухания градиента сильнее, чем сигмоида",
        "Трансформеры обрабатывают токены строго последовательно, как RNN",
        "Batch normalization на инференсе пересчитывает статистики по текущему батчу",
    ]
    return statements_multi(rng, ["Какие утверждения о глубоком обучении верны?"], true_pool, false_pool)


# ================================================================== статистика
@template("stats.descriptive", "Описательная статистика", "statistics", STAT, 1, "input", time_limit=150)
def stats_descriptive(rng: random.Random, ctx: GenCtx) -> Variant:
    xs = [rng.randint(1, 30) for _ in range(rng.choice([7, 8, 9]))]
    stat = rng.choice(["среднее", "медиану"])
    if stat == "среднее":
        val = sum(xs) / len(xs)
    else:
        s = sorted(xs)
        m = len(s) // 2
        val = s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2
    return Variant(text=f"Выборка: {', '.join(map(str, xs))}. Найдите {stat} (до сотых).", kind="input", input_type="number", answer=_r2(val),
                   tolerance=0.011)


def _percentile_variant(rng: random.Random, unit="мс"):
    xs = [rng.randint(20, 400) for _ in range(20)]
    p = rng.choice([50, 90, 95])
    s = sorted(xs)
    rank = math.ceil(p / 100 * len(s))
    return Variant(
        text=f"Время ответа 20 запросов ({unit}): {', '.join(map(str, xs))}. Найдите p{p} методом ближайшего ранга "
        f"(значение с порядковым номером ⌈{p}/100 · n⌉ в отсортированном ряду).",
        kind="input",
        input_type="number",
        answer=s[rank - 1],
    )


@template("stats.percentile", "Перцентили", "statistics", STAT, 2, "input", time_limit=180)
def stats_percentile(rng: random.Random, ctx: GenCtx) -> Variant:
    return _percentile_variant(rng)


@template("sre.percentile", "Перцентили задержек (SLI)", "sre", ("devops",), 2, "input", time_limit=180)
def sre_percentile(rng: random.Random, ctx: GenCtx) -> Variant:
    return _percentile_variant(rng)


@template("perf.percentile", "Перцентили времени отклика", "performance", ("qa",), 2, "input", time_limit=180)
def perf_percentile(rng: random.Random, ctx: GenCtx) -> Variant:
    return _percentile_variant(rng)


@template("stats.ab_test", "A/B-тест: z-тест для долей", "statistics", STAT, 3, "single", time_limit=240)
def stats_ab(rng: random.Random, ctx: GenCtx) -> Variant:
    n1, n2 = rng.randrange(2000, 6000, 500), rng.randrange(2000, 6000, 500)
    p1 = rng.uniform(0.04, 0.12)
    lift = rng.choice([0.0, 0.1, 0.2, 0.35])
    c1, c2 = round(n1 * p1), round(n2 * p1 * (1 + lift) + rng.randint(-8, 8))
    pp = (c1 + c2) / (n1 + n2)
    se = math.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2))
    z = (c2 / n2 - c1 / n1) / se
    sig = abs(z) > 1.96
    ans = f"Различие статистически значимо (|z| ≈ {abs(z):.2f} > 1.96)" if sig else f"Различие незначимо (|z| ≈ {abs(z):.2f} ≤ 1.96)"
    wrong_z = abs(z) * rng.choice([0.5, 1.7]) + 0.3
    d = [
        f"Различие статистически значимо (|z| ≈ {wrong_z:.2f} > 1.96)" if not sig else f"Различие незначимо (|z| ≈ {wrong_z:.2f} ≤ 1.96)",
        "Сравнивать нельзя: выборки разного размера",
        "Значимость определяется только разницей конверсий больше 1 п.п.",
    ]
    table = [{"name": "Результаты", "columns": ["Группа", "Пользователей", "Конверсий"], "rows": [["A", n1, c1], ["B", n2, c2]]}]
    return single("Двусторонний z-тест для разности долей с объединённой оценкой дисперсии, α = 0.05. Какой вывод верен?", ans, d,
                  tables=table)


@template("stats.ci_mean", "Доверительный интервал среднего", "statistics", STAT, 3, "input", time_limit=180)
def stats_ci(rng: random.Random, ctx: GenCtx) -> Variant:
    mean, sd, n = rng.randint(100, 500), rng.randint(20, 80), rng.choice([64, 100, 144, 400])
    lower = rng.random() < 0.5
    half = 1.96 * sd / math.sqrt(n)
    val = mean - half if lower else mean + half
    return Variant(text=f"Среднее чека по выборке n = {n} равно {mean} ₽, стандартное отклонение {sd} ₽. Найдите {'нижнюю' if lower else 'верхнюю'} "
                   "границу 95% доверительного интервала для среднего (z = 1.96, до сотых).",
                   kind="input", input_type="number", answer=_r2(val), tolerance=0.02)


@template("stats.bayes", "Формула Байеса", "statistics", STAT, 3, "input", time_limit=210)
def stats_bayes(rng: random.Random, ctx: GenCtx) -> Variant:
    prev = rng.choice([0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.1, 0.15])
    sens = rng.choice([0.8, 0.85, 0.9, 0.92, 0.95, 0.97, 0.99])
    spec = rng.choice([0.85, 0.9, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995])
    post = sens * prev / (sens * prev + (1 - spec) * (1 - prev))
    ctxs = [("Антифрод-правило", "мошеннических операций", "честных", "операция с срабатыванием правила действительно мошенническая"),
            ("Медицинский тест", "больных", "здоровых", "человек с положительным тестом действительно болен"),
            ("Спам-фильтр", "спам-писем", "обычных писем", "письмо, помеченное фильтром, действительно спам")]
    name, pos, neg, q = rng.choice(ctxs)
    return Variant(text=f"{name} срабатывает на {sens * 100:g}% {pos} и ошибочно на {round((1 - spec) * 100, 1):g}% {neg}. "
                   f"Доля {pos} — {prev * 100:g}%. Какова вероятность, что {q}, в процентах (до десятых)?",
                   kind="input", input_type="number", answer=round(post * 100, 1), tolerance=0.11)


@template("stats.simpson", "Парадокс Симпсона", "statistics", STAT, 4, "single", time_limit=240)
def stats_simpson(rng: random.Random, ctx: GenCtx) -> Variant:
    # A лучше в каждом сегменте, но B лучше в сумме — из-за разного состава трафика в группах
    k = rng.choice([1, 2, 3])
    a, b = rng.choice([
        ([(81, 87), (192, 263)], [(234, 270), (55, 80)]),
        ([(19, 20), (60, 180)], [(160, 180), (5, 20)]),
    ])
    a = [(x * k, y * k) for x, y in a]
    b = [(x * k, y * k) for x, y in b]
    seg = rng.sample(["Мобильные", "Десктоп", "Новые", "Вернувшиеся"], 2)
    rows = [[seg[0], f"{a[0][0]}/{a[0][1]}", f"{b[0][0]}/{b[0][1]}"], [seg[1], f"{a[1][0]}/{a[1][1]}", f"{b[1][0]}/{b[1][1]}"]]
    swap = rng.random() < 0.5
    if swap:
        rows = [[r[0], r[2], r[1]] for r in rows]
    better_seg, better_total = ("B", "A") if swap else ("A", "B")
    ans = f"{better_seg} лучше в каждом сегменте, но {better_total} лучше в сумме — нужно учитывать различие состава групп"
    d = [f"{better_seg} лучше и в сегментах, и в сумме", f"{better_total} лучше и в сегментах, и в сумме", "Варианты не различаются"]
    table = [{"name": "Конверсии (успехи/попытки)", "columns": ["Сегмент", "A", "B"], "rows": rows}]
    return single("Посчитайте конверсии в сегментах и суммарно. Какой вывод верен?", ans, d, tables=table)


@template("stats.concepts", "Проверка гипотез", "statistics", STAT, 2, "multi", time_limit=150, method="pool")
def stats_concepts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "p-value — вероятность получить наблюдаемый или более экстремальный результат при верной нулевой гипотезе",
        "Ошибка I рода — отвергнуть верную нулевую гипотезу",
        "Мощность теста — вероятность обнаружить эффект, если он есть",
        "Корреляция не доказывает причинно-следственную связь",
        "Коэффициент Пирсона чувствителен к выбросам",
        "При множественных сравнениях растёт вероятность ложноположительного результата",
    ]
    false_pool = [
        "p-value — вероятность того, что нулевая гипотеза верна",
        "Ошибка II рода — отвергнуть верную нулевую гипотезу",
        "Незначимый результат доказывает отсутствие эффекта",
        "Коэффициент Спирмена применим только к нормально распределённым данным",
        "Увеличение размера выборки увеличивает вероятность ошибки I рода",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


@template("stats.ab_design", "Дизайн A/B-экспериментов", "statistics", STAT, 4, "multi", time_limit=210, method="pool")
def stats_ab_design(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Многократное подглядывание в результаты с остановкой при p < 0.05 завышает долю ложноположительных выводов",
        "Sample Ratio Mismatch (расхождение долей групп с запланированными) — сигнал о проблеме в сплитовании",
        "Минимально детектируемый эффект (MDE) уменьшается при росте размера выборки",
        "Эффект новизны может завысить результат в первые дни эксперимента",
        "CUPED снижает дисперсию метрики, используя данные до эксперимента",
        "Поправка Бонферрони контролирует FWER при множественных сравнениях",
    ]
    false_pool = [
        "Эксперимент нужно останавливать сразу, как только p-value стало ниже 0.05",
        "Расхождение размеров групп 45/55 при сплите 50/50 и миллионе пользователей — нормально",
        "Увеличение выборки увеличивает MDE",
        "Для метрик-отношений (например, CTR) всегда корректен обычный t-тест по пользователям без поправок",
        "Чем больше метрик проверяем, тем ниже вероятность хотя бы одного ложного срабатывания",
    ]
    return statements_multi(rng, ["Какие утверждения о дизайне экспериментов верны?"], true_pool, false_pool)


# ================================================================== продуктовые метрики
@template("product.retention", "Retention по когорте", "product_metrics", DA, 2, "input", time_limit=150)
def product_retention(rng: random.Random, ctx: GenCtx) -> Variant:
    n = rng.randrange(800, 5000, 100)
    d1 = round(n * rng.uniform(0.3, 0.55))
    d7 = round(d1 * rng.uniform(0.35, 0.6))
    d30 = round(d7 * rng.uniform(0.4, 0.7))
    day = rng.choice([7, 30])
    val = (d7 if day == 7 else d30) / n * 100
    table = [{"name": "Когорта установок 1 марта", "columns": ["День 0", "День 1", "День 7", "День 30"], "rows": [[n, d1, d7, d30]]}]
    return Variant(text=f"Вычислите retention дня {day} (классический, в %, до десятых).", kind="input", input_type="number",
                   answer=round(val, 1), tolerance=0.11, tables=table)


@template("product.funnel", "Конверсия воронки", "product_metrics", DA, 2, "input", time_limit=150)
def product_funnel(rng: random.Random, ctx: GenCtx) -> Variant:
    steps = ["Визит", "Карточка товара", "Корзина", "Оформление", "Оплата"]
    v = [rng.randrange(10000, 50000, 1000)]
    for _ in range(4):
        v.append(round(v[-1] * rng.uniform(0.25, 0.7)))
    a, b = sorted(rng.sample(range(5), 2))
    val = v[b] / v[a] * 100
    table = [{"name": "Воронка", "columns": steps, "rows": [v]}]
    return Variant(text=f"Какова конверсия из шага «{steps[a]}» в шаг «{steps[b]}» в % (до десятых)?", kind="input", input_type="number",
                   answer=round(val, 1), tolerance=0.11, tables=table)


@template("product.unit_economics", "ARPU, ARPPU, LTV", "product_metrics", DA, 3, "input", time_limit=210)
def product_unit(rng: random.Random, ctx: GenCtx) -> Variant:
    users = rng.randrange(10000, 50000, 1000)
    paying_share = rng.choice([0.02, 0.04, 0.05, 0.08, 0.1])
    payers = round(users * paying_share)
    revenue = payers * rng.randrange(300, 2000, 50)
    metric = rng.choice(["ARPU", "ARPPU", "LTV"])
    if metric == "ARPU":
        val = revenue / users
        q = "Найдите ARPU за месяц, ₽ (до сотых)."
    elif metric == "ARPPU":
        val = revenue / payers
        q = "Найдите ARPPU за месяц, ₽ (до сотых)."
    else:
        churn = rng.choice([0.1, 0.2, 0.25])
        val = revenue / users / churn
        q = f"Месячный отток пользователей — {int(churn * 100)}% и постоянен. Оцените LTV пользователя как ARPU / churn, ₽ (до сотых)."
    table = [{"name": "Данные за месяц", "columns": ["Активных пользователей", "Платящих", "Выручка, ₽"], "rows": [[users, payers, revenue]]}]
    return Variant(text=q, kind="input", input_type="number", answer=_r2(val), tolerance=0.02, tables=table)


@template("product.stickiness", "DAU/MAU", "product_metrics", DA, 2, "input", time_limit=120)
def product_sticky(rng: random.Random, ctx: GenCtx) -> Variant:
    mau = rng.randrange(20000, 200000, 1000)
    dau = round(mau * rng.uniform(0.08, 0.45))
    return Variant(text=f"MAU = {mau}, средний DAU = {dau}. Вычислите stickiness (DAU/MAU) в % (до десятых).", kind="input",
                   input_type="number", answer=round(dau / mau * 100, 1), tolerance=0.11)


PRODUCT_QA = [
    (["Как называется доля пользователей, вернувшихся в продукт через N дней после первого входа?"], "Retention"),
    (["Как называется доля пользователей, переставших пользоваться продуктом за период?"], "Churn rate"),
    (["Как называется прогноз суммарной выручки от одного пользователя за всё время жизни?"], "LTV"),
    (["Как называется стоимость привлечения одного клиента?"], "CAC"),
    (["Как называется главная метрика, отражающая ценность продукта для пользователей и бизнеса?"], "North Star Metric"),
]


@template("product.concepts", "Продуктовые метрики: определения", "product_metrics", DA, 1, "single", time_limit=90, method="pool")
def product_concepts(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, PRODUCT_QA, [a for _, a in PRODUCT_QA] + ["ARPPU", "MAU"])


CHART_SCENARIOS = [
    (["Показать динамику выручки по дням за квартал.", "Как менялось число активных пользователей по неделям?"], "Линейный график"),
    (["Сравнить выручку пяти регионов.", "Сопоставить число заказов по категориям товаров."], "Столбчатая диаграмма"),
    (["Показать распределение времени ответа сервиса.", "Как распределены суммы чеков покупателей?"], "Гистограмма"),
    (["Проверить связь между ценой и количеством продаж.", "Есть ли зависимость между возрастом и средним чеком?"], "Диаграмма рассеяния"),
    (["Сравнить медианы и разброс зарплат в нескольких отделах с выбросами.", "Показать квартильный разброс времени доставки по городам."], "Ящик с усами (boxplot)"),
    (["Показать активность пользователей по дням недели и часам суток.", "Нагрузка на сервис по часам и дням — где пики?"], "Тепловая карта"),
]


@template("viz.chart_choice", "Выбор типа визуализации", "visualization", DA, 1, "single", time_limit=90, method="pool")
def viz_chart(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, CHART_SCENARIOS, [a for _, a in CHART_SCENARIOS] + ["Круговая диаграмма"], prefix="Какой график подойдёт лучше? ")


@template("viz.facts", "Принципы визуализации и BI", "visualization", DA, 2, "multi", time_limit=150, method="pool")
def viz_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Ось Y у столбчатой диаграммы должна начинаться с нуля, иначе различия искажаются",
        "Круговая диаграмма плохо подходит для сравнения многих близких по величине категорий",
        "Для категориальных данных лучше использовать качественную палитру, а для величин — последовательную",
        "Дашборд должен отвечать на конкретные вопросы своей аудитории",
        "Две оси Y на одном графике легко вводят в заблуждение",
    ]
    false_pool = [
        "3D-эффекты улучшают точность восприятия значений",
        "Чем больше графиков на дашборде, тем он полезнее",
        "Для временных рядов лучше всего подходит круговая диаграмма",
        "Цвет должен быть единственным способом кодирования важной информации",
    ]
    return statements_multi(rng, ["Какие утверждения о визуализации верны?"], true_pool, false_pool)


# ================================================================== Python для данных (pandas)
@template("py.pandas", "pandas: группировка и фильтрация", "lang", ("ml", "data_analyst"), 2, "input", langs=("python",), time_limit=180)
def py_pandas(rng: random.Random, ctx: GenCtx) -> Variant:
    n = rng.randint(6, 8)
    cities = ["msk", "spb", "kzn"]
    rows = [(rng.choice(cities), rng.randrange(100, 1000, 50), rng.choice([0, 1])) for _ in range(n)]
    form = rng.choice(["groupby_sum", "filter_len", "groupby_mean"])
    data = f"df = pd.DataFrame({{\n    'city': {[r[0] for r in rows]},\n    'amount': {[r[1] for r in rows]},\n    'paid': {[r[2] for r in rows]},\n}})"
    city = rng.choice([r[0] for r in rows])
    if form == "groupby_sum":
        code = data + f"\nres = df[df.paid == 1].groupby('city')['amount'].sum()\nprint(res.get('{city}', 0))"
        ans = sum(r[1] for r in rows if r[2] == 1 and r[0] == city)
    elif form == "filter_len":
        t = rng.randrange(300, 800, 50)
        code = data + f"\nprint(len(df[(df.amount > {t}) | (df.city == '{city}')]))"
        ans = sum(1 for r in rows if r[1] > t or r[0] == city)
    else:
        code = data + f"\nprint(round(df.groupby('city')['amount'].mean()['{city}'], 2))"
        vals = [r[1] for r in rows if r[0] == city]
        ans = round(sum(vals) / len(vals), 2)
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, tolerance=0.011, code=code, code_lang="python")
