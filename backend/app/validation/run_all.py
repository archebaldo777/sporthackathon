"""Запуск полной процедуры валидации: python -m app.validation.run_all

Результаты: validation_results/report.json (отдаётся API /validation/report и страницей «Валидация»),
validation_results/report.md и графики PNG (для документации и презентации).
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from app.core.db import SessionLocal
from app.validation import matching_eval, resume_eval, testing_eval
from app.validation.external_eval import build_example, evaluate_external

OUT = Path(__file__).resolve().parents[2] / "validation_results"


def main(fast: bool = False) -> dict:
    t0 = time.time()
    OUT.mkdir(exist_ok=True)
    report: dict = {"generated_at": time.strftime("%Y-%m-%d %H:%M"), "fast": fast}
    print("1/7 точность и согласованность тестирования…")
    ev = testing_eval.evaluate(n=400 if fast else 1200)
    item_obs = ev.pop("item_observations")
    report["testing"] = ev
    print("2/7 уникальность вариантов…")
    report["variants"] = testing_eval.variant_uniqueness(n_seeds=60 if fast else 150)
    print("3/7 атака утечкой…")
    report["leak_attack"] = testing_eval.leak_attack(n_attackers=60 if fast else 150)
    report["integrity"] = testing_eval.integrity_eval(n_honest=300 if fast else 800, n_cheaters=120 if fast else 300)
    print("4/7 контроль экспозиции…")
    report["exposure_ablation"] = testing_eval.exposure_ablation(n=150 if fast else 400)
    print("5/7 CAT vs фиксированная форма, калибровка…")
    report["fixed_form"] = testing_eval.fixed_form_comparison(n=200 if fast else 500)
    report["calibration"] = testing_eval.calibration_recovery(item_obs)
    report["stop_rule_ablation"] = testing_eval.stop_rule_ablation(n=300 if fast else 1000)
    report["resume_parsing"] = resume_eval.evaluate_all()
    print("6/7 подбор…")
    with SessionLocal() as db:
        report["matching"] = matching_eval.evaluate(db)
        print("7/7 проверка на внешнем наборе пар (формат для жюри)…")
        ext = evaluate_external(build_example(db))
        report["external_example"] = {k: v for k, v in ext.items() if k != "per_vacancy"}
        # устойчивость: тот же расчёт на независимых выборках вакансий и кандидатов
        runs = [evaluate_external(build_example(db, seed=s))["summary"]["pool"] for s in (6, 7, 8, 9, 10)]
        report["external_example"]["seeds"] = {
            m: {k: {"mean": round(statistics.mean(r[m][k] for r in runs), 3), "sd": round(statistics.pstdev(r[m][k] for r in runs), 3)}
                for k in ("p@10", "ndcg@10", "mrr")} for m in ("ours", "keyword_baseline")}
    report["elapsed_s"] = round(time.time() - t0, 1)
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    try:
        from app.validation.charts import render_all

        render_all(report, OUT)
    except Exception as exc:  # noqa: BLE001 — графики опциональны (matplotlib — dev-зависимость)
        print("графики не построены:", exc)
    try:
        from app.validation.report_md import write_doc

        write_doc(report)
    except Exception as exc:  # noqa: BLE001
        print("раздел документации не обновлён:", exc)
    print(f"готово за {report['elapsed_s']} с → {OUT / 'report.json'}")
    return report


if __name__ == "__main__":
    import sys

    main(fast="--fast" in sys.argv)
