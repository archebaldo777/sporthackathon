"""Проверка ключей ответов исполнением: генерируемые задания с кодом запускаются настоящими
интерпретаторами и компиляторами, а вывод сверяется с ответом, который вычислил генератор.

Задания на трассировку кода (9 языков) и SQL-задания с таблицами генерируются по зерну, ответ генератор
считает сам, моделируя семантику языка. Ошибка в такой модели — неверный ключ, а значит несправедливая
оценка кандидата. Поэтому каждый вариант можно исполнить:

  - SQL — во встроенном SQLite (всегда, без внешних программ);
  - Python, JavaScript, Swift, Java, Go, PHP, Dart, Kotlin, C# — интерпретатором из PATH, если он установлен
    (автотест tests/test_code_exec.py пропускает отсутствующие);
  - все 9 языков сразу — в официальных Docker-образах: python -m app.validation.code_exec --docker

Запуск: python -m app.validation.code_exec [--seeds 6] [--langs python,javascript] [--docker] [--out res.json]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

from app.testing.bank import all_templates
from app.testing.bank.base import GenCtx
from app.testing.bank.code_trace import ALL_LANGS

# Языки и способ запуска: файл программы, команда локально, Docker-образ и команда в нём.
KOTLINC = "https://github.com/JetBrains/kotlin/releases/download/v2.0.21/kotlin-compiler-2.0.21.zip"
RUNNERS: dict[str, dict] = {
    "python": {"file": "main.py", "local": [sys.executable, "main.py"], "image": "python:3.12.10-slim-bookworm", "cmd": "python main.py",
               "setup": "pip install -q --disable-pip-version-check --root-user-action=ignore pandas"},
    "javascript": {"file": "main.js", "local": ["node", "main.js"], "image": "node:20-alpine", "cmd": "node main.js"},
    "swift": {"file": "main.swift", "local": ["swift", "main.swift"], "image": "swift:5.10", "cmd": "swift main.swift"},
    "java": {"file": "Main.java", "local": ["java", "Main.java"], "image": "eclipse-temurin:21-jdk", "cmd": "java Main.java"},
    "go": {"file": "main.go", "local": ["go", "run", "main.go"], "image": "golang:1.23-alpine", "cmd": "go run main.go"},
    "php": {"file": "main.php", "local": ["php", "main.php"], "image": "php:8.3-cli-alpine", "cmd": "php main.php"},
    "dart": {"file": "main.dart", "local": ["dart", "run", "main.dart"], "image": "dart:stable", "cmd": "dart run main.dart"},
    "kotlin": {"file": "main.kts", "local": ["kotlinc", "-script", "main.kts"], "image": "eclipse-temurin:21-jdk",
               "cmd": "kotlinc -script main.kts",
               "setup": f"cd /opt && curl -sL -o k.zip {KOTLINC} && jar xf k.zip && chmod +x kotlinc/bin/* "
                        "&& export PATH=/opt/kotlinc/bin:$PATH && cd - >/dev/null"},
    # C# — через проект: dotnet run для отдельного файла есть только в .NET 10
    "csharp": {"file": "Program.cs", "local": None, "image": "mcr.microsoft.com/dotnet/sdk:8.0",
               "cmd": "cp Program.cs /proj/Program.cs && dotnet run --project /proj -v q",
               "setup": "export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1 && dotnet new console -o /proj >/dev/null "
                        "&& dotnet build /proj -v q >/dev/null"},
}
assert set(RUNNERS) == set(ALL_LANGS)

_DECL = re.compile(
    r"^(func |static |fun |function |data class |class |struct |record |enum |interface |abstract |sealed |object |@"
    r"|(int|void|String|bool|double|List<int>|Future<void>|Stream<int>)\s+\w+\s*\()"
)


@dataclass
class Case:
    template: str
    lang: str
    seed: int
    source: str  # программа, готовая к запуску
    answers: list
    tolerance: float = 0.0
    count_true: bool = False  # ответ — сколько раз выведено true
    result: dict = field(default_factory=dict)


def _split(code: str) -> tuple[list[str], list[str], list[str]]:
    """Делит фрагмент на импорты, объявления верхнего уровня (функции, типы) и тело программы."""
    imports, members, body, depth, inside = [], [], [], 0, False
    for ln in code.split("\n"):
        if not inside and re.match(r"^(import |using |package )", ln):
            imports.append(ln)
            continue
        if not inside and _DECL.match(ln):
            inside, depth = True, 0
        if inside:
            members.append(ln)
            depth += ln.count("{") - ln.count("}")
            if depth <= 0 and ("}" in ln or "{" not in ln and not ln.rstrip().endswith(("(", ","))):
                inside = False
        else:
            body.append(ln)
    return imports, members, body


def wrap(lang: str, code: str) -> str:
    """Фрагмент, показанный кандидату, — в компилируемую программу (как её дописал бы человек)."""
    if lang in ("python", "javascript", "swift", "kotlin"):
        return code if lang != "python" or "pd." not in code else "import pandas as pd\n" + code
    if lang == "php":
        return "<?php\n" + code
    imports, members, body = _split(code)
    has_main = any(re.search(r"\bmain\s*\(", m) for m in members)
    B, M, I = "\n".join(body), "\n".join(members), "\n".join(imports)
    if lang == "java":
        M = re.sub(r"^(class|record|interface|enum) ", r"static \1 ", M, flags=re.M)
        return ("import java.util.*;\nimport java.util.function.*;\nimport java.util.stream.*;\n" + I +
                f"\npublic class Main {{\n{M}\npublic static void main(String[] args) throws Exception {{\n{B}\n}}\n}}\n")
    if lang == "go":
        pkgs = ["fmt"] + [p for p in ("strings", "sort", "errors", "sync", "time", "strconv", "math") if p + "." in code]
        imp = "import (\n" + "\n".join(f'    "{p}"' for p in pkgs) + "\n)\n"
        return f"package main\n\n{imp}\n{M}\n" + ("" if has_main else f"func main() {{\n{B}\n}}\n")
    if lang == "dart":
        return f"{I}\n{M}\n" + ("" if has_main else f"void main() {{\n{B}\n}}\n")
    if lang == "csharp":
        # в программе с операторами верхнего уровня типы объявляются после операторов
        types = re.findall(r"^((?:public |sealed |abstract )*(?:struct|class|record|interface|enum) .*?(?:\n(?!\S).*?)*?(?:\n\}|\}$|;$))",
                           code, flags=re.M)
        rest = code
        for t in types:
            rest = rest.replace(t, "")
        return "using System;\nusing System.Collections.Generic;\nusing System.Linq;\n" + rest + "\n" + "\n".join(types) + "\n"
    raise ValueError(lang)


def code_cases(langs=ALL_LANGS, seeds: int = 6) -> list[Case]:
    """Варианты заданий «что выведет программа» с ответом-вводом по каждому языку."""
    out = []
    for t in all_templates():
        if t.competency != "lang" or not t.langs:
            continue
        for lang in langs:
            if lang not in t.langs:
                continue
            for seed in range(seeds):
                v = t.gen(random.Random(seed), GenCtx(lang=lang, spec="backend"))
                if not v.code or v.kind != "input":
                    break
                out.append(Case(t.id, lang, seed, wrap(lang, v.code), v.answer if isinstance(v.answer, list) else [v.answer],
                                v.tolerance, count_true="Сколько раз программа выведет `true`" in v.text))
    return out


def _norm(s) -> str:
    return " ".join(str(s).split()).lower()


def check_output(case: Case, rc: int, out: str, err: str = "") -> dict:
    got = _norm(out)
    if rc != 0:
        ok = False
    elif case.count_true:
        ok = got.split().count("true") == case.answers[0]
    elif isinstance(case.answers[0], (int, float)) and not isinstance(case.answers[0], bool):
        try:
            ok = abs(float(got) - float(case.answers[0])) <= max(case.tolerance, 1e-9)
        except ValueError:
            ok = False
    else:
        ok = any(_norm(a) == got for a in case.answers)
    return {"ok": ok, "rc": rc, "output": got[:200], "error": err[-400:] if rc else ""}


def available_locally(lang: str) -> bool:
    r = RUNNERS[lang]
    if not r["local"]:
        return False
    if lang == "python":
        return True
    if not shutil.which(r["local"][0]):
        return False
    if lang == "java":  # на macOS /usr/bin/java — заглушка без JDK
        return subprocess.run(["java", "-version"], capture_output=True).returncode == 0
    return True


def _has_module(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


def run_local(cases: list[Case], timeout: int = 60) -> list[Case]:
    """Исполняет локально; варианты, которым нужна неустановленная библиотека (pandas), отбрасываются."""
    cases[:] = [c for c in cases if "import pandas" not in c.source or _has_module("pandas")]
    with tempfile.TemporaryDirectory() as tmp:
        for i, c in enumerate(cases):
            d = os.path.join(tmp, str(i))
            os.makedirs(d)
            with open(os.path.join(d, RUNNERS[c.lang]["file"]), "w") as f:
                f.write(c.source)
            try:
                p = subprocess.run(RUNNERS[c.lang]["local"], cwd=d, capture_output=True, text=True, timeout=timeout)
                c.result = check_output(c, p.returncode, p.stdout, p.stderr)
            except subprocess.TimeoutExpired:
                c.result = {"ok": False, "rc": -1, "output": "", "error": "timeout"}
    return cases


def run_docker(cases: list[Case], timeout: int = 120) -> list[Case]:
    """Все программы языка — одним контейнером официального образа."""
    by_lang: dict[str, list[tuple[int, Case]]] = {}
    for i, c in enumerate(cases):
        by_lang.setdefault(c.lang, []).append((i, c))
    with tempfile.TemporaryDirectory(dir=os.path.expanduser("~")) as tmp:  # Docker Desktop монтирует домашнюю папку
        for lang, items in by_lang.items():
            r = RUNNERS[lang]
            for i, c in items:
                os.makedirs(os.path.join(tmp, lang, str(i)))
                with open(os.path.join(tmp, lang, str(i), r["file"]), "w") as f:
                    f.write(c.source)
            script = (r.get("setup", "true") + f" && for d in /w/{lang}/*/; do (cd $d && timeout {timeout} sh -c '{r['cmd']}' "
                      "> out.txt 2> err.txt; echo $? > rc.txt); done")
            subprocess.run(["docker", "run", "--rm", "-v", f"{tmp}:/w", r["image"], "sh", "-c", script], check=True)
            for i, c in items:
                d = os.path.join(tmp, lang, str(i))
                read = lambda n: open(os.path.join(d, n)).read() if os.path.exists(os.path.join(d, n)) else ""
                c.result = check_output(c, int(read("rc.txt").strip() or -1), read("out.txt"), read("err.txt"))
    return cases


# ------------------------------------------------------------------ SQL
@dataclass
class SqlCase:
    template: str
    seed: int
    text: str
    sql: str
    tables: list[dict]
    answers: list
    tolerance: float
    result: dict = field(default_factory=dict)


def sql_cases(seeds: int = 30) -> list[SqlCase]:
    out = []
    for t in all_templates():
        if t.competency == "lang":
            continue
        for seed in range(seeds):
            v = t.gen(random.Random(seed), GenCtx(lang="python", spec=t.specs[0]))
            if v.code_lang != "sql" or not v.tables or v.kind != "input":
                break
            out.append(SqlCase(t.id, seed, v.text, v.code, v.tables, v.answer if isinstance(v.answer, list) else [v.answer],
                               v.tolerance))
    return out


def run_sql(case: SqlCase) -> SqlCase:
    """Исполняет запрос в SQLite и извлекает значение, о котором спрашивает условие."""
    db = sqlite3.connect(":memory:")
    for t in case.tables:
        db.execute(f"CREATE TABLE {t['name']} ({', '.join(t['columns'])})")
        db.executemany(f"INSERT INTO {t['name']} VALUES ({', '.join('?' * len(t['columns']))})", t["rows"])
    cur = db.execute(case.sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    text = case.text
    if text.startswith("Сколько строк"):
        got = len(rows)
    elif m := re.search(r"значение (\w+) будет у сотрудника (\w+)", text):
        got = next(r[cols.index(m[1])] for r in rows if r[cols.index("name")] == m[2])
    elif m := re.search(r"значение (\w+) будет в строке с id = (\d+)", text):
        got = next(r[cols.index(m[1])] for r in rows if r[cols.index("id")] == int(m[2]))
    elif m := re.search(r"значение будет в колонке (\w+)", text):
        got = rows[0][cols.index(m[1])] if rows else 0
    else:
        got = rows[0][0] if rows else None
    exp = case.answers[0]
    if isinstance(exp, (int, float)):
        try:
            ok = abs(float(got) - float(exp)) <= max(case.tolerance, 0.005)
        except (TypeError, ValueError):
            ok = False
    else:
        ok = any(_norm(a) == _norm(got) for a in case.answers)
    case.result = {"ok": ok, "output": str(got)}
    return case


def summarize(cases: list, key=lambda c: c.lang) -> dict:
    by: dict[str, dict] = {}
    for c in cases:
        s = by.setdefault(key(c), {"total": 0, "ok": 0, "templates": set(), "failed": []})
        s["total"] += 1
        s["ok"] += c.result.get("ok", False)
        s["templates"].add(c.template)
        if not c.result.get("ok"):
            s["failed"].append({"template": c.template, "seed": c.seed, "expected": c.answers, **c.result})
    return {k: {**v, "templates": len(v["templates"])} for k, v in sorted(by.items())}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--langs", default=",".join(ALL_LANGS))
    ap.add_argument("--docker", action="store_true", help="исполнять в официальных Docker-образах")
    ap.add_argument("--out")
    a = ap.parse_args()
    langs = [x for x in a.langs.split(",") if x]
    if not a.docker:
        skipped = [x for x in langs if not available_locally(x)]
        langs = [x for x in langs if x not in skipped]
        if skipped:
            print("нет локально, пропущены:", ", ".join(skipped), "(запустите с --docker)")
    cases = code_cases(langs, a.seeds)
    (run_docker if a.docker else run_local)(cases)
    sql = [run_sql(c) for c in sql_cases(max(a.seeds, 30))]
    res = {"code": summarize(cases), "sql": summarize(sql, key=lambda c: "sqlite")["sqlite"], "seeds": a.seeds}
    for lang, s in res["code"].items():
        print(f"{lang:<11} {s['ok']:>4}/{s['total']:<4} вариантов, шаблонов {s['templates']}")
    print(f"{'SQL':<11} {res['sql']['ok']:>4}/{res['sql']['total']:<4} вариантов, шаблонов {res['sql']['templates']}")
    for lang, s in [*res["code"].items(), ("SQL", res["sql"])]:
        for f in s["failed"][:5]:
            print("  ✗", lang, f)
    if a.out:
        with open(a.out, "w") as f:
            json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    sys.exit(0 if all(s["ok"] == s["total"] for s in [*res["code"].values(), res["sql"]]) else 1)


if __name__ == "__main__":
    main()
