import { useQuery } from "@tanstack/react-query";
import { BarChart3, FileSearch, FlaskConical, Info, ShieldCheck, Target } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, Badge, Card, CardHeader, PageLoader, Stat } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import ExternalEval from "./ExternalEval";

const NAMES: Record<string, string> = { keyword_resume_baseline: "Поиск по резюме (классика)", self_declared_category: "Самоописанная категория", ours_full: "Драфт — полная модель",
  ours_without_fsp: "Драфт без ФСП", ours_without_adjacent: "Драфт без смежных категорий" };
const G = ["intern", "junior", "middle", "senior"];
const GN: Record<string, string> = { intern: "Стажёр", junior: "Junior", middle: "Middle", senior: "Senior" };
const pct = (v?: number) => (v == null ? "—" : `${Math.round(v * 100)}%`);

export default function Validation() {
  const { data: r, isLoading, error } = useQuery({ queryKey: ["validation"], queryFn: () => api("/validation/report", { auth: false }) });
  if (isLoading) return <PageLoader />;
  if (error || !r) return <div className="mx-auto max-w-3xl px-4 py-16"><Alert tone="warn">{(error as ApiError)?.message ?? "Отчёт не найден"}</Alert></div>;
  const t = r.testing, m = r.matching, la = r.leak_attack;
  const mrows = Object.entries(m.summary).map(([k, v]: any) => ({ name: NAMES[k] ?? k, key: k, ...v }));
  return (
    <div>
      <section className="bg-night text-white">
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
          <div className="kicker text-white/50">Процедура валидации · сформирован {r.generated_at}</div>
          <h1 className="mt-3 max-w-4xl text-[34px] font-extrabold leading-tight sm:text-[42px]">Проверяем тест и подбор на данных, где известна истина</h1>
          <p className="mt-4 max-w-3xl text-[15.5px] text-white/65">Эталонной разметки в задаче нет, поэтому мы строим синтетическую популяцию со скрытой «истиной» (истинная способность, истинный грейд, реальные навыки). Наблюдаемые данные зашумлены как в жизни: 25% кандидатов завышают грейд, 20% «набивают» резюме. Тест и подбор видят только наблюдаемое — сравнение с истиной честно показывает качество.</p>
        </div>
      </section>
      <div className="mx-auto max-w-7xl space-y-8 px-4 py-12 sm:px-6">
        <div>
          <div className="mb-4 flex items-center gap-2 text-[20px] font-bold"><Target className="h-6 w-6 text-brand-500" />Механика подбора</div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="nDCG@10" value={`${m.summary.ours_full["ndcg@10"].toFixed(2)}${m.spread_between_need_sets ? ` ± ${m.spread_between_need_sets.ours_full["ndcg@10_sd"].toFixed(2)}` : ""}`} hint={`классика: ${m.summary.keyword_resume_baseline["ndcg@10"].toFixed(2)} · лучше в ${pct(m.ours_beats_keyword_share)} запросов`} accent />
            <Stat label="Precision@10" value={m.summary.ours_full["p@10"].toFixed(2)} hint={`классика: ${m.summary.keyword_resume_baseline["p@10"].toFixed(2)}`} />
            <Stat label="MRR" value={m.summary.ours_full.mrr.toFixed(2)} hint="первый релевантный — почти всегда на 1-м месте" />
            <Stat label="ФСП в топ-10" value={pct(m.fsp_share_top10)} hint={`в базе: ${pct(m.fsp_share_pool)}`} />
          </div>
          <Card className="mt-5">
            <CardHeader title={`Сравнение на тестовом наборе: ${m.needs_evaluated} потребностей (${m.need_sets ?? 1} независимых наборов) × ${m.pool_size} кандидатов`} subtitle="Релевантность 0–3 по скрытой истине: специализация, истинный грейд, реальные навыки, условия. Precision@10 — доля релевантных (≥2) в топ-10." />
            <div className="grid gap-4 px-5 pb-5 lg:grid-cols-[1.2fr_1fr]">
              <div className="h-72">
                <ResponsiveContainer>
                  <BarChart data={mrows} margin={{ left: -16, right: 10 }}>
                    <CartesianGrid stroke="#EDEDF3" vertical={false} /><XAxis dataKey="name" tick={{ fontSize: 10.5 }} interval={0} height={56} /><YAxis domain={[0, 1]} tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v: any) => Number(v).toFixed(3)} />
                    <Bar dataKey="ndcg@10" name="nDCG@10" radius={[6, 6, 0, 0]}>{mrows.map((x) => <Cell key={x.key} fill={x.key === "ours_full" ? "#402FFF" : x.key.startsWith("ours") ? "#A497FF" : "#B8B8C7"} />)}</Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead><tr className="text-left text-ink-3"><th className="py-2 font-medium">Ранжирование</th><th className="font-medium">P@10</th><th className="font-medium">nDCG</th><th className="font-medium">MRR</th><th className="font-medium">R@30</th><th className="font-medium">шум</th></tr></thead>
                  <tbody>{mrows.map((x: any) => <tr key={x.key} className={"border-t border-line " + (x.key === "ours_full" ? "font-semibold text-brand-700" : "")}><td className="py-2 pr-2">{x.name}</td><td className="num">{x["p@10"].toFixed(2)}</td><td className="num">{x["ndcg@10"].toFixed(2)}</td><td className="num">{x.mrr.toFixed(2)}</td><td className="num">{x["recall@30"].toFixed(2)}</td><td className="num">{x["noise@10"].toFixed(2)}</td></tr>)}</tbody>
                </table>
                <p className="mt-3 text-[12.5px] text-ink-3">«Самоописанная категория» — та же формула, но грейд из анкеты и без тестовых доказательств: разница с полной моделью — вклад верифицированного профиля. «Шум» — доля полностью нерелевантных в топ-10.</p>
              </div>
            </div>
          </Card>
          <div className="mt-5"><ExternalEval /></div>
        </div>

        <div>
          <div className="mb-4 flex items-center gap-2 text-[20px] font-bold"><FlaskConical className="h-6 w-6 text-brand-500" />Механика тестирования (Монте-Карло, {t.population} виртуальных кандидатов)</div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Грейд по тесту = истинный" value={pct(t.accuracy.exact_grade_agreement)} hint={`самоописание: ${pct(t.accuracy.self_declared_agreement)} · ±1 грейд: ${pct(t.accuracy.within_one_grade)}`} accent />
            <Stat label="Test–retest r(θ̂)" value={t.consistency.theta_test_retest_r.toFixed(2)} hint={`взвешенная κ грейда: ${t.consistency.grade_kappa_weighted.toFixed(2)}`} />
            <Stat label="AUC соседних грейдов" value={Math.min(...Object.values(t.discrimination.adjacent_grade_auc) as number[]).toFixed(2) + "+"} hint="разделение слабых и сильных" />
            <Stat label="Заданий в тесте" value={t.accuracy.mean_items.toFixed(1)} hint={t.accuracy.items_distribution ? `от ${t.config.min_items} до ${t.config.max_items}: тест идёт, пока решение не надёжно` : `средняя SE ${t.accuracy.mean_se.toFixed(2)}`} />
          </div>
          {t.accuracy.by_distance_to_cut && (
            <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1.35fr]">
              <Card>
                <CardHeader icon={<ShieldCheck className="h-5 w-5" />} title="Завышенный грейд не проходит" subtitle={`${pct(t.accuracy.inflated_share)} виртуальных кандидатов заявили в анкете грейд выше истинного — как в жизни`} />
                <div className="grid grid-cols-2 gap-3 px-5 pb-5">
                  <div className="rounded-xl bg-night p-4 text-white"><div className="kicker text-white/50">не подтверждён</div><div className="mt-1 font-mono text-[28px] font-bold">{pct(t.accuracy.inflated_rejected)}</div><div className="mt-1 text-[12px] text-white/60">завышенных заявок</div></div>
                  <div className="rounded-xl border border-line p-4"><div className="kicker">подтверждён</div><div className="mt-1 font-mono text-[28px] font-bold">{pct(t.accuracy.honest_confirmed)}</div><div className="mt-1 text-[12px] text-ink-3">честно заявленных грейдов</div></div>
                  <p className="col-span-2 text-[12.5px] text-ink-3">Резюме и анкета не отличают того, кто «приписал» себе грейд; тест возвращает к истинному уровню {pct(t.accuracy.inflated_exact)} таких кандидатов. Проходят завышенный грейд в основном те, чья способность почти дотягивает до порога.</p>
                </div>
              </Card>
              <Card>
                <CardHeader title="Где тест ошибается" subtitle="Точность грейда в зависимости от того, насколько истинная способность далека от порога между грейдами" />
                <div className="h-56 px-3 pb-4">
                  <ResponsiveContainer>
                    <BarChart data={t.accuracy.by_distance_to_cut.map((b: any) => ({ n: `${b.range} (${pct(b.share)})`, v: b.accuracy }))} margin={{ left: -16, right: 10 }}>
                      <CartesianGrid stroke="#EDEDF3" vertical={false} /><XAxis dataKey="n" tick={{ fontSize: 10 }} interval={0} /><YAxis domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={{ fontSize: 12 }} />
                      <Tooltip formatter={(v: any) => pct(Number(v))} />
                      <Bar dataKey="v" name="Точность грейда" radius={[6, 6, 0, 0]}>{t.accuracy.by_distance_to_cut.map((b: any, i: number) => <Cell key={i} fill={b.accuracy >= 0.85 ? "#402FFF" : "#A497FF"} />)}</Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="px-5 pb-5 text-[12.5px] text-ink-3">Подпись — расстояние до порога в логитах и доля популяции. Дальше 0.5 от границы тест почти не ошибается; у самой границы «правильного» грейда по сути нет — поэтому грейд не понижается принудительно, а пересдача доступна через 14 дней.</p>
              </Card>
            </div>
          )}
          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader title="Матрица ошибок категоризации" subtitle={`κ Коэна ${t.accuracy.kappa.toFixed(2)} (взвешенная ${t.accuracy.kappa_weighted.toFixed(2)}); вдали от порогов (>0.25 θ) — ${pct(t.accuracy.exact_agreement_far_from_cuts)} точных совпадений`} />
              <div className="overflow-x-auto px-5 pb-5">
                <table className="w-full text-center text-[13px]">
                  <thead><tr><th className="py-2 text-left text-[12px] font-medium text-ink-3">истина ↓ / тест →</th>{G.map((g) => <th key={g} className="font-mono">{GN[g]}</th>)}</tr></thead>
                  <tbody>{G.map((a) => { const row = t.accuracy.confusion[a]; const tot = G.reduce((s, b) => s + row[b], 0) || 1; return (
                    <tr key={a}><td className="py-1.5 text-left font-mono font-semibold">{GN[a]}</td>{G.map((b) => <td key={b} className="p-1"><div className="rounded-lg py-2 font-mono" style={{ background: a === b ? `rgba(64,47,255,${0.15 + 0.7 * row[b] / tot})` : `rgba(236,29,53,${0.6 * row[b] / tot})`, color: a === b && row[b] / tot > 0.5 ? "white" : undefined }}>{row[b]}</div></td>)}</tr>); })}</tbody>
                </table>
                <div className="mt-3 grid grid-cols-2 gap-3 text-[12.5px] text-ink-3"><div>Чувствительность решения «подтверждён»: <b className="text-ink">{pct(t.accuracy.decision_sensitivity)}</b></div><div>Специфичность: <b className="text-ink">{pct(t.accuracy.decision_specificity)}</b></div><div>Смещение θ̂: <b className="text-ink">{t.accuracy.theta_bias.toFixed(2)}</b>, RMSE <b className="text-ink">{t.accuracy.theta_rmse.toFixed(2)}</b></div><div>Повтор: совпадение решения <b className="text-ink">{pct(t.consistency.decision_agreement)}</b></div></div>
              </div>
            </Card>
            <Card>
              <CardHeader icon={<ShieldCheck className="h-5 w-5" />} title="Атака утечкой ответов" subtitle="Junior (θ = −0.5) сдаёт тест на Middle, заранее зная ответы, собранные у предыдущих кандидатов" />
              <div className="px-5 pb-5">
                <div className="h-52">
                  <ResponsiveContainer>
                    <BarChart data={[{ n: "Без утечки", v: la.none.pass_rate_middle }, { n: "Статичный банк (60% ответов)", v: la.static.pass_rate_middle }, { n: "Драфт: генерация", v: la.parametric.pass_rate_middle }]} margin={{ left: -16 }}>
                      <CartesianGrid stroke="#EDEDF3" vertical={false} /><XAxis dataKey="n" tick={{ fontSize: 11 }} /><YAxis domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={{ fontSize: 12 }} />
                      <Tooltip formatter={(v: any) => pct(Number(v))} />
                      <Bar dataKey="v" name="Доля «прошедших» Middle" radius={[6, 6, 0, 0]}>{["#B8B8C7", "#EC1D35", "#402FFF"].map((c) => <Cell key={c} fill={c} />)}</Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="grid grid-cols-2 gap-3 text-[12.5px] text-ink-3">
                  <div>Завышение θ при статичном банке: <b className="text-accent-600">+{la.theta_inflation_static.toFixed(2)}</b></div>
                  <div>Завышение θ у нас: <b className="text-brand-700">+{la.theta_inflation_parametric.toFixed(2)}</b></div>
                  <div>Уникальность вариантов: медиана <b className="text-ink">{pct(r.variants.median_unique_share)}</b></div>
                  <div>Вероятность совпадения двух вариантов: <b className="text-ink">{(r.variants.mean_pairwise_collision * 100).toFixed(2)}%</b></div>
                </div>
              </div>
            </Card>
          </div>
          <div className="mt-5 grid gap-5 lg:grid-cols-3">
            <Card className="p-5">
              <div className="text-[15px] font-semibold">Экспозиция и пересечение форм</div>
              <div className="mt-3 space-y-2 text-[13px] text-ink-2">
                <div className="flex justify-between"><span>Макс. экспозиция семейства (Драфт)</span><b>{pct(r.exposure_ablation.randomesque.max_exposure)}</b></div>
                <div className="flex justify-between"><span>…без контроля экспозиции</span><b className="text-accent-600">{pct(r.exposure_ablation.max_info.max_exposure)}</b></div>
                <div className="flex justify-between"><span>Пересечение форм двух кандидатов</span><b>{pct(t.exposure.mean_form_overlap_between_candidates)}</b></div>
                <div className="flex justify-between"><span>…семейства, не варианты; варианты различны</span><b>{(r.variants.mean_pairwise_collision * 100).toFixed(2)}%</b></div>
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-[15px] font-semibold">Адаптивный vs фиксированный тест той же средней длины</div>
              <div className="mt-3 space-y-2 text-[13px] text-ink-2">
                <div className="flex justify-between"><span>Точность грейда: CAT</span><b>{pct(r.fixed_form.cat.grade_accuracy)}</b></div>
                <div className="flex justify-between"><span>Точность грейда: фикс. форма</span><b>{pct(r.fixed_form.fixed.grade_accuracy)}</b></div>
                <div className="flex justify-between"><span>Средняя SE: CAT / фикс.</span><b>{r.fixed_form.cat.mean_se.toFixed(2)} / {r.fixed_form.fixed.mean_se.toFixed(2)}</b></div>
                <div className="text-[12px] text-ink-3">При той же средней длине ({r.fixed_form.items}) CAT измеряет точнее по всему диапазону, а фиксированная форма одинакова у всех и уязвима к утечке.</div>
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-[15px] font-semibold">Калибровка и дрейф</div>
              <div className="mt-3 space-y-2 text-[13px] text-ink-2">
                <div className="flex justify-between"><span>RMSE трудности: априорная</span><b>{r.calibration.rmse_b_prior}</b></div>
                <div className="flex justify-between"><span>…после онлайн-калибровки</span><b className="text-brand-700">{r.calibration.rmse_b_after}</b></div>
                <div className="flex justify-between"><span>Имитация утечки приёма решения</span><b>{r.calibration.drift_detected} из {r.calibration.drift_simulated} найдено</b></div>
                <div className="flex justify-between"><span>Ложные срабатывания</span><b>{r.calibration.false_alarms}</b></div>
                <div className="flex justify-between"><span>Медиана точечно-бисериальной r</span><b>{t.discrimination.median_point_biserial}</b></div>
              </div>
            </Card>
          </div>
        </div>
        {r.stop_rule_ablation && (
          <Card>
            <CardHeader title="Правило остановки: по точности оценки или по надёжности решения" subtitle="Тест решает задачу классификации, поэтому мы заменили остановку «SE ≤ 0.35» на классификационную: тест идёт, пока решение по каждому порогу не станет надёжным (≥ 85%), у границы грейда задания подбираются по информации в точке порога. Одна популяция, два независимых прохождения." />
            <div className="overflow-x-auto px-5 pb-5">
              <table className="w-full min-w-[560px] text-[13px]">
                <thead><tr className="text-left text-ink-3"><th className="py-2 font-medium">Правило</th><th className="font-medium">Точный грейд</th><th className="font-medium">Вдали от порогов</th><th className="font-medium">Решение</th><th className="font-medium">Повтор: тот же грейд</th><th className="font-medium">Заданий (макс.)</th></tr></thead>
                <tbody>{Object.entries(r.stop_rule_ablation).map(([k, v]: any) => (
                  <tr key={k} className={"border-t border-line " + (k === "classification" ? "font-semibold text-brand-700" : "")}>
                    <td className="py-2 pr-2">{k === "classification" ? "По надёжности решения (Драфт)" : "По точности, SE ≤ 0.35 (прежнее)"}</td>
                    <td className="num">{pct(v.exact)}</td><td className="num">{pct(v.far_from_cuts)}</td><td className="num">{pct(v.decision)}</td><td className="num">{pct(v.retest_agreement)}</td><td className="num">{v.mean_items} ({v.max_items})</td>
                  </tr>))}
                </tbody>
              </table>
              <p className="mt-3 text-[12.5px] text-ink-3">Точнее и короче в среднем: очевидные случаи завершаются за 8–12 заданий, а время уходит туда, где решение спорное.</p>
            </div>
          </Card>
        )}
        {r.resume_parsing && <ResumeParsing rp={r.resume_parsing} />}
        <Alert tone="brand" icon={<Info className="h-4 w-4" />} title="Ограничения и дальнейшая валидация с ФСП">
          Параметры заданий — экспертные априорные значения, уточняемые онлайн-калибровкой. После пилота предлагаем: калибровку на 300–500 реальных прохождениях, сопоставление θ с рейтингом ФСП (конвергентная валидность), разметку 20 потребностей × 30 кандидатов экспертами-рекрутерами для оценки подбора (инструмент проверки на своём наборе пар уже встроен — блок выше) и A/B-сравнение доли принятых приглашений.
        </Alert>
      </div>
    </div>
  );
}

const FIELD_NAMES: Record<string, string> = { name: "ФИО", email: "E-mail", phone: "Телефон", telegram: "Telegram", github: "GitHub", city: "Город",
  specialization: "Специализация", experience_years: "Стаж (±0.5 года)" };

function ResumeParsing({ rp }: { rp: any }) {
  const fr = rp.holdout_first_run;
  const sk = (s: any) => `${s.precision.toFixed(2)} / ${s.recall.toFixed(2)} / ${s.f1.toFixed(2)}`;
  return (
    <Card>
      <CardHeader icon={<FileSearch className="h-5 w-5" />} title="Категоризация по стеку: разбор резюме на размеченном вручную наборе"
        subtitle={`Резюме написаны независимо от генератора синтетики: hh.ru, LinkedIn, свободный текст, сленг («реакт», «k8s», «докер»), английский. Основной набор (${rp.dev.resumes}) использовался для доработки парсера, отложенный (${rp.holdout.resumes}) — написан после неё; первый замер на нём — до любых правок.`} />
      <div className="overflow-x-auto px-5 pb-5">
        <table className="w-full min-w-[560px] text-[13px]">
          <thead><tr className="text-left text-ink-3"><th className="py-2 font-medium">Поле</th><th className="font-medium">Основной</th><th className="font-medium">Отложенный: первый замер</th><th className="font-medium">Отложенный: после правок</th></tr></thead>
          <tbody>
            {Object.keys(FIELD_NAMES).map((k) => (
              <tr key={k} className="border-t border-line"><td className="py-1.5 pr-2">{FIELD_NAMES[k]}</td><td className="num">{pct(rp.dev.field_accuracy[k])}</td>
                <td className="num font-semibold text-brand-700">{fr ? pct(fr.field_accuracy[k]) : "—"}</td><td className="num">{pct(rp.holdout.field_accuracy[k])}</td></tr>))}
            <tr className="border-t border-line"><td className="py-1.5 pr-2">Навыки: precision / recall / F1</td><td className="num">{sk(rp.dev.skills)}</td>
              <td className="num font-semibold text-brand-700">{fr ? sk(fr.skills) : "—"}</td><td className="num">{sk(rp.holdout.skills)}</td></tr>
          </tbody>
        </table>
        <p className="mt-3 text-[12.5px] text-ink-3">Кандидат подтверждает распознанное перед сохранением, а грейд определяет тест — ошибка разбора резюме не меняет категорию. Оставшиеся ошибки — содержательные неоднозначности (fullstack PHP + Vue, C++-разработчик сетевого шлюза).</p>
      </div>
    </Card>
  );
}
