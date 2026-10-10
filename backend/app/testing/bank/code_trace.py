"""Компетенция «Язык программирования»: задания на трассировку кода.

Универсальные семейства (циклы, рекурсия, словари, целочисленное деление, ссылочная семантика, finally)
рендерятся в синтаксис языка кандидата — одна и та же когнитивная операция на 9 языках. Ответ вычисляется
с учётом семантики конкретного языка (например, -17 // 5 в Python = -4, а в Java -17 / 5 = -3).
Языкоспецифичные семейства проверяют известные «ловушки» (event loop в JS, Integer cache в Java, defer в Go...).
"""
from __future__ import annotations

import math
import random

from app.testing.bank.base import FUNC_NAMES, VAR_NAMES, GenCtx, Variant, pick_distractors, single, statements_multi, template

ALL_LANGS = ("python", "javascript", "java", "go", "csharp", "kotlin", "php", "swift", "dart")
LANG_SPECS = ("backend", "frontend", "mobile", "ml", "data_analyst", "devops", "qa")
SEMI = {"javascript", "java", "csharp", "php", "dart"}


class Emit:
    """Мини-эмиттер кода: одинаковая структура программы в синтаксисе разных языков."""

    def __init__(self, lang: str):
        self.lang = lang
        self.lines: list[str] = []
        self.depth = 0

    def v(self, name: str) -> str:
        return f"${name}" if self.lang == "php" else name

    def line(self, s: str = ""):
        self.lines.append(("    " * self.depth + s) if s else "")

    def stmt(self, s: str):
        self.line(s + (";" if self.lang in SEMI else ""))

    def open(self, header: str):
        self.line(header + (":" if self.lang == "python" else " {"))
        self.depth += 1

    def close(self):
        self.depth -= 1
        if self.lang != "python":
            self.line("}")

    def decl(self, name: str, expr: str):
        L, n = self.lang, self.v(name)
        if L == "python" or L == "php":
            self.stmt(f"{n} = {expr}")
        elif L == "javascript":
            self.stmt(f"let {n} = {expr}")
        elif L in ("java", "csharp"):
            self.stmt(f"int {n} = {expr}")
        elif L == "go":
            self.stmt(f"{n} := {expr}")
        else:  # kotlin, swift, dart
            self.stmt(f"var {n} = {expr}")

    def inc(self, name: str):
        n = self.v(name)
        self.stmt(f"{n} += 1" if self.lang in ("python", "swift") else f"{n}++")

    def add(self, name: str, expr: str):
        self.stmt(f"{self.v(name)} += {expr}")

    def ret(self, expr: str):
        self.stmt(f"return {expr}")

    def print(self, expr: str):
        L = self.lang
        fmt = {
            "python": "print({})",
            "javascript": "console.log({})",
            "java": "System.out.println({})",
            "go": "fmt.Println({})",
            "csharp": "Console.WriteLine({})",
            "kotlin": "println({})",
            "php": "echo {}",
            "swift": "print({})",
            "dart": "print({})",
        }[L]
        self.stmt(fmt.format(expr))

    def for_range(self, var: str, n: str):
        L, i = self.lang, self.v(var)
        header = {
            "python": f"for {var} in range({n})",
            "javascript": f"for (let {var} = 0; {var} < {n}; {var}++)",
            "java": f"for (int {var} = 0; {var} < {n}; {var}++)",
            "csharp": f"for (int {var} = 0; {var} < {n}; {var}++)",
            "go": f"for {var} := 0; {var} < {n}; {var}++",
            "kotlin": f"for ({var} in 0 until {n})",
            "php": f"for ({i} = 0; {i} < {n}; {i}++)",
            "swift": f"for {var} in 0..<{n}",
            "dart": f"for (var {var} = 0; {var} < {n}; {var}++)",
        }[L]
        self.open(header)

    def for_each(self, var: str, coll: str):
        L = self.lang
        header = {
            "python": f"for {var} in {coll}",
            "javascript": f"for (const {var} of {coll})",
            "java": f"for (int {var} : {coll})",
            "csharp": f"foreach (var {var} in {coll})",
            "go": f"for _, {var} := range {coll}",
            "kotlin": f"for ({var} in {coll})",
            "php": f"foreach (${coll} as ${var})",
            "swift": f"for {var} in {coll}",
            "dart": f"for (final {var} in {coll})",
        }[L]
        self.open(header)

    def if_(self, cond: str):
        L = self.lang
        if L == "python":
            self.open(f"if {cond}")
        elif L in ("go", "swift"):
            self.open(f"if {cond}")
        else:
            self.open(f"if ({cond})")

    def if_inline(self, cond: str, action: str):
        """if (cond) continue/break — однострочно."""
        L = self.lang
        if L == "python":
            self.line(f"if {cond}: {action}")
        elif L in ("go", "swift"):
            self.line(f"if {cond} {{ {action} }}")
        elif L == "kotlin":
            self.line(f"if ({cond}) {action}")
        else:
            self.line(f"if ({cond}) {action};")

    def func(self, name: str, params: list[tuple[str, str]], ret: str = "int"):
        L = self.lang
        tmap = {
            "java": {"int": "int", "list": "int[]"},
            "csharp": {"int": "int", "list": "int[]"},
            "go": {"int": "int", "list": "[]int"},
            "kotlin": {"int": "Int", "list": "List<Int>"},
            "php": {"int": "int", "list": "array"},
            "swift": {"int": "Int", "list": "[Int]"},
            "dart": {"int": "int", "list": "List<int>"},
        }
        if L == "python":
            header = f"def {name}({', '.join(p for p, _ in params)})"
        elif L == "javascript":
            header = f"function {name}({', '.join(p for p, _ in params)})"
        elif L == "java":
            header = f"static {tmap[L][ret]} {name}({', '.join(f'{tmap[L][t]} {p}' for p, t in params)})"
        elif L == "csharp":
            header = f"static {tmap[L][ret]} {cs_name(name)}({', '.join(f'{tmap[L][t]} {p}' for p, t in params)})"
        elif L == "go":
            header = f"func {name}({', '.join(f'{p} {tmap[L][t]}' for p, t in params)}) {tmap[L][ret]}"
        elif L == "kotlin":
            header = f"fun {name}({', '.join(f'{p}: {tmap[L][t]}' for p, t in params)}): {tmap[L][ret]}"
        elif L == "php":
            header = f"function {name}({', '.join(f'{tmap[L][t]} ${p}' for p, t in params)}): {tmap[L][ret]}"
        elif L == "swift":
            header = f"func {name}({', '.join(f'_ {p}: {tmap[L][t]}' for p, t in params)}) -> {tmap[L][ret]}"
        else:  # dart
            header = f"{tmap[L][ret]} {name}({', '.join(f'{tmap[L][t]} {p}' for p, t in params)})"
        self.open(header)

    def call(self, name: str, args: str) -> str:
        return f"{cs_name(name) if self.lang == 'csharp' else name}({args})"

    def list_lit(self, xs: list[int]) -> str:
        body = ", ".join(map(str, xs))
        return {
            "java": f"new int[]{{{body}}}",
            "go": f"[]int{{{body}}}",
            "csharp": f"new[] {{ {body} }}",
            "kotlin": f"listOf({body})",
        }.get(self.lang, f"[{body}]")

    def text(self) -> str:
        return "\n".join(self.lines)


def cs_name(name: str) -> str:
    return name[:1].upper() + name[1:]


def lang_of(ctx: GenCtx) -> str:
    return ctx.lang if ctx.lang in ALL_LANGS else "python"


# ===================================================================== универсальные семейства
@template("trace.loop_filter_sum", "Цикл с условием", "lang", LANG_SPECS, 1, "input", langs=ALL_LANGS, time_limit=120)
def loop_filter_sum(rng: random.Random, ctx: GenCtx) -> Variant:
    L = lang_of(ctx)
    xs = [rng.randint(0, 30) for _ in range(rng.randint(6, 8))]
    m = rng.choice([2, 3, 4])
    r = rng.randrange(m)
    fn, var = rng.choice(FUNC_NAMES), rng.choice(VAR_NAMES)
    e = Emit(L)
    e.func(fn, [(var, "list")])
    e.decl("total", "0")
    e.for_each("x", var)
    e.if_(f"{e.v('x')} % {m} == {r}")
    e.add("total", e.v("x"))
    e.close()
    e.close()
    e.ret(e.v("total"))
    e.close()
    e.line()
    e.print(e.call(fn, e.list_lit(xs)))
    ans = sum(x for x in xs if x % m == r)
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=e.text(), code_lang=L)


@template("trace.nested_loops", "Вложенные циклы с break/continue", "lang", LANG_SPECS, 2, "input", langs=ALL_LANGS, time_limit=180)
def nested_loops(rng: random.Random, ctx: GenCtx) -> Variant:
    L = lang_of(ctx)
    n, m = rng.randint(3, 7), rng.randint(4, 8)
    k, d = rng.choice([2, 3, 4]), rng.randint(1, 3)
    use_eq = rng.random() < 0.5
    e = Emit(L)
    i, j = e.v("i"), e.v("j")
    e.decl("count", "0")
    e.for_range("i", str(n))
    e.for_range("j", str(m))
    cont = f"{j} == {i}" if use_eq else f"({i} + {j}) % {k} == 0"
    e.if_inline(cont, "continue")
    e.if_inline(f"{j} > {i} + {d}", "break")
    e.inc("count")
    e.close()
    e.close()
    e.print(e.v("count"))
    count = 0
    for ii in range(n):
        for jj in range(m):
            if (jj == ii) if use_eq else ((ii + jj) % k == 0):
                continue
            if jj > ii + d:
                break
            count += 1
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=count, code=e.text(), code_lang=L)


@template("trace.recursion", "Рекурсивная функция", "lang", LANG_SPECS, 2, "input", langs=ALL_LANGS, time_limit=180)
def recursion(rng: random.Random, ctx: GenCtx) -> Variant:
    L = lang_of(ctx)
    base_n, base_v = rng.randint(0, 2), rng.randint(1, 5)
    s, m = rng.choice([2, 3]), rng.choice([3, 4, 5])
    N = rng.randint(9, 16)
    fn = rng.choice(["f", "g", "h"])
    e = Emit(L)
    nv = e.v("n")
    e.func(fn, [("n", "int")])
    e.if_(f"{nv} <= {base_n}")
    e.ret(str(base_v))
    e.close()
    e.ret(f"{e.call(fn, f'{nv} - {s}')} + {nv} % {m}")
    e.close()
    e.line()
    e.print(e.call(fn, str(N)))

    def f(n):
        return base_v if n <= base_n else f(n - s) + n % m

    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=f(N), code=e.text(), code_lang=L)


WORDS = ["api", "db", "cache", "queue", "log", "auth", "test", "build"]


@template("trace.map_count", "Подсчёт частот в словаре", "lang", LANG_SPECS, 2, "input", langs=ALL_LANGS, time_limit=180)
def map_count(rng: random.Random, ctx: GenCtx) -> Variant:
    L = lang_of(ctx)
    vocab = rng.sample(WORDS, 4)
    words = [rng.choice(vocab) for _ in range(rng.randint(8, 10))]
    skip = rng.choice(vocab)
    ask = rng.choice([w for w in vocab if w != skip and w in words] or [vocab[0]])
    ans = sum(1 for w in words if w == ask and w != skip)
    lst = ", ".join(f'"{w}"' for w in words)
    lst_sq = ", ".join(f"'{w}'" for w in words)
    code = {
        "python": f'words = [{lst}]\ncounts = {{}}\nfor w in words:\n    if w == "{skip}":\n        continue\n    counts[w] = counts.get(w, 0) + 1\nprint(counts.get("{ask}", 0))',
        "javascript": f'const words = [{lst}];\nconst counts = new Map();\nfor (const w of words) {{\n    if (w === "{skip}") continue;\n    counts.set(w, (counts.get(w) ?? 0) + 1);\n}}\nconsole.log(counts.get("{ask}") ?? 0);',
        "java": f'String[] words = {{{lst}}};\nMap<String, Integer> counts = new HashMap<>();\nfor (String w : words) {{\n    if (w.equals("{skip}")) continue;\n    counts.merge(w, 1, Integer::sum);\n}}\nSystem.out.println(counts.getOrDefault("{ask}", 0));',
        "go": f'words := []string{{{lst}}}\ncounts := map[string]int{{}}\nfor _, w := range words {{\n    if w == "{skip}" {{\n        continue\n    }}\n    counts[w]++\n}}\nfmt.Println(counts["{ask}"])',
        "csharp": f'var words = new[] {{ {lst} }};\nvar counts = new Dictionary<string, int>();\nforeach (var w in words) {{\n    if (w == "{skip}") continue;\n    counts[w] = counts.GetValueOrDefault(w) + 1;\n}}\nConsole.WriteLine(counts.GetValueOrDefault("{ask}"));',
        "kotlin": f'val words = listOf({lst})\nval counts = mutableMapOf<String, Int>()\nfor (w in words) {{\n    if (w == "{skip}") continue\n    counts[w] = (counts[w] ?: 0) + 1\n}}\nprintln(counts["{ask}"] ?: 0)',
        "php": f'$words = [{lst}];\n$counts = [];\nforeach ($words as $w) {{\n    if ($w === "{skip}") continue;\n    $counts[$w] = ($counts[$w] ?? 0) + 1;\n}}\necho $counts["{ask}"] ?? 0;',
        "swift": f'let words = [{lst}]\nvar counts: [String: Int] = [:]\nfor w in words {{\n    if w == "{skip}" {{ continue }}\n    counts[w, default: 0] += 1\n}}\nprint(counts["{ask}", default: 0])',
        "dart": f"final words = [{lst_sq}];\nfinal counts = <String, int>{{}};\nfor (final w in words) {{\n  if (w == '{skip}') continue;\n  counts[w] = (counts[w] ?? 0) + 1;\n}}\nprint(counts['{ask}'] ?? 0);",
    }[L]
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang=L)


def _trunc_div(a: int, b: int) -> int:
    return int(a / b)


def _trunc_mod(a: int, b: int) -> int:
    return a - b * _trunc_div(a, b)


def _euclid_mod(a: int, b: int) -> int:
    return a - abs(b) * math.floor(a / abs(b))


@template("trace.int_div_mod", "Целочисленное деление отрицательных чисел", "lang", LANG_SPECS, 2, "input", langs=ALL_LANGS,
          time_limit=150, b_offset=0.35)
def int_div_mod(rng: random.Random, ctx: GenCtx) -> Variant:
    L = lang_of(ctx)
    a, b = rng.randint(11, 29), rng.choice([3, 4, 5, 6, 7])
    while a % b == 0:
        a += 1
    if rng.random() < 0.6:
        a = -a
    else:
        b = -b
    variant = rng.random() < 0.5
    if L == "python":
        code, q, r = f"a, b = {a}, {b}\nprint(a // b, a % b)", a // b, a % b
    elif L == "javascript":
        if variant:
            code, q, r = f"const a = {a}, b = {b};\nconsole.log(Math.floor(a / b), a % b);", math.floor(a / b), _trunc_mod(a, b)
        else:
            code, q, r = f"const a = {a}, b = {b};\nconsole.log(Math.trunc(a / b), a % b);", _trunc_div(a, b), _trunc_mod(a, b)
    elif L == "java":
        if variant:
            code, q, r = (f"int a = {a}, b = {b};\nSystem.out.println(Math.floorDiv(a, b) + \" \" + Math.floorMod(a, b));", a // b, a % b)
        else:
            code, q, r = f"int a = {a}, b = {b};\nSystem.out.println((a / b) + \" \" + (a % b));", _trunc_div(a, b), _trunc_mod(a, b)
    elif L == "go":
        code, q, r = f"a, b := {a}, {b}\nfmt.Println(a/b, a%b)", _trunc_div(a, b), _trunc_mod(a, b)
    elif L == "csharp":
        code, q, r = f'int a = {a}, b = {b};\nConsole.WriteLine($"{{a / b}} {{a % b}}");', _trunc_div(a, b), _trunc_mod(a, b)
    elif L == "kotlin":
        if variant:
            code, q, r = f'val a = {a}\nval b = {b}\nprintln("${{Math.floorDiv(a, b)}} ${{a.mod(b)}}")', a // b, a % b
        else:
            code, q, r = f'val a = {a}\nval b = {b}\nprintln("${{a / b}} ${{a % b}}")', _trunc_div(a, b), _trunc_mod(a, b)
    elif L == "php":
        code, q, r = f'$a = {a}; $b = {b};\necho intdiv($a, $b), " ", $a % $b;', _trunc_div(a, b), _trunc_mod(a, b)
    elif L == "swift":
        code, q, r = f"let a = {a}, b = {b}\nprint(a / b, a % b)", _trunc_div(a, b), _trunc_mod(a, b)
    else:  # dart: ~/ — усечение, % — евклидов остаток (всегда неотрицательный)
        code, q, r = f"final a = {a}, b = {b};\nprint('${{a ~/ b}} ${{a % b}}');", _trunc_div(a, b), _euclid_mod(a, b)
    return Variant(
        text="Что выведет программа? Введите два числа через пробел.",
        kind="input",
        input_type="text",
        answer=[f"{q} {r}"],
        code=code,
        code_lang=L,
    )


@template("trace.aliasing", "Ссылочная и значимая семантика коллекций", "lang", LANG_SPECS, 3, "input", langs=ALL_LANGS, time_limit=150)
def aliasing(rng: random.Random, ctx: GenCtx) -> Variant:
    L = lang_of(ctx)
    x, y, z, w = (rng.randint(1, 9) for _ in range(4))
    copy = rng.random() < 0.4
    go_array = L == "go" and rng.random() < 0.5
    if L == "python":
        assign = rng.choice(["a[:]", "list(a)", "a.copy()"]) if copy else "a"
        code = f"a = [{x}, {y}, {z}]\nb = {assign}\nb[0] = {w}\nprint(a[0] + b[0])"
        shared = not copy
    elif L == "javascript":
        assign = rng.choice(["[...a]", "a.slice()"]) if copy else "a"
        code = f"const a = [{x}, {y}, {z}];\nconst b = {assign};\nb[0] = {w};\nconsole.log(a[0] + b[0]);"
        shared = not copy
    elif L == "java":
        assign = "a.clone()" if copy else "a"
        code = f"int[] a = {{{x}, {y}, {z}}};\nint[] b = {assign};\nb[0] = {w};\nSystem.out.println(a[0] + b[0]);"
        shared = not copy
    elif L == "go":
        if go_array:
            code = f"a := [3]int{{{x}, {y}, {z}}}\nb := a\nb[0] = {w}\nfmt.Println(a[0] + b[0])"
            shared = False
        else:
            if copy:
                code = f"a := []int{{{x}, {y}, {z}}}\nb := make([]int, len(a))\ncopy(b, a)\nb[0] = {w}\nfmt.Println(a[0] + b[0])"
            else:
                code = f"a := []int{{{x}, {y}, {z}}}\nb := a\nb[0] = {w}\nfmt.Println(a[0] + b[0])"
            shared = not copy
    elif L == "csharp":
        assign = "(int[])a.Clone()" if copy else "a"
        code = f"int[] a = {{ {x}, {y}, {z} }};\nint[] b = {assign};\nb[0] = {w};\nConsole.WriteLine(a[0] + b[0]);"
        shared = not copy
    elif L == "kotlin":
        assign = "a.toMutableList()" if copy else "a"
        code = f"val a = mutableListOf({x}, {y}, {z})\nval b = {assign}\nb[0] = {w}\nprintln(a[0] + b[0])"
        shared = not copy
    elif L == "php":  # массивы копируются при присваивании, & — ссылка
        ref = rng.random() < 0.5
        code = f"$a = [{x}, {y}, {z}];\n$b = {'&' if ref else ''}$a;\n$b[0] = {w};\necho $a[0] + $b[0];"
        shared = ref
    elif L == "swift":  # Array — тип-значение (copy-on-write)
        code = f"var a = [{x}, {y}, {z}]\nvar b = a\nb[0] = {w}\nprint(a[0] + b[0])"
        shared = False
    else:  # dart
        assign = rng.choice(["List.of(a)", "[...a]"]) if copy else "a"
        code = f"final a = [{x}, {y}, {z}];\nfinal b = {assign};\nb[0] = {w};\nprint(a[0] + b[0]);"
        shared = not copy
    ans = (w if shared else x) + w
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang=L)


@template("trace.try_finally", "Порядок выполнения try/finally и return", "lang", LANG_SPECS, 3, "input",
          langs=("python", "javascript", "java", "csharp", "kotlin", "php", "dart"), time_limit=180)
def try_finally(rng: random.Random, ctx: GenCtx) -> Variant:
    L = lang_of(ctx)
    A, B, C, T = rng.randint(2, 5), rng.randint(5, 20), rng.choice([100, 1000]), rng.randint(3, 6)
    x1, x2 = T + rng.randint(1, 4), T - rng.randint(0, 2)
    code = {
        "python": f"def f(x):\n    r = x * {A}\n    try:\n        if x > {T}:\n            return r\n        r += {B}\n    finally:\n        r += {C}\n    return r\n\nprint(f({x1}) + f({x2}))",
        "javascript": f"function f(x) {{\n    let r = x * {A};\n    try {{\n        if (x > {T}) return r;\n        r += {B};\n    }} finally {{\n        r += {C};\n    }}\n    return r;\n}}\n\nconsole.log(f({x1}) + f({x2}));",
        "java": f"static int f(int x) {{\n    int r = x * {A};\n    try {{\n        if (x > {T}) return r;\n        r += {B};\n    }} finally {{\n        r += {C};\n    }}\n    return r;\n}}\n\nSystem.out.println(f({x1}) + f({x2}));",
        "csharp": f"static int F(int x) {{\n    int r = x * {A};\n    try {{\n        if (x > {T}) return r;\n        r += {B};\n    }} finally {{\n        r += {C};\n    }}\n    return r;\n}}\n\nConsole.WriteLine(F({x1}) + F({x2}));",
        "kotlin": f"fun f(x: Int): Int {{\n    var r = x * {A}\n    try {{\n        if (x > {T}) return r\n        r += {B}\n    }} finally {{\n        r += {C}\n    }}\n    return r\n}}\n\nprintln(f({x1}) + f({x2}))",
        "php": f"function f(int $x): int {{\n    $r = $x * {A};\n    try {{\n        if ($x > {T}) return $r;\n        $r += {B};\n    }} finally {{\n        $r += {C};\n    }}\n    return $r;\n}}\n\necho f({x1}) + f({x2});",
        "dart": f"int f(int x) {{\n  var r = x * {A};\n  try {{\n    if (x > {T}) return r;\n    r += {B};\n  }} finally {{\n    r += {C};\n  }}\n  return r;\n}}\n\nvoid main() => print(f({x1}) + f({x2}));",
    }[L]
    # return r внутри try фиксирует значение до выполнения finally
    ans = x1 * A + (x2 * A + B + C)
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang=L)


@template("trace.null_coalescing", "Работа с null/optional", "lang", LANG_SPECS, 2, "input",
          langs=("javascript", "csharp", "kotlin", "php", "swift", "dart"), time_limit=120)
def null_coalescing(rng: random.Random, ctx: GenCtx) -> Variant:
    L = lang_of(ctx)
    word = rng.choice(["kotlin", "swift", "draft", "build", "deploy", "commit", "merge"])
    k1, k2 = rng.randint(2, 9), rng.randint(10, 30)
    a_null = rng.random() < 0.5
    a_val = "null" if a_null else f'"{word}"'
    code = {
        "javascript": f"const a = {a_val};\nconst b = null;\nconsole.log((a?.length ?? {k1}) + (b?.length ?? {k2}));",
        "csharp": f"string? a = {a_val};\nstring? b = null;\nConsole.WriteLine((a?.Length ?? {k1}) + (b?.Length ?? {k2}));",
        "kotlin": f"val a: String? = {a_val}\nval b: String? = null\nprintln((a?.length ?: {k1}) + (b?.length ?: {k2}))",
        "php": f"$a = {a_val};\n$b = null;\necho strlen($a ?? str_repeat('x', {k1})) + strlen($b ?? str_repeat('x', {k2}));",
        "swift": f"let a: String? = {'nil' if a_null else chr(34) + word + chr(34)}\nlet b: String? = nil\nprint((a?.count ?? {k1}) + (b?.count ?? {k2}))",
        "dart": f"String? a = {a_val};\nString? b;\nprint((a?.length ?? {k1}) + (b?.length ?? {k2}));",
    }[L]
    ans = (k1 if a_null else len(word)) + k2
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang=L)


# ===================================================================== Python
@template("py.mutable_default", "Python: изменяемый аргумент по умолчанию", "lang", LANG_SPECS, 3, "input", langs=("python",), time_limit=150)
def py_mutable_default(rng: random.Random, ctx: GenCtx) -> Variant:
    fn = rng.choice(["add", "collect", "push", "remember"])
    calls, shared, out = [], 0, None
    n = rng.randint(3, 5)
    for idx in range(n):
        explicit = idx not in (0, n - 1) and rng.random() < 0.5
        x = rng.randint(1, 9)
        if explicit:
            calls.append(f"{fn}({x}, [])")
            res = 1
        else:
            shared += 1
            calls.append(f"{fn}({x})")
            res = shared
        out = res
    body = "\n".join(calls[:-1]) + f"\nprint({calls[-1]})"
    code = f"def {fn}(x, acc=[]):\n    acc.append(x)\n    return len(acc)\n\n{body}"
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=out, code=code, code_lang="python")


@template("py.slicing", "Python: срезы строк", "lang", LANG_SPECS, 2, "input", langs=("python",), time_limit=120)
def py_slicing(rng: random.Random, ctx: GenCtx) -> Variant:
    s = rng.choice(["programming", "federation", "algorithm", "hackathon", "verification", "candidate", "category"])
    forms = [(rng.randint(0, 3), rng.randint(5, len(s)), rng.choice([1, 2, 3])), (None, None, -1), (-rng.randint(3, 6), None, 1),
             (rng.randint(1, 4), -rng.randint(1, 3), rng.choice([1, 2]))]
    a, b, c = rng.choice(forms)
    expr = f"s[{'' if a is None else a}:{'' if b is None else b}{'' if c == 1 else f':{c}'}]"
    return Variant(text="Что выведет программа?", kind="input", input_type="text", answer=[s[slice(a, b, c)]],
                   code=f's = "{s}"\nprint({expr})', code_lang="python")


@template("py.comprehension", "Python: генераторы списков", "lang", LANG_SPECS, 2, "input", langs=("python",), time_limit=120)
def py_comprehension(rng: random.Random, ctx: GenCtx) -> Variant:
    a, b = rng.randint(0, 3), rng.randint(8, 13)
    m, r, k = rng.choice([2, 3]), 0, rng.randint(2, 4)
    r = rng.randrange(m)
    agg = rng.choice(["sum", "len", "max"])
    xs = [x * k for x in range(a, b) if x % m == r]
    ans = {"sum": sum(xs), "len": len(xs), "max": max(xs)}[agg]
    code = f"xs = [x * {k} for x in range({a}, {b}) if x % {m} == {r}]\nprint({agg}(xs))"
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang="python")


@template("py.late_binding", "Python: замыкания и позднее связывание", "lang", LANG_SPECS, 3, "input", langs=("python",), time_limit=150)
def py_late_binding(rng: random.Random, ctx: GenCtx) -> Variant:
    n, k = rng.randint(3, 6), rng.randint(2, 9)
    j = rng.randrange(n)
    default = rng.random() < 0.4
    lam = f"lambda i=i: i * {k}" if default else f"lambda: i * {k}"
    code = f"fs = [{lam} for i in range({n})]\nprint(fs[{j}]())"
    ans = j * k if default else (n - 1) * k
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang="python")


@template("py.class_attr", "Python: атрибуты класса и экземпляра", "lang", LANG_SPECS, 4, "input", langs=("python",), time_limit=180)
def py_class_attr(rng: random.Random, ctx: GenCtx) -> Variant:
    cls, meth, attr = rng.choice(["Bag", "Cart", "Box", "Queue", "Store"]), rng.choice(["add", "put", "push", "store"]), rng.choice(["items", "data", "buf"])
    rebind = rng.random() < 0.5
    init = rng.randint(0, 2)
    adds_a, adds_b = rng.randint(1, 5), rng.randint(1, 5)
    method = f"self.{attr} = self.{attr} + [x]" if rebind else f"self.{attr}.append(x)"
    calls = [f"a.{meth}({i})" for i in range(adds_a)] + [f"b.{meth}({i})" for i in range(adds_b)]
    rng.shuffle(calls)
    code = (f"class {cls}:\n    {attr} = {list(range(init))}\n\n    def {meth}(self, x):\n        {method}\n\n"
            "a, b = " + f"{cls}(), {cls}()\n" + "\n".join(calls) + f"\nprint(len(a.{attr}) + len({cls}.{attr}))")
    # при append общий список класса; при переприсваивании у экземпляра появляется свой атрибут
    ans = (init + adds_a + init) if rebind else (init + adds_a + adds_b) * 2
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang="python")


# ===================================================================== JavaScript / TypeScript
def _simulate_event_loop(parts):
    out, micro, macro = [], [], []
    for kind, payload in parts:
        if kind == "sync":
            out.append(payload)
        elif kind == "timeout":
            macro.append(payload)
        elif kind == "micro":
            micro.append(payload)
        elif kind == "async":
            out.append(payload[0])
            micro.append(("log", payload[1]))
        elif kind == "promise_ctor":
            out.append(payload[0])
            micro.append(("log", payload[1]))
    # payload для timeout/micro: ("log", x) | ("log_then_micro", x, y) | ("log_then_timeout", x, y)

    def run(task):
        if task[0] == "log":
            out.append(task[1])
        elif task[0] == "log_then_micro":
            out.append(task[1])
            micro.append(("log", task[2]))
        elif task[0] == "log_then_timeout":
            out.append(task[1])
            macro.append(("log", task[2]))

    def drain():
        while micro:
            run(micro.pop(0))

    drain()
    while macro:
        run(macro.pop(0))
        drain()
    return out


@template("js.event_loop", "JavaScript: event loop, микро- и макрозадачи", "lang", LANG_SPECS, 4, "input", langs=("javascript",),
          time_limit=240)
def js_event_loop(rng: random.Random, ctx: GenCtx) -> Variant:
    labels = iter(rng.sample(range(1, 10), 9))
    parts, lines = [], []
    kinds = ["sync", "timeout", "micro_then", "micro_q", "async", "timeout_nested", "promise_ctor", "micro_nested_timeout"]
    chosen = ["sync", "timeout", rng.choice(["micro_then", "micro_q"])] + rng.sample(kinds, 3)
    rng.shuffle(chosen)
    for k in chosen:
        if k == "sync":
            a = next(labels)
            parts.append(("sync", a))
            lines.append(f"console.log({a});")
        elif k == "timeout":
            a = next(labels)
            parts.append(("timeout", ("log", a)))
            lines.append(f"setTimeout(() => console.log({a}), 0);")
        elif k == "micro_then":
            a = next(labels)
            parts.append(("micro", ("log", a)))
            lines.append(f"Promise.resolve().then(() => console.log({a}));")
        elif k == "micro_q":
            a = next(labels)
            parts.append(("micro", ("log", a)))
            lines.append(f"queueMicrotask(() => console.log({a}));")
        elif k == "async":
            a, b = next(labels), next(labels)
            parts.append(("async", (a, b)))
            lines.append(f"(async () => {{\n  console.log({a});\n  await null;\n  console.log({b});\n}})();")
        elif k == "timeout_nested":
            a, b = next(labels), next(labels)
            parts.append(("timeout", ("log_then_micro", a, b)))
            lines.append(f"setTimeout(() => {{\n  console.log({a});\n  Promise.resolve().then(() => console.log({b}));\n}}, 0);")
        elif k == "promise_ctor":
            a, b = next(labels), next(labels)
            parts.append(("promise_ctor", (a, b)))
            lines.append(f"new Promise((resolve) => {{\n  console.log({a});\n  resolve();\n}}).then(() => console.log({b}));")
        elif k == "micro_nested_timeout":
            a, b = next(labels), next(labels)
            parts.append(("micro", ("log_then_timeout", a, b)))
            lines.append(f"Promise.resolve().then(() => {{\n  console.log({a});\n  setTimeout(() => console.log({b}), 0);\n}});")
    out = [str(x) for x in _simulate_event_loop(parts)]
    return Variant(
        text="В каком порядке будут выведены числа? Введите их через пробел.",
        kind="input",
        input_type="text",
        answer=[" ".join(out), "".join(out)],
        code="\n".join(lines),
        code_lang="javascript",
    )


@template("js.coercion", "JavaScript: приведение типов", "lang", LANG_SPECS, 2, "single", langs=("javascript",), time_limit=120)
def js_coercion(rng: random.Random, ctx: GenCtx) -> Variant:
    a, b, c = rng.randint(2, 9), rng.randint(1, 9), rng.randint(1, 9)
    forms = [
        (f'"{a}" + {b}', f'"{a}{b}"', [str(a + b), "NaN", f'"{b}{a}"']),
        (f'"{a}" - {b}', str(a - b), [f'"{a}-{b}"', "NaN", f'"{a}{b}"']),
        (f'"{a}" * "{b}"', str(a * b), [f'"{a}{b}"', "NaN", f'"{a}*{b}"']),
        (f"{a} + true", str(a + 1), [f'"{a}true"', "NaN", str(a)]),
        (f"{a} + null", str(a), ["NaN", f'"{a}null"', "null"]),
        (f"{a} + undefined", "NaN", [str(a), f'"{a}undefined"', "undefined"]),
        (f"[{a}] + [{b}]", f'"{a}{b}"', [str(a + b), f"[{a}, {b}]", "NaN"]),
        (f'"{a}" + {b} - {c}', str(int(f"{a}{b}") - c), [str(a + b - c), f'"{a}{b - c}"', "NaN"]),
        (f'{a} + {b} + "{c}"', f'"{a + b}{c}"', [f'"{a}{b}{c}"', str(a + b + c), "NaN"]),
    ]
    expr, ans, d = rng.choice(forms)
    return single(f"Чему равно выражение `{expr}`?", ans, d)


@template("js.closure_var_let", "JavaScript: var/let в замыканиях", "lang", LANG_SPECS, 3, "input", langs=("javascript",), time_limit=150)
def js_closure(rng: random.Random, ctx: GenCtx) -> Variant:
    n, k = rng.randint(3, 6), rng.randint(2, 9)
    j = rng.randrange(n)
    use_var = rng.random() < 0.55
    kw = "var" if use_var else "let"
    code = f"const fns = [];\nfor ({kw} i = 0; i < {n}; i++) {{\n  fns.push(() => i * {k});\n}}\nconsole.log(fns[{j}]());"
    ans = n * k if use_var else j * k
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang="javascript")


@template("js.array_chain", "JavaScript: map/filter/reduce", "lang", LANG_SPECS, 2, "input", langs=("javascript",), time_limit=150)
def js_array_chain(rng: random.Random, ctx: GenCtx) -> Variant:
    xs = [rng.randint(1, 12) for _ in range(rng.randint(5, 7))]
    k, t, init = rng.randint(2, 3), rng.randint(8, 20), rng.choice([0, 10])
    code = f"const xs = [{', '.join(map(str, xs))}];\nconst r = xs\n  .map((x) => x * {k})\n  .filter((x) => x > {t})\n  .reduce((acc, x) => acc + x, {init});\nconsole.log(r);"
    ans = init + sum(x * k for x in xs if x * k > t)
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang="javascript")


@template("ts.types", "TypeScript: система типов", "lang", LANG_SPECS, 3, "multi", langs=("javascript",), time_limit=180, method="pool")
def ts_types(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "TypeScript использует структурную типизацию: совместимость определяется формой объекта, а не именем типа",
        "Значение типа `unknown` нельзя использовать без сужения типа или приведения",
        "Тип `never` описывает значения, которые никогда не возникают, например результат функции, всегда бросающей исключение",
        "`as const` делает литералы неизменяемыми и сужает их до литеральных типов",
        "`Partial<T>` делает все поля типа T необязательными",
        "Проверка `typeof x === \"string\"` сужает тип объединения `string | number` до `string` внутри ветки",
        "Типы TypeScript стираются при компиляции и недоступны во время выполнения",
    ]
    false_pool = [
        "`any` и `unknown` полностью эквивалентны с точки зрения проверки типов",
        "TypeScript проверяет типы во время выполнения программы в браузере",
        "Интерфейс нельзя расширить другим интерфейсом",
        "`readonly` запрещает изменение свойства во время выполнения JavaScript-кода",
        "`Pick<T, K>` удаляет из типа T перечисленные ключи K",
        "Объект с лишними полями никогда не совместим с типом, где этих полей нет",
    ]
    return statements_multi(rng, ["Какие утверждения о TypeScript верны?"], true_pool, false_pool)


# ===================================================================== Java
@template("java.integer_cache", "Java: сравнение обёрток и строк", "lang", LANG_SPECS, 4, "input", langs=("java",), time_limit=210)
def java_integer_cache(rng: random.Random, ctx: GenCtx) -> Variant:
    lines, trues = [], 0
    small = rng.randint(-100, 120)
    big = rng.randint(200, 5000)
    checks = [
        (f"Integer a = {small}, b = {small};\nSystem.out.println(a == b);", True),
        (f"Integer c = {big}, d = {big};\nSystem.out.println(c == d);", False),
        (f"System.out.println(c.equals(d));", True),
        ('String s1 = "fsp", s2 = "fsp";\nSystem.out.println(s1 == s2);', True),
        ('String s3 = new String("fsp");\nSystem.out.println(s1 == s3);', False),
        ("System.out.println(s1.equals(s3));", True),
    ]
    chosen = checks[:3] if rng.random() < 0.5 else checks
    for code, val in chosen:
        lines.append(code)
        trues += val
    return Variant(
        text="Сколько раз программа выведет `true`? (стандартная JVM без изменения параметров кэша Integer)",
        kind="input",
        input_type="number",
        answer=trues,
        code="\n".join(lines),
        code_lang="java",
    )


# ===================================================================== Go
@template("go.defer", "Go: порядок defer и вычисление аргументов", "lang", LANG_SPECS, 3, "input", langs=("go",), time_limit=180)
def go_defer(rng: random.Random, ctx: GenCtx) -> Variant:
    n, k = rng.randint(2, 4), rng.randint(1, 3)
    x0, x1 = rng.randint(1, 4), rng.randint(5, 9)
    code = (
        f"func main() {{\n    x := {x0}\n    defer fmt.Print(x, \" \")\n    x = {x1}\n"
        f"    for i := 0; i < {n}; i++ {{\n        defer fmt.Print(i*{k}, \" \")\n    }}\n    fmt.Print(x, \" \")\n}}"
    )
    out = [x1] + [i * k for i in reversed(range(n))] + [x0]
    return Variant(
        text="Что выведет программа? Введите числа через пробел.",
        kind="input",
        input_type="text",
        answer=[" ".join(map(str, out))],
        code=code,
        code_lang="go",
    )


@template("go.slice_append", "Go: append и общий базовый массив", "lang", LANG_SPECS, 4, "input", langs=("go",), time_limit=210)
def go_slice_append(rng: random.Random, ctx: GenCtx) -> Variant:
    ln = rng.randint(2, 4)
    shared = rng.random() < 0.6
    cap = ln + rng.randint(1, 3) if shared else ln
    v1, v2 = rng.randint(10, 49), rng.randint(50, 99)
    code = f"a := make([]int, {ln}, {cap})\nb := append(a, {v1})\nc := append(a, {v2})\nfmt.Println(b[{ln}] + c[{ln}])"
    ans = (v2 + v2) if shared else (v1 + v2)
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang="go")


# ===================================================================== C#, Swift: значимые и ссылочные типы
@template("lang.value_vs_ref", "Значимые и ссылочные типы (struct/class)", "lang", LANG_SPECS, 3, "input", langs=("csharp", "swift"),
          time_limit=150)
def value_vs_ref(rng: random.Random, ctx: GenCtx) -> Variant:
    L = lang_of(ctx)
    is_struct = rng.random() < 0.5
    a, b = rng.randint(1, 9), rng.randint(10, 30)
    kw = "struct" if is_struct else "class"
    if L == "csharp":
        code = f"{kw} Point {{ public int X; }}\n\nvar p1 = new Point {{ X = {a} }};\nvar p2 = p1;\np2.X = {b};\nConsole.WriteLine(p1.X + p2.X);"
    else:
        init = "var x: Int\n    init(x: Int) { self.x = x }" if not is_struct else "var x: Int"
        code = f"{kw} Point {{\n    {init}\n}}\n\nvar p1 = Point(x: {a})\nvar p2 = p1\np2.x = {b}\nprint(p1.x + p2.x)"
    ans = (a + b) if is_struct else (b + b)
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang=L)


@template("csharp.closure_for", "C#: захват переменной цикла", "lang", LANG_SPECS, 3, "input", langs=("csharp",), time_limit=150)
def csharp_closure(rng: random.Random, ctx: GenCtx) -> Variant:
    n, k = rng.randint(3, 6), rng.randint(2, 9)
    j = rng.randrange(n)
    use_for = rng.random() < 0.55
    if use_for:
        loop = f"for (int i = 0; i < {n}; i++)\n    actions.Add(() => i * {k});"
        ans = n * k
    else:
        loop = f"foreach (var i in Enumerable.Range(0, {n}))\n    actions.Add(() => i * {k});"
        ans = j * k
    code = f"var actions = new List<Func<int>>();\n{loop}\nConsole.WriteLine(actions[{j}]());"
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang="csharp")


@template("php.closure_use", "PHP: захват переменных в замыкании", "lang", LANG_SPECS, 3, "input", langs=("php",), time_limit=150)
def php_closure(rng: random.Random, ctx: GenCtx) -> Variant:
    n, k = rng.randint(3, 6), rng.randint(2, 9)
    j = rng.randrange(n)
    by_ref = rng.random() < 0.5
    code = f"$fns = [];\nfor ($i = 0; $i < {n}; $i++) {{\n    $fns[] = function () use ({'&' if by_ref else ''}$i) {{ return $i * {k}; }};\n}}\necho $fns[{j}]();"
    ans = n * k if by_ref else j * k
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang="php")


@template("kotlin.data_copy", "Kotlin: data class и поверхностное копирование", "lang", LANG_SPECS, 4, "input", langs=("kotlin",),
          time_limit=180)
def kotlin_data_copy(rng: random.Random, ctx: GenCtx) -> Variant:
    a, b = rng.randint(1, 9), rng.randint(10, 20)
    x = rng.randint(21, 40)
    code = (
        f"data class Team(val size: Int, val scores: MutableList<Int>)\n\n"
        f"val t1 = Team({a}, mutableListOf({b}))\nval t2 = t1.copy(size = {a + 1})\nt2.scores.add({x})\n"
        f"println(t1.scores.size + t1.size + if (t1 == t2) 100 else 0)"
    )
    ans = 2 + a  # список общий (поверхностная копия), size различается → не равны
    return Variant(text="Что выведет программа?", kind="input", input_type="number", answer=ans, code=code, code_lang="kotlin")
