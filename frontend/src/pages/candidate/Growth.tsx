import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";
import { Compass, Footprints, TrendingUp, Wallet } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CardHeader, Meter, PageLoader } from "@/components/ui";
import { api } from "@/lib/api";
import { GRADE_NAMES } from "@/lib/format";

const k = (v?: number | null) => (v == null ? "—" : `${Math.round(v / 1000)}к`);
const POSITION: Record<string, [string, string]> = {
  below: ["ниже рынка категории", "warn"], in: ["в рынке категории", "ok"], above: ["выше рынка категории", "brand"],
};

/** Шкала: квартили ожиданий категории и отметки — ваши ожидания, медианы вакансий, приглашений и рынка. */
function Radar({ r, own }: { r: any; own?: number | null }) {
  const marks = [
    own ? { v: own, label: "вы", cls: "bg-night" } : null,
    r.offers ? { v: r.offers.median, label: "приглашения", cls: "bg-ok-500" } : null,
    r.vacancies ? { v: r.vacancies.median, label: "вакансии", cls: "bg-accent-500" } : null,
    r.market_median ? { v: r.market_median, label: "рынок", cls: "bg-ink-3" } : null,
  ].filter(Boolean) as { v: number; label: string; cls: string }[];
  const q = r.expectations;
  const vals = [...marks.map((m) => m.v), ...(q ? [q.p25, q.p75] : [])];
  const lo = Math.min(...vals) * 0.85, hi = Math.max(...vals) * 1.1;
  const pos = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  return (
    <div>
      <div className="relative mt-8 h-3 rounded-full bg-line">
        {q && <div className="absolute inset-y-0 rounded-full bg-brand-200" style={{ left: pos(q.p25), width: `calc(${pos(q.p75)} - ${pos(q.p25)})` }} title="ожидания кандидатов категории: 25–75%" />}
        {q && <div className="absolute inset-y-[-3px] w-0.5 bg-brand-600" style={{ left: pos(q.p50) }} />}
        {marks.map((m) => (
          <div key={m.label} className="absolute -top-7 -translate-x-1/2 text-center" style={{ left: pos(m.v) }}>
            <div className="whitespace-nowrap text-[11px] text-ink-3">{m.label} · {k(m.v)}</div>
            <div className={clsx("mx-auto mt-1 h-5 w-1.5 rounded-full", m.cls)} />
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-3">
        {q ? <span>ожидания {q.n} кандидатов категории: 25% — {k(q.p25)}, медиана — {k(q.p50)}, 75% — {k(q.p75)}</span> : <span>кандидатов категории пока меньше 5 — распределение скрыто</span>}
        {r.vacancies && <span>вакансии: медиана середины вилки по {r.vacancies.companies} компаниям</span>}
        {r.offers && <span>приглашения: медиана по {r.offers.companies} компаниям</span>}
      </div>
    </div>
  );
}

export default function Growth() {
  const { data, isLoading } = useQuery({ queryKey: ["insights"], queryFn: () => api("/candidate/insights") });
  if (isLoading || !data) return <PageLoader />;
  if (!data.available) return (
    <div className="space-y-6"><PageHeader title="Рост и зарплаты" /><Alert>{data.reason} <Link className="link" to="/c/assessment">Перейти к опросу →</Link></Alert></div>
  );
  const pos = data.position ? POSITION[data.position] : null;
  return (
    <div className="space-y-6">
      <PageHeader title="Рост и зарплаты" subtitle={`Категория ${data.category}. Данные платформы обезличены: распределения — от ${data.privacy.min_values} значений, вилки компаний — от ${data.privacy.min_companies} компаний. Все суммы — gross в месяц.`} />
      <Card>
        <CardHeader icon={<Wallet className="h-5 w-5" />} title="Зарплатный радар" subtitle={`${data.category}${data.grade_confirmed ? "" : " · грейд не подтверждён"}`}
          action={pos && <Badge tone={pos[1] as any}>Ваши ожидания {pos[0]}</Badge>} />
        <div className="px-5 pb-6"><Radar r={data.now} own={data.own_expectation} />
          {!data.own_expectation && <p className="mt-3 text-[13px] text-ink-3">Укажите ожидания в <Link className="link" to="/c/profile">профиле</Link>, чтобы увидеть своё место на шкале.</p>}
        </div>
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader icon={<TrendingUp className="h-5 w-5" />} title={data.next_grade ? `Следующий грейд — ${GRADE_NAMES[data.next_grade]}` : "Вы на верхнем грейде платформы"}
            subtitle={data.next_grade ? "Ориентир зарплаты после повышения" : "Рост — в навыках и результатах ФСП"} />
          <div className="space-y-4 px-5 pb-5">
            {data.next && (
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-surface p-4"><div className="kicker">Сейчас · рынок</div><div className="mt-1 font-mono text-[22px] font-bold">{k(data.now.market_median)}</div></div>
                <div className="rounded-xl bg-night p-4 text-white"><div className="kicker text-white/50">{GRADE_NAMES[data.next_grade]} · рынок</div><div className="mt-1 font-mono text-[22px] font-bold">{k(data.next.market_median)}</div></div>
              </div>
            )}
            {data.next && <Radar r={data.next} own={null} />}
            <Link to="/c/assessment"><Button variant="outline" className="mt-2">К тестированию</Button></Link>
          </div>
        </Card>
        <Card>
          <CardHeader icon={<Compass className="h-5 w-5" />} title={`Что просят на уровне ${GRADE_NAMES[data.demand.grade]}`}
            subtitle={data.demand.postings ? `по ${data.demand.postings} вакансиям и потребностям работодателей${data.demand.postings < 5 ? " — выборка пока мала" : ""}` : "публикаций пока нет"} />
          <div className="space-y-4 px-5 pb-5">
            {data.demand.gaps.length > 0 && (
              <div>
                <div className="kicker mb-2">Нет в вашем профиле</div>
                {data.demand.gaps.map((g: any) => (
                  <div key={g.skill} className="grid grid-cols-[130px_1fr_44px] items-center gap-3 py-1 text-[13px]"><span>{g.skill}</span><Meter value={g.share} /><span className="num text-right text-ink-3">{Math.round(g.share * 100)}%</span></div>
                ))}
              </div>
            )}
            {data.demand.strengths.length > 0 && (
              <div>
                <div className="kicker mb-2">Уже есть</div>
                <div className="flex flex-wrap gap-1.5">{data.demand.strengths.map((s: any) => <Badge key={s.skill} tone={s.verified ? "brand" : undefined}>{s.skill}{s.verified ? " · тест" : ""}</Badge>)}</div>
              </div>
            )}
          </div>
        </Card>
      </div>
      <Card>
        <CardHeader icon={<Footprints className="h-5 w-5" />} title="Следующие шаги" />
        <ol className="space-y-2.5 px-5 pb-5">
          {data.steps.map((s: string, i: number) => (
            <li key={i} className="flex gap-3 text-[14px] text-ink-2"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand-50 font-mono text-[12px] font-semibold text-brand-700">{i + 1}</span>{s}</li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
