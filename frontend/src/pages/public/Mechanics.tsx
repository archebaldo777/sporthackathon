import { useQuery } from "@tanstack/react-query";
import { Dices, FlaskConical, Play, Repeat, ShieldCheck, Sigma, TimerReset } from "lucide-react";
import { useMemo, useState } from "react";
import { CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis, Area } from "recharts";
import { Badge, Button, Card, CardHeader, DataTable, Field, PageLoader, RichText, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { GRADE_NAMES } from "@/lib/format";

const SPECS: Record<string, string> = { backend: "Backend", frontend: "Frontend", mobile: "Mobile", ml: "Data Science / ML", data_analyst: "Аналитика данных", devops: "DevOps / SRE", qa: "QA", infosec: "Информационная безопасность" };
const LVL = ["", "Стажёр", "Junior", "Middle", "Senior"];

export default function Mechanics() {
  const { data: bank, isLoading } = useQuery({ queryKey: ["bank"], queryFn: () => api("/mechanics/bank", { auth: false }) });
  return (
    <div>
      <section className="bg-night text-white">
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
          <div className="kicker text-white/50">Механика тестирования</div>
          <h1 className="mt-3 max-w-4xl text-[34px] font-extrabold leading-tight sm:text-[44px]">Задания, которые невозможно «слить», и тест, который сравнивает всех по одной шкале</h1>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {[
              [<Dices key="1" />, "Шаблоны-генераторы вместо заданий", "В банке хранятся семейства. Каждый вариант генерируется заново: другие данные, код, таблицы, набор утверждений. Ответ вычисляется — исполнением SQL, симуляцией алгоритма, пересчётом формулы."],
              [<Sigma key="2" />, "Одинаковая трудность — IRT", "Варианты семейства изоморфны: та же когнитивная операция. Параметры трудности a, b, c калибруются на уровне семейства по модели 3PL, поэтому оценки разных кандидатов сопоставимы."],
              [<Repeat key="3" />, "Адаптивность и контроль экспозиции", "Следующее задание — по максимуму информации около текущей оценки (у границы грейда — в точке порога), с балансом компетенций и случайным выбором из топ-4. Тест заканчивается, когда решение о грейде надёжно: очевидным случаям — 8–12 заданий, пограничным — до 22."],
            ].map(([icon, t, d], i) => (
              <div key={i} className="rounded-2xl border border-white/10 bg-white/5 p-5">
                <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-500 [&_svg]:h-5 [&_svg]:w-5">{icon}</div>
                <h3 className="mt-4 font-sans text-[16px] font-semibold">{t}</h3>
                <p className="mt-1.5 text-[14px] leading-relaxed text-white/65">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
      <div className="mx-auto max-w-7xl space-y-8 px-4 py-12 sm:px-6">
        {isLoading || !bank ? <PageLoader /> : (
          <>
            <BankOverview bank={bank} />
            <VariantLab bank={bank} />
            <CatSimulator />
            <Rules />
          </>
        )}
      </div>
    </div>
  );
}

function BankOverview({ bank }: { bank: any }) {
  return (
    <Card>
      <CardHeader icon={<FlaskConical className="h-5 w-5" />} title={`Банк: ${bank.total} семейств заданий`} subtitle={`Параметрических генераторов — ${bank.methods.parametric}, комбинаторных пулов утверждений — ${bank.methods.pool}. План теста (blueprint) — доли компетенций по специализации.`} />
      <div className="grid gap-3 px-5 pb-5 md:grid-cols-2 lg:grid-cols-4">
        {Object.entries(bank.by_spec).map(([code, s]: any) => (
          <div key={code} className="rounded-xl border border-line p-4">
            <div className="text-[14px] font-semibold">{s.name}</div>
            <div className="mt-2 space-y-1.5">
              {Object.entries(s.competencies).map(([c, v]: any) => (
                <div key={c} className="flex items-center justify-between gap-2 text-[12.5px]">
                  <span className="truncate text-ink-2">{v.name}</span>
                  <span className="shrink-0 font-mono text-ink-3">{Math.round(s.blueprint[c] * 100)}% · {v.families}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function VariantLab({ bank }: { bank: any }) {
  const showcase = ["sql.left_join", "trace.int_div_mod", "js.event_loop", "alg.graph_traversal", "ml.confusion_f1", "net.cidr_membership", "css.flex_grow", "sec.vuln_snippet", "db.indexes"];
  const [tid, setTid] = useState("sql.left_join");
  const tpl = bank.items.find((t: any) => t.id === tid);
  const langs: string[] = tpl?.langs ?? [];
  const [lang, setLang] = useState("");
  const [nonce, setNonce] = useState(0);
  const { data, isFetching } = useQuery({ queryKey: ["preview", tid, lang, nonce], queryFn: () => api("/mechanics/preview", { query: { template_id: tid, lang: lang || undefined, n: 2 }, auth: false }) });
  const options = useMemo(() => [...showcase.map((s) => bank.items.find((t: any) => t.id === s)).filter(Boolean), ...bank.items.filter((t: any) => !showcase.includes(t.id))], [bank]);
  return (
    <Card>
      <CardHeader icon={<Dices className="h-5 w-5" />} title="Лаборатория вариантов" subtitle="Одно семейство — два случайных варианта, как их увидели бы два разных кандидата. Ключи ответов не показываются." />
      <div className="flex flex-wrap items-end gap-3 px-5 pb-4">
        <Field label="Семейство заданий" className="min-w-[280px] flex-1">
          <Select value={tid} onChange={(e) => { setTid(e.target.value); setLang(""); }}>
            {options.map((t: any) => <option key={t.id} value={t.id}>{t.title} · {t.competency_name} · {LVL[t.level]}</option>)}
          </Select>
        </Field>
        {langs.length > 1 && <Field label="Язык"><Select value={lang} onChange={(e) => setLang(e.target.value)}>{langs.map((l) => <option key={l} value={l}>{l}</option>)}</Select></Field>}
        <Button variant="secondary" icon={<TimerReset className="h-4 w-4" />} loading={isFetching} onClick={() => setNonce(nonce + 1)}>Сгенерировать заново</Button>
      </div>
      {tpl && (
        <div className="flex flex-wrap gap-2 px-5 pb-3 text-[12.5px]">
          <Badge tone="brand">{tpl.method === "parametric" ? "параметрический генератор" : "комбинаторный пул"}</Badge>
          <Badge>IRT: a = {tpl.a}, b = {tpl.b}, c = {tpl.c}</Badge>
          <Badge>уровень {LVL[tpl.level]}</Badge>
          {tpl.administered > 0 && <Badge>показано {tpl.administered} раз · доля верных {Math.round((tpl.p_value ?? 0) * 100)}%</Badge>}
        </div>
      )}
      <div className="grid gap-4 px-5 pb-5 lg:grid-cols-2">
        {(data?.variants ?? []).map((v: any, i: number) => (
          <div key={v.variant_hash} className="rounded-xl border border-line p-4">
            <div className="mb-3 flex items-center justify-between"><Badge tone="dark">Кандидат {i === 0 ? "А" : "Б"}</Badge><span className="font-mono text-[11px] text-ink-4">hash {v.variant_hash.slice(0, 10)}</span></div>
            <RichText text={v.payload.text} className="text-[14px]" />
            {v.payload.code && <pre className="code-block mt-3 max-h-72">{v.payload.code}</pre>}
            {v.payload.tables?.map((t: any) => <div key={t.name} className="mt-3"><DataTable {...t} /></div>)}
            {v.payload.options && <ul className="mt-3 space-y-1.5">{v.payload.options.map((o: string, j: number) => <li key={j} className="rounded-lg border border-line px-3 py-2 text-[13px]">{o}</li>)}</ul>}
            {v.payload.input && <div className="mt-3 rounded-lg border border-dashed border-line px-3 py-2 text-[13px] text-ink-3">Поле ввода ответа ({v.payload.input.type === "number" ? "число" : "текст"})</div>}
          </div>
        ))}
      </div>
    </Card>
  );
}

function CatSimulator() {
  const [theta, setTheta] = useState(0.6);
  const [spec, setSpec] = useState("backend");
  const [grade, setGrade] = useState("middle");
  const [nonce, setNonce] = useState(0);
  const { data, isFetching } = useQuery({ queryKey: ["sim", theta, spec, grade, nonce], queryFn: () => api("/mechanics/simulate", { query: { theta, specialization: spec, target_grade: grade, seed: nonce || undefined }, auth: false }) });
  const traj = (data?.trajectory ?? []).map((t: any) => ({ ...t, band: [t.theta - t.se, t.theta + t.se], ok: t.correct ? t.b : null, bad: !t.correct ? t.b : null }));
  return (
    <Card>
      <CardHeader icon={<Play className="h-5 w-5" />} title="Симулятор адаптивного теста" subtitle="Виртуальный кандидат с заданной истинной способностью проходит тест тем же движком, что и реальные пользователи." />
      <div className="grid gap-4 px-5 pb-4 md:grid-cols-[1fr_200px_160px_auto] md:items-end">
        <Field label={`Истинная способность θ = ${theta.toFixed(1)} (${theta >= 1 ? "Senior" : theta >= 0 ? "Middle" : theta >= -1 ? "Junior" : "Стажёр"})`}>
          <input type="range" min={-2.5} max={2.5} step={0.1} value={theta} onChange={(e) => setTheta(Number(e.target.value))} className="w-full accent-[#402FFF]" />
        </Field>
        <Field label="Специализация"><Select value={spec} onChange={(e) => setSpec(e.target.value)}>{Object.entries(SPECS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
        <Field label="Заявленный грейд"><Select value={grade} onChange={(e) => setGrade(e.target.value)}>{Object.entries(GRADE_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
        <Button variant="secondary" loading={isFetching} onClick={() => setNonce(Math.floor(Math.random() * 1e6) + 1)}>Ещё раз</Button>
      </div>
      {data && (
        <div className="grid gap-5 px-5 pb-5 lg:grid-cols-[1.5fr_1fr]">
          <div className="h-72">
            <ResponsiveContainer>
              <ComposedChart data={traj} margin={{ top: 10, right: 16, left: -14, bottom: 0 }}>
                <CartesianGrid stroke="#EDEDF3" /><XAxis dataKey="n" tick={{ fontSize: 12 }} /><YAxis domain={[-3, 3]} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: any) => (Array.isArray(v) ? v.map((x: number) => x.toFixed(2)).join(" … ") : Number(v).toFixed(2))} labelFormatter={(l) => `Задание ${l}`} />
                <ReferenceLine y={data.true_theta} stroke="#EC1D35" strokeDasharray="5 4" label={{ value: "истинная θ", fontSize: 11, fill: "#EC1D35", position: "insideTopRight" }} />
                {[-1, 0, 1].map((c) => <ReferenceLine key={c} y={c} stroke="#C9C2FF" strokeDasharray="3 3" />)}
                <Area dataKey="band" stroke="none" fill="#402FFF" fillOpacity={0.12} />
                <Line dataKey="theta" stroke="#402FFF" strokeWidth={2.5} dot={false} name="оценка θ̂" />
                <Scatter dataKey="ok" fill="#12A150" name="трудность (верно)" />
                <Scatter dataKey="bad" fill="#EC1D35" name="трудность (неверно)" />
              </ComposedChart>
            </ResponsiveContainer>
            <div className="mt-1 text-[12px] text-ink-3">Линия — оценка θ̂ ± SE после каждого ответа; точки — трудность выданного задания (зелёные — верно, красные — неверно). Пунктир — пороги грейдов.</div>
          </div>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-night p-4 text-white"><div className="kicker text-white/50">θ̂ ± SE</div><div className="mt-1 font-mono text-[22px] font-bold">{data.theta.toFixed(2)} ± {data.se.toFixed(2)}</div></div>
              <div className="rounded-xl bg-surface p-4"><div className="kicker">Решение</div><div className="mt-1 text-[15px] font-semibold">{data.passed ? `${GRADE_NAMES[grade]} подтверждён` : "не подтверждён"}</div>{data.upgrade && <div className="text-[12.5px] text-ok-700">предложить {GRADE_NAMES[data.upgrade]}</div>}{data.suggested && <div className="text-[12.5px] text-ink-3">тест на {GRADE_NAMES[data.suggested]}</div>}</div>
            </div>
            <div className="max-h-52 space-y-1 overflow-y-auto rounded-xl border border-line p-2 text-[12.5px]">
              {data.trajectory.map((t: any) => (
                <div key={t.n} className="flex items-center gap-2 rounded-lg px-2 py-1 hover:bg-surface"><span className="w-5 font-mono text-ink-4">{t.n}</span><span className={t.correct ? "text-ok-700" : "text-accent-600"}>{t.correct ? "✓" : "✗"}</span><span className="flex-1 truncate">{t.title}</span><span className="font-mono text-ink-3">b={t.b}</span></div>
              ))}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

function Rules() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card className="p-5">
        <div className="flex items-center gap-2 text-[15px] font-semibold"><ShieldCheck className="h-5 w-5 text-brand-500" />Решение о грейде</div>
        <ul className="mt-3 space-y-2 text-[13.5px] text-ink-2">
          <li>• Итоговая θ оценивается с популяционным априорным N(0, 1.2) — заявленный грейд не влияет на решение.</li>
          <li>• Остановка — классификационная: по каждому порогу P(выше) или P(ниже) ≥ 85%; иначе тест продолжается (до 22 заданий).</li>
          <li>• Грейд подтверждён, если P(θ ≥ порог) ≥ 50%. Пороги: Стажёр −2, Junior −1, Middle 0, Senior +1.</li>
          <li>• «Уверенно справился» — P(θ ≥ порог следующего грейда) ≥ 80% → отдельный тест на грейд выше без ожидания. Автоматического повышения нет.</li>
          <li>• Не подтвердил — грейд не понижается принудительно; тест на уровень ниже доступен сразу и не расходует попытку.</li>
          <li>• Смена грейда — не чаще раза в 90 дней; повтор того же уровня — через 14 дней; не более 4 попыток за 30 дней.</li>
        </ul>
      </Card>
      <Card className="p-5">
        <div className="flex items-center gap-2 text-[15px] font-semibold"><ShieldCheck className="h-5 w-5 text-brand-500" />Защита от утечек и подсказок</div>
        <ul className="mt-3 space-y-2 text-[13.5px] text-ink-2">
          <li>• Ключ ответа не покидает сервер; время ответа считается по серверным часам, на задание — свой лимит.</li>
          <li>• Уже показанный кому-либо вариант больше не выдаётся: заученные чужие ответы бесполезны (в симуляции утечки — 0% заданий «из утечки»).</li>
          <li>• Индекс согласованности ответов lz (person-fit) выявляет аномалии: «провал» лёгких и решение трудных заданий.</li>
          <li>• Фиксируются уходы со вкладки, вставки текста, подозрительно быстрые верные ответы на сложные задания.</li>
          <li>• При сигналах грейд не присваивается до контрольной формы: 6–10 свежих заданий у порога, таймер строже.</li>
          <li>• Онлайн-калибровка трудности по накопленным ответам; если семейство «вдруг» стало легче — флаг дрейфа (признак утечки способа решения).</li>
        </ul>
      </Card>
    </div>
  );
}
