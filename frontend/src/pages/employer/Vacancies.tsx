import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Briefcase, FlaskConical, Mail, Pencil, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { CandidateRow, CategoryBadge, ExplainPanel, InviteModal, SkillChips, StatusBadge } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, ChoiceChips, EmptyState, Field, Input, Modal, PageLoader, ScoreRing, Select, Tabs, TagInput, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { ago, FORMAT_NAMES, salaryRange, GROSS_HINT } from "@/lib/format";
import { TestPlanModal } from "./NeedDetail";

export default function Vacancies() {
  const { id } = useParams();
  return id ? <VacancyDetail id={Number(id)} /> : <VacancyList />;
}

function VacancyList() {
  const { data, isLoading } = useQuery({ queryKey: ["emp-vacancies"], queryFn: () => api("/employer/vacancies") });
  const [edit, setEdit] = useState<any>(null);
  if (isLoading) return <PageLoader />;
  return (
    <div>
      <PageHeader title="Вакансии" subtitle="Классический сценарий: публикация вакансии и работа с откликами. Дополняет обратную механику — кандидаты без приглашений сохраняют возможность проявить инициативу."
        action={<Button icon={<Plus className="h-4 w-4" />} onClick={() => setEdit({})}>Новая вакансия</Button>} />
      {(data?.items ?? []).length === 0 ? <Card><EmptyState icon={<Briefcase />} title="Вакансий нет" action={<Button onClick={() => setEdit({})}>Опубликовать вакансию</Button>} /></Card> : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.items.map((v: any) => (
            <Link key={v.id} to={`/e/vacancies/${v.id}`} className="card block p-5 transition hover:border-brand-300">
              <div className="flex items-start justify-between gap-3">
                <div><h3 className="font-sans text-[16px] font-semibold">{v.title}</h3><div className="mt-1.5 flex flex-wrap items-center gap-2"><CategoryBadge label={v.category} /><span className="num text-[13px] font-semibold text-brand-700">{salaryRange(v.salary_from, v.salary_to)}</span></div></div>
                <StatusBadge status={v.status === "published" ? "accepted" : "expired"} name={v.status === "published" ? "опубликована" : v.status === "draft" ? "черновик" : "закрыта"} />
              </div>
              <div className="mt-3 flex flex-wrap gap-x-4 text-[12.5px] text-ink-3"><span>Отклики: <b className="text-ink">{v.applications.total}</b>{v.applications.sent ? ` (новых ${v.applications.sent})` : ""}</span><span>Просмотры: {v.views}</span><span>{ago(v.created_at)}</span></div>
              {v.risk_flags?.length > 0 && <div className="mt-2"><Badge tone="warn">{v.risk_flags[0].message}</Badge></div>}
            </Link>
          ))}
        </div>
      )}
      <VacancyForm v={edit} onClose={() => setEdit(null)} />
    </div>
  );
}

function VacancyForm({ v, onClose }: { v: any; onClose: () => void }) {
  const { data: cat } = useCatalog();
  const qc = useQueryClient();
  const [f, setF] = useState<any>({});
  useEffect(() => {
    if (v) setF({ title: v.title ?? "", description: v.description ?? "", specialization: v.specialization ?? "backend", grade: v.grade ?? "middle", must_skills: v.must_skills ?? [],
      nice_skills: v.nice_skills ?? [], work_formats: v.work_formats ?? [], city: v.city ?? "", salary_from: v.salary_from ?? "", salary_to: v.salary_to ?? "", status: v.status ?? "published" });
  }, [v]);
  const save = useMutation({
    mutationFn: () => api(v?.id ? `/employer/vacancies/${v.id}` : "/employer/vacancies", { method: v?.id ? "PUT" : "POST", body: { ...f, city: f.city || null, salary_from: Number(f.salary_from), salary_to: Number(f.salary_to) } }),
    onSuccess: () => { toast.success("Вакансия сохранена"); qc.invalidateQueries(); onClose(); },
    onError: (e: ApiError) => toast.error(e.message, { description: Array.isArray(e.details) ? e.details.map((d: any) => d.msg || d.message).join("; ") : undefined }),
  });
  if (!v || !cat) return null;
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e?.target ? e.target.value : e });
  return (
    <Modal open={!!v} onClose={onClose} wide title={v.id ? "Редактировать вакансию" : "Новая вакансия"}
      footer={<><Button variant="ghost" onClick={onClose}>Отмена</Button><Button loading={save.isPending} onClick={() => save.mutate()}>Сохранить</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Название" required className="sm:col-span-2"><Input value={f.title} onChange={set("title")} /></Field>
        <Field label="Специализация"><Select value={f.specialization} onChange={set("specialization")}>{cat.specializations.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}</Select></Field>
        <Field label="Грейд"><Select value={f.grade} onChange={set("grade")}>{cat.grades.map((g) => <option key={g.code} value={g.code}>{g.name}</option>)}</Select></Field>
        <Field label="Зарплата от, ₽ gross" hint={GROSS_HINT} required><Input type="number" value={f.salary_from} onChange={set("salary_from")} /></Field>
        <Field label="до, ₽" required><Input type="number" value={f.salary_to} onChange={set("salary_to")} /></Field>
        <Field label="Обязательные навыки" className="sm:col-span-2"><TagInput value={f.must_skills} onChange={(x) => setF({ ...f, must_skills: x })} suggestions={cat.skills.map((s) => s.name)} /></Field>
        <Field label="Желательные навыки" className="sm:col-span-2"><TagInput value={f.nice_skills} onChange={(x) => setF({ ...f, nice_skills: x })} suggestions={cat.skills.map((s) => s.name)} /></Field>
        <Field label="Формат"><ChoiceChips multi options={cat.work_formats} value={f.work_formats} onChange={(x) => setF({ ...f, work_formats: x })} /></Field>
        <Field label="Статус"><Select value={f.status} onChange={set("status")}><option value="published">Опубликована</option><option value="draft">Черновик</option><option value="closed">Закрыта</option></Select></Field>
        <Field label="Описание" required className="sm:col-span-2" hint="Тексты с признаками мошенничества (предоплата, запрос паспортных данных) не публикуются"><Textarea rows={6} value={f.description} onChange={set("description")} /></Field>
      </div>
    </Modal>
  );
}

function VacancyDetail({ id }: { id: number }) {
  const qc = useQueryClient();
  const [tab, setTab] = useState("applications");
  const [edit, setEdit] = useState<any>(null);
  const [plan, setPlan] = useState(false);
  const [invite, setInvite] = useState<any[] | null>(null);
  const { data, isLoading } = useQuery({ queryKey: ["emp-vacancy-apps", id], queryFn: () => api(`/employer/vacancies/${id}/applications`) });
  const { data: rec } = useQuery({ queryKey: ["emp-vacancy-rec", id], queryFn: () => api(`/employer/vacancies/${id}/recommended`), enabled: tab === "recommended" });
  const status = useMutation({ mutationFn: ({ aid, s }: any) => api(`/employer/applications/${aid}`, { method: "PUT", body: { status: s } }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["emp-vacancy-apps", id] }); toast.success("Статус отклика обновлён"); } });
  if (isLoading || !data) return <PageLoader />;
  const v = data.vacancy;
  return (
    <div className="space-y-5">
      <PageHeader back={{ to: "/e/vacancies", label: "Вакансии" }} title={v.title}
        subtitle={<span className="flex flex-wrap items-center gap-2"><CategoryBadge label={v.category} /><span>{salaryRange(v.salary_from, v.salary_to)}</span>{v.must_skills.map((s: string) => <Badge key={s} tone="brand">{s}</Badge>)}</span>}
        action={<><Button variant="outline" icon={<FlaskConical className="h-4 w-4" />} onClick={() => setPlan(true)}>План теста под вакансию</Button><Button variant="outline" icon={<Pencil className="h-4 w-4" />} onClick={() => setEdit(v)}>Изменить</Button></>} />
      {v.market?.status === "low" && <Alert tone="warn">{v.market.message}</Alert>}
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "applications", label: "Отклики", count: data.items.length }, { id: "recommended", label: "Рекомендованные кандидаты" }, { id: "about", label: "Описание" }]} />
      {tab === "applications" && (data.items.length === 0 ? <Card><EmptyState title="Откликов пока нет" text="Посмотрите рекомендованных кандидатов и пригласите сами." action={<Button onClick={() => setTab("recommended")}>Рекомендации</Button>} /></Card> : (
        <div className="space-y-3">
          {data.items.map((c: any) => (
            <Card key={c.application_id} className="p-4">
              <div className="flex flex-col gap-4 sm:flex-row">
                {c.match_score != null && <ScoreRing value={c.match_score} />}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><Link to={`/e/candidates/${c.id}`} className="text-[16px] font-semibold hover:text-brand-600">{c.contacts?.full_name || c.name}</Link><CategoryBadge label={c.category} /><StatusBadge status={c.status} name={{ sent: "новый", viewed: "просмотрен", interview: "интервью", offer: "оффер", rejected: "отказ" }[c.status as string] ?? c.status} /></div>
                  <div className="mt-1 flex flex-wrap gap-x-4 text-[13px] text-ink-3"><span className="inline-flex items-center gap-1"><Mail className="h-3.5 w-3.5" />{c.contacts?.email}</span>{c.contacts?.telegram && <span>{c.contacts.telegram}</span>}<span>{salaryRange(c.salary_from, c.salary_to)}</span><span>{ago(c.applied_at)}</span></div>
                  <div className="mt-2"><SkillChips verified={c.verified_skills} declared={c.skills} limit={10} /></div>
                  {c.cover_letter && <p className="mt-2 rounded-xl bg-surface p-3 text-[13.5px] text-ink-2">«{c.cover_letter}»</p>}
                  {c.match && <details className="mt-2"><summary className="cursor-pointer text-[13px] text-brand-600">Почему подходит</summary><div className="mt-2"><ExplainPanel match={c.match} compact /></div></details>}
                </div>
                <div className="flex flex-row flex-wrap gap-2 sm:flex-col">
                  {[["interview", "Пригласить на интервью"], ["offer", "Оффер"], ["rejected", "Отказать"]].map(([s, l]) => <Button key={s} size="sm" variant={s === "rejected" ? "ghost" : "outline"} onClick={() => status.mutate({ aid: c.application_id, s })}>{l}</Button>)}
                </div>
              </div>
            </Card>
          ))}
        </div>
      ))}
      {tab === "recommended" && (
        <div className="space-y-3">
          <Alert>Обратная механика для вакансии: система подбирает кандидатов из категории вакансии — пригласите их, не дожидаясь откликов.</Alert>
          {!rec ? <PageLoader /> : rec.items.map((c: any) => <CandidateRow key={c.id} c={c} onInvite={(x) => setInvite([x])} />)}
        </div>
      )}
      {tab === "about" && <Card className="p-5"><p className="whitespace-pre-line text-[14.5px] text-ink-2">{v.description}</p><div className="mt-3 flex flex-wrap gap-2">{v.work_formats.map((f: string) => <Badge key={f}>{FORMAT_NAMES[f]}</Badge>)}</div></Card>}
      <VacancyForm v={edit} onClose={() => setEdit(null)} />
      <TestPlanModal open={plan} onClose={() => setPlan(false)} url={`/employer/vacancies/${id}/test-plan`} />
      <InviteModal open={!!invite} onClose={() => setInvite(null)} candidates={invite ?? []} vacancy={v} />
    </div>
  );
}
