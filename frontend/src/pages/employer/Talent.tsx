import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";
import { Map, Search, Trophy } from "lucide-react";
import { useState } from "react";
import { CandidateRow, InviteModal } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Button, Card, Checkbox, Field, Input, PageLoader, Select, TagInput, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { GRADE_NAMES, GRADE_ORDER } from "@/lib/format";

export default function Talent() {
  const { data: cat } = useCatalog();
  const { data: map, isLoading } = useQuery({ queryKey: ["category-map"], queryFn: () => api("/employer/categories") });
  const [f, setF] = useState<any>({ specialization: "", grades: [], skills: [], verified_only: false, fsp_only: false, confirmed_only: false, formats: [], city: "", salary_max: "", q: "", sort: "strength" });
  const [page, setPage] = useState(0);
  const { data: res, isFetching } = useQuery({ queryKey: ["talent-search", f, page], queryFn: () => api("/employer/candidates", { query: { ...f, limit: 20, offset: page * 20 } }), placeholderData: (p) => p });
  const [invite, setInvite] = useState<any[] | null>(null);
  if (isLoading || !cat) return <PageLoader />;
  const max = Math.max(...map.rows.flatMap((r: any) => r.cells.map((c: any) => c.count)), 1);
  const pick = (spec: string, grade: string) => { setF({ ...f, specialization: spec, grades: [grade] }); setPage(0); document.getElementById("results")?.scrollIntoView({ behavior: "smooth" }); };
  return (
    <div className="space-y-6">
      <PageHeader title="Банк кандидатов" subtitle="Кандидаты распределены по категориям «специализация × грейд» по результатам тестирования. Выберите категорию на карте или уточните поиск." />
      <Card className="overflow-x-auto">
        <div className="flex items-center gap-2 px-5 pt-5 text-[15px] font-semibold"><Map className="h-5 w-5 text-brand-500" />Карта категорий <span className="text-[13px] font-normal text-ink-3">· {map.total} кандидатов в базе</span></div>
        <table className="mt-3 w-full min-w-[760px] border-separate border-spacing-1.5 px-3 pb-3 text-[13px]">
          <thead><tr><th className="w-48 px-2 text-left font-medium text-ink-3">Специализация</th>{GRADE_ORDER.map((g) => <th key={g} className="font-mono font-semibold text-ink-2">{GRADE_NAMES[g]}</th>)}</tr></thead>
          <tbody>
            {map.rows.map((r: any) => (
              <tr key={r.specialization}>
                <td className="px-2 font-medium">{r.name}</td>
                {r.cells.map((c: any) => {
                  const intensity = c.count / max;
                  const active = f.specialization === r.specialization && f.grades.length === 1 && f.grades[0] === c.grade;
                  return (
                    <td key={c.grade} className="p-0">
                      <button onClick={() => pick(r.specialization, c.grade)} title={`${r.short} · ${c.grade_name}`}
                        className={clsx("w-full rounded-xl px-3 py-2.5 text-left transition hover:ring-2 hover:ring-brand-400", active && "ring-2 ring-brand-500")}
                        style={{ background: `rgba(64,47,255,${0.06 + intensity * 0.55})`, color: intensity > 0.55 ? "white" : "#1B1C21" }}>
                        <div className="font-mono text-[18px] font-bold leading-none">{c.count}</div>
                        <div className="mt-1 flex items-center gap-2 text-[11px] opacity-80"><span className="inline-flex items-center gap-0.5"><Trophy className="h-3 w-3" />{c.with_fsp}</span>{c.median_salary && <span>~{Math.round(c.median_salary / 1000)}к</span>}{c.unconfirmed > 0 && <span title="Грейд заявлен, тестом не подтверждён">+{c.unconfirmed} не подтв.</span>}</div>
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <div id="results" className="grid gap-5 lg:grid-cols-[270px_1fr]">
        <Card className="h-fit space-y-4 p-4 lg:sticky lg:top-24">
          <div className="text-[14px] font-semibold">Фильтры</div>
          <Field label="Поиск"><div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-4" /><Input className="pl-9" value={f.q} onChange={(e) => { setF({ ...f, q: e.target.value }); setPage(0); }} placeholder="Заголовок, навык…" /></div></Field>
          <Field label="Специализация"><Select value={f.specialization} onChange={(e) => { setF({ ...f, specialization: e.target.value }); setPage(0); }}><option value="">Все</option>{cat.specializations.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}</Select></Field>
          <div><div className="label">Грейд</div><div className="grid grid-cols-2 gap-1.5">{GRADE_ORDER.map((g) => <Checkbox key={g} checked={f.grades.includes(g)} onChange={(v) => { setF({ ...f, grades: v ? [...f.grades, g] : f.grades.filter((x: string) => x !== g) }); setPage(0); }} label={GRADE_NAMES[g]} />)}</div></div>
          <Field label="Стек"><TagInput value={f.skills} onChange={(v) => { setF({ ...f, skills: v }); setPage(0); }} suggestions={cat.skills.map((s) => s.name)} placeholder="Навыки" /></Field>
          <Toggle checked={f.verified_only} onChange={(v) => setF({ ...f, verified_only: v })} label="Навыки подтверждены тестом" />
          <Toggle checked={f.fsp_only} onChange={(v) => setF({ ...f, fsp_only: v })} label="Есть достижения ФСП" />
          <Toggle checked={f.confirmed_only} onChange={(v) => { setF({ ...f, confirmed_only: v }); setPage(0); }} label="Только с подтверждённым грейдом" />
          <Field label="Ожидания не выше, ₽ gross"><Input type="number" value={f.salary_max} onChange={(e) => setF({ ...f, salary_max: e.target.value })} /></Field>
          <Field label="Город"><Select value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })}><option value="">Любой</option>{cat.cities.map((c) => <option key={c}>{c}</option>)}</Select></Field>
          <Field label="Сортировка"><Select value={f.sort} onChange={(e) => setF({ ...f, sort: e.target.value })}><option value="strength">Сила подтверждённого профиля</option><option value="theta">Результат теста</option><option value="fresh">Свежая активность</option><option value="salary">Ожидания по зарплате</option></Select></Field>
        </Card>
        <div className="space-y-3">
          <div className="text-[13px] text-ink-3">Найдено: <b className="text-ink">{res?.total ?? "…"}</b>{isFetching && " · обновляем…"} · внутри категории кандидаты упорядочены по силе подтверждённого профиля: тест, ФСП, задачи{res?.unconfirmed > 0 && ` · ${res.unconfirmed} с грейдом, не подтверждённым тестом, — в конце списка`}</div>
          {(res?.items ?? []).map((c: any) => <CandidateRow key={c.id} c={{ ...c, match: null }} onInvite={(x) => setInvite([x])} />)}
          {res && res.total > 20 && (
            <div className="flex items-center justify-center gap-3 pt-2">
              <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Назад</Button>
              <span className="text-[13px] text-ink-3">{page + 1} / {Math.ceil(res.total / 20)}</span>
              <Button variant="outline" size="sm" disabled={(page + 1) * 20 >= res.total} onClick={() => setPage(page + 1)}>Далее</Button>
            </div>
          )}
        </div>
      </div>
      <InviteModal open={!!invite} onClose={() => setInvite(null)} candidates={invite ?? []} />
    </div>
  );
}
