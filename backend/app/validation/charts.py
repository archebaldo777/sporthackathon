"""Графики результатов валидации (PNG) для документации и презентации. Требует matplotlib (dev-зависимость)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BRAND, RED, GREY, INK = "#402FFF", "#EC1D35", "#B8B8C7", "#14141A"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#8a8a99", "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})


def _save(fig, out: Path, name: str):
    fig.tight_layout()
    fig.savefig(out / name, dpi=180)
    plt.close(fig)


def render_all(r: dict, out: Path) -> None:
    m = r["matching"]["summary"]
    names = {"keyword_resume_baseline": "Поиск по резюме\n(классика)", "self_declared_category": "Самоописанная\nкатегория",
             "ours_full": "Драфт\n(полная модель)", "ours_without_fsp": "Драфт\nбез ФСП", "ours_without_adjacent": "Драфт без\nсмежных категорий"}
    keys = [k for k in names if k in m]
    for metric, title in [("ndcg@10", "nDCG@10"), ("p@10", "Precision@10"), ("mrr", "MRR")]:
        fig, ax = plt.subplots(figsize=(8, 4))
        vals = [m[k][metric] for k in keys]
        colors = [BRAND if k == "ours_full" else (GREY if "baseline" in k or "declared" in k else "#8F86FF") for k in keys]
        bars = ax.bar([names[k] for k in keys], vals, color=colors, width=0.62)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.01, f"{v:.2f}", ha="center", fontsize=10)
        ax.set_ylim(0, 1)
        ax.set_title(f"Качество подбора: {title} (тестовый набор потребностей)", loc="left", fontsize=12)
        _save(fig, out, f"matching_{metric.replace('@', '_at_')}.png")

    t = r["testing"]
    conf = t["accuracy"]["confusion"]
    grades = ["intern", "junior", "middle", "senior"]
    labels = ["Стажёр", "Junior", "Middle", "Senior"]
    mat = [[conf[a][b] for b in grades] for a in grades]
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    ax.imshow(mat, cmap="Purples")
    for i in range(4):
        for j in range(4):
            ax.text(j, i, mat[i][j], ha="center", va="center", color="white" if mat[i][j] > max(map(max, mat)) * 0.5 else INK)
    ax.set_xticks(range(4), labels)
    ax.set_yticks(range(4), labels)
    ax.set_xlabel("Грейд по тесту")
    ax.set_ylabel("Истинный грейд")
    ax.set_title("Матрица ошибок категоризации", loc="left", fontsize=12)
    _save(fig, out, "testing_confusion.png")

    la = r["leak_attack"]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    modes = [("none", "Без утечки"), ("static", "Статичный банк,\nутекло 60% ответов"),
             ("parametric_reuse", "Генерация без\nпроверки свежести"), ("parametric", "Драфт: только\nсвежие варианты")]
    vals = [la[k]["pass_rate_middle"] for k, _ in modes]
    bars = ax.bar([n for _, n in modes], vals, color=[GREY, RED, "#F2A1AB", BRAND], width=0.55)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.0%}", ha="center")
    ax.set_ylim(0, 1)
    ax.set_title("Junior пытается подтвердить Middle с утёкшими ответами: доля «прошедших»", loc="left", fontsize=11)
    _save(fig, out, "testing_leak_attack.png")

    ex = r["exposure_ablation"]
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ks = [("max_info", "Максимум информации"), ("randomesque", "Драфт: randomesque + контроль")]
    vals = [ex[k]["max_exposure"] for k, _ in ks]
    ax.barh([n for _, n in ks], vals, color=[GREY, BRAND])
    for i, v in enumerate(vals):
        ax.text(v + 0.01, i, f"{v:.0%}", va="center")
    ax.set_xlim(0, 1.1)
    ax.set_title("Максимальная экспозиция семейства заданий", loc="left", fontsize=12)
    _save(fig, out, "testing_exposure.png")
