"""Ключи ответов сверяются исполнением: SQL — в SQLite, код — интерпретаторами, которые установлены
(Python всегда; JavaScript, Swift, Java, Go, PHP, Dart, Kotlin — если есть в PATH, иначе тест пропускается).
Все 9 языков сразу: python -m app.validation.code_exec --docker"""
import pytest

from app.testing.bank.code_trace import ALL_LANGS
from app.validation.code_exec import available_locally, code_cases, run_local, run_sql, sql_cases, wrap


def test_sql_answers_match_sqlite():
    cases = [run_sql(c) for c in sql_cases(seeds=15)]
    assert len({c.template for c in cases}) >= 12
    bad = [(c.template, c.seed, c.answers, c.result) for c in cases if not c.result["ok"]]
    assert not bad, bad


@pytest.mark.parametrize("lang", ALL_LANGS)
def test_code_answers_match_execution(lang):
    if not available_locally(lang):
        pytest.skip(f"{lang}: интерпретатор не установлен")
    cases = run_local(code_cases([lang], seeds=3))
    assert cases
    bad = [(c.template, c.seed, c.answers, c.result) for c in cases if not c.result["ok"]]
    assert not bad, bad


def test_wrappers_produce_complete_programs():
    """Фрагмент, показанный кандидату, превращается в программу без потери строк."""
    for lang in ALL_LANGS:
        for c in code_cases([lang], seeds=1):
            assert c.source.strip()
    java = wrap("java", "static int f(int x) {\n    return x;\n}\n\nSystem.out.println(f(2));")
    assert "public static void main" in java and "static int f" in java.split("public static void main")[0]
    go = wrap("go", 'x := 1\nfmt.Println(strings.Repeat("a", x))')
    assert '"strings"' in go and "func main()" in go
