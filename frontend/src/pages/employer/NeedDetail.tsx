import clsx from "clsx";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Pencil, RefreshCw, RotateCcw, Send, SlidersHorizontal, Trophy, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { CompareModal } from "@/components/Compare";
import { CandidateRow, InviteModal } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, Checkbox, ChoiceChips, DataTable, EmptyState, Meter, Modal, PageLoader, RichText, Tabs, Toggle } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { ago, GRADE_NAMES, GRADE_ORDER, salaryRange } from "@/lib/format";

const EMPTY = { grades: [] as string[], skills: [] as string[], verified_only: false, fsp_only: false, formats: [] as string[], relation: "", min_score: 0, within_budget: false, mark: "" };

export default function NeedDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const [flt, setFlt] = useState({ ...EMPTY });
  const [sel, setSel] = useState<Record<number, any>>({});
  const [inviteFor, setInviteFor] = useState<any[] | null>(null);
  const [plan, setPlan] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const { data: need } = useQuery({ queryKey: ["emp-need", id], queryFn: () => api(`/employer/needs/${id}`) });
  const { data, isLoading, isFetching } = useQuery({ queryKey: ["shortlist", id, flt], queryFn: () => api(`/employer/needs/${id}/shortlist`, { query: flt }), placeholderData: (p) => p });
  const rerun = useMutation({ mutationFn: () => api(`/employer/needs/${id}/run`, { method: "POST" }), onSuccess: (r: any) => { toast.success(`Подборка обновлена: ${r.total_matched} подходящих`); qc.invalidateQueries(); } });
  const mark = useMutation({ mutationFn: ({ cid, mark }: any) => api(`/employer/needs/${id}/shortlist/${cid}`, { method: "PUT", body: { mark } }), onSuccess: () => qc.invalidateQueries({ queryKey: ["shortlist", id] }), onError: (e: ApiError) => toast.error(e.message) });
  const refined = JSON.stringify(flt) !== JSON.stringify(EMPTY);
  const selected = Object.values(sel);
  const [compareIds, setCompareIds] = useState<number[] | null>(null);
  const skillOptions = useMemo(() => [...(need?.must_skills ?? []), ...(need?.nice_skills ?? [])], [need]);
  if (!need || isLoading) return <PageLoader />;
  const items = data?.items ?? [];
  const cats = need.recommended_categories ?? [];
  return (
    <div className="space-y-5">
      <PageHeader back={{ to: "/e/needs", label: "Потребности" }} title={need.title}
        subtitle={<span className="flex flex-wrap items-center gap-2">{need.categories.map((c: string) => <Badge key={c} tone="dark">{c}</Badge>)}<span>{salaryRange(need.salary_from, need.salary_to)}</span>
          {need.must_skills.map((s: string) => <Badge key={s} tone="brand">{s}</Badge>)}<span className="text-ink-4">· обновлено {ago(need.last_run_at)}</span></span>}
        action={<>
          <Button variant="outline" icon={<FlaskConical className="h-4 w-4" />} onClick={() => setPlan(true)}>Как тестировали кандидатов</Button>
          <Link to={`/e/needs/${id}/edit`}><Button variant="outline" icon={<Pencil className="h-4 w-4" />}>Изменить</Button></Link>
          <Button variant="secondary" icon={<RefreshCw className={clsx("h-4 w-4", rerun.isPending && "animate-spin")} />} onClick={() => rerun.mutate()}>Обновить подборку</Button>
        </>} />
      {need.market?.status === "low" && <Alert tone="warn">{need.market.message} (медиана {Math.round(need.market.market_median / 1000)} тыс. ₽).</Alert>}

      {/* рекомендованные категории */}
      <div>
        <div className="kicker mb-2.5">Рекомендованные категории</div>
        <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-thin">
          {cats.map((c: any) => {
            const active = flt.relation === c.relation && (flt.grades.length === 1 && flt.grades[0] === c.grade);
            return (
              <button key={`${c.specialization}-${c.grade}`} onClick={() => setFlt(active ? { ...EMPTY } : { ...EMPTY, relation: c.relation, grades: [c.grade] })}
                className={clsx("min-w-[230px] rounded-2xl border p-4 text-left transition", active ? "border-brand-500 bg-brand-50" : c.relation === "target" ? "border-night bg-white" : "border-line bg-white hover:border-brand-200")}>
                <div className="flex items-center justify-between gap-2"><span className="font-mono text-[14px] font-bold">{c.label}</span>{c.relation === "target" ? <Badge tone="dark">целевая</Badge> : <Badge tone="warn">смежная</Badge>}</div>
                <div className="mt-3 flex items-end gap-4">
                  <div><div className="font-mono text-[24px] font-bold leading-none">{c.count}</div><div className="text-[11.5px] text-ink-3">кандидатов</div></div>
                  <div className="text-[12px] text-ink-3"><div className="flex items-center gap-1"><Trophy className="h-3.5 w-3.5 text-accent-500" />{c.with_fsp} с ФСП</div><div>{Math.round(c.salary_fit_share * 100)}% в вашей вилке</div></div>
                </div>
                <div className="mt-2 line-clamp-2 text-[12px] text-ink-3">{c.note}</div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[260px_1fr]">
        {/* уточнение */}
        <div className={clsx("lg:block", !showFilters && "hidden")}>
          <Card className="space-y-5 p-4 lg:sticky lg:top-24">
            <div className="flex items-center justify-between"><span className="text-[14px] font-semibold">Уточнить подборку</span>{refined && <button onClick={() => setFlt({ ...EMPTY })} className="inline-flex items-center gap-1 text-[12px] text-brand-600"><RotateCcw className="h-3.5 w-3.5" />сбросить</button>}</div>
            <div>
              <div className="kicker mb-2">Грейд</div>
              <div className="space-y-1.5">{GRADE_ORDER.map((g) => <Checkbox key={g} checked={flt.grades.includes(g)} onChange={(v) => setFlt({ ...flt, grades: v ? [...flt.grades, g] : flt.grades.filter((x) => x !== g) })} label={GRADE_NAMES[g]} />)}</div>
            </div>
            {skillOptions.length > 0 && (
              <div>
                <div className="kicker mb-2">Обязательно владеет</div>
                <div className="space-y-1.5">{skillOptions.map((s: string) => <Checkbox key={s} checked={flt.skills.includes(s)} onChange={(v) => setFlt({ ...flt, skills: v ? [...flt.skills, s] : flt.skills.filter((x) => x !== s) })} label={s} />)}</div>
                <div className="mt-2.5"><Toggle checked={flt.verified_only} onChange={(v) => setFlt({ ...flt, verified_only: v })} label="Только подтверждённые" /></div>
              </div>
            )}
            <div className="space-y-3">
              <Toggle checked={flt.fsp_only} onChange={(v) => setFlt({ ...flt, fsp_only: v })} label="С достижениями ФСП" />
              <Toggle checked={flt.within_budget} onChange={(v) => setFlt({ ...flt, within_budget: v })} label="Ожидания в моей вилке" />
            </div>
            <div><div className="kicker mb-2">Формат</div><ChoiceChips multi options={[{ code: "office", name: "Офис" }, { code: "hybrid", name: "Гибрид" }, { code: "remote", name: "Удалённо" }]} value={flt.formats} onChange={(v) => setFlt({ ...flt, formats: v })} /></div>
            <div>
              <div className="kicker mb-2">Минимальное соответствие: {flt.min_score}</div>
              <input type="range" min={0} max={80} step={5} value={flt.min_score} onChange={(e) => setFlt({ ...flt, min_score: Number(e.target.value) })} className="w-full accent-[#402FFF]" />
            </div>
          </Card>
        </div>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex min-w-0 max-w-full items-center gap-3">
              <Button size="sm" variant="outline" className="shrink-0 lg:hidden" icon={<SlidersHorizontal className="h-4 w-4" />} onClick={() => setShowFilters(!showFilters)}>Фильтры</Button>
              <Tabs value={flt.mark || "all"} onChange={(v: string) => setFlt({ ...flt, mark: v === "all" ? "" : v })}
                className="min-w-0" tabs={[{ id: "all", label: "Подборка" }, { id: "starred", label: "Избранные", count: need.shortlist.starred }, { id: "hidden", label: "Скрытые", count: need.shortlist.hidden }]} />
            </div>
            <div className="flex items-center gap-2 text-[13px] text-ink-3">
              <Users className="h-4 w-4" />{refined ? <>показано <b className="text-ink">{data.filtered_total}</b> из {data.base_total} — исходная подборка сохранена</> : <>{data.base_total} в подборке</>}
              {isFetching && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
            </div>
          </div>
          {selected.length > 0 && (
            <div className="sticky top-20 z-20 flex items-center justify-between gap-3 rounded-2xl bg-night px-4 py-3 text-white shadow-xl">
              <span className="text-[14px]">Выбрано: <b>{selected.length}</b></span>
              <div className="flex gap-2"><Button size="sm" variant="ghost" className="text-white/70 hover:bg-white/10" onClick={() => setSel({})}>Сбросить</Button>
                <Button size="sm" variant="secondary" disabled={selected.length < 2 || selected.length > 3} onClick={() => setCompareIds(selected.map((x: any) => x.id))}>
                  {selected.length < 2 ? "Сравнить (выберите 2–3)" : selected.length > 3 ? "Сравнить можно до 3" : "Сравнить"}</Button>
                <Button size="sm" icon={<Send className="h-4 w-4" />} onClick={() => setInviteFor(selected)}>Пригласить выбранных</Button></div>
            </div>
          )}
          {items.length === 0 ? <Card><EmptyState icon={<Users />} title="Никого не найдено" text={refined ? "Ослабьте уточнения — исходная подборка не потеряна." : "Расширьте грейды или обязательные навыки."} action={refined && <Button onClick={() => setFlt({ ...EMPTY })}>Сбросить уточнения</Button>} /></Card> : (
            items.map((c: any) => (
              <CandidateRow key={c.id} c={c} needId={need.id} onInvite={(x) => setInviteFor([x])} onMark={(m) => mark.mutate({ cid: c.id, mark: m })}
                selected={!!sel[c.id]} onSelect={(v) => setSel((s) => { const n = { ...s }; if (v) n[c.id] = c; else delete n[c.id]; return n; })} />
            ))
          )}
        </div>
      </div>
      <CompareModal needId={need.id} ids={compareIds} onClose={() => setCompareIds(null)} />
      <InviteModal open={!!inviteFor} onClose={() => setInviteFor(null)} candidates={inviteFor ?? []} need={need} onSent={() => setSel({})} />
      <TestPlanModal open={plan} onClose={() => setPlan(false)} url={`/employer/needs/${id}/test-plan`} />
    </div>
  );
}

export function TestPlanModal({ open, onClose, url }: { open: boolean; onClose: () => void; url: string }) {
  const { data, isLoading } = useQuery({ queryKey: ["plan", url], queryFn: () => api(url), enabled: open });
  return (
    <Modal open={open} onClose={onClose} wide title="Как формируется тест под эту потребность">
      {isLoading || !data ? <PageLoader /> : (
        <div className="space-y-5">
          <Alert tone="brand">{data.note}</Alert>
          <div>
            <div className="kicker mb-2">План теста: доли компетенций с учётом стека ({data.lang}{data.framework ? `, ${data.framework}` : ""})</div>
            <div className="space-y-2.5">
              {data.plan.map((p: any) => (
                <div key={p.competency} className="grid grid-cols-[minmax(0,1fr)_120px_120px] items-center gap-3 text-[13px]">
                  <div className="min-w-0"><div className="font-medium">{p.name}</div><div className="truncate text-[12px] text-ink-3">{(data.coverage[p.competency] ?? []).join(", ") || "базовая компетенция специализации"}</div></div>
                  <Meter value={p.weight / 0.4} /><span className="num text-right text-ink-3">{Math.round(p.weight * 100)}% · {p.families} семейств</span>
                </div>
              ))}
            </div>
            {data.uncovered_skills?.length > 0 && <div className="mt-2 text-[12.5px] text-ink-3">Не проверяются тестом напрямую (учитываются через ФСП, задачи и резюме): {data.uncovered_skills.join(", ")}</div>}
          </div>
          <div>
            <div className="kicker mb-2">Примеры сгенерированных заданий (у каждого кандидата — свой вариант)</div>
            <div className="grid gap-3">
              {data.samples.map((s: any) => (
                <div key={s.variant_hash} className="rounded-xl border border-line p-4">
                  <div className="mb-2 flex flex-wrap items-center gap-2"><Badge tone="brand">{s.competency}</Badge><Badge>{s.title}</Badge><span className="font-mono text-[11px] text-ink-4">вариант {s.variant_hash.slice(0, 8)}</span></div>
                  <RichText text={s.payload.text} className="text-[14px]" />
                  {s.payload.code && <pre className="code-block mt-2 max-h-48">{s.payload.code}</pre>}
                  {s.payload.tables?.slice(0, 1).map((t: any) => <div key={t.name} className="mt-2"><DataTable {...t} /></div>)}
                  {s.payload.options && <ul className="mt-2 space-y-1">{s.payload.options.map((o: string, i: number) => <li key={i} className="rounded-lg bg-surface px-3 py-1.5 text-[13px]">{o}</li>)}</ul>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}
