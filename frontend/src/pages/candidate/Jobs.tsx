import clsx from "clsx";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Briefcase, CheckCircle2, MapPin, Search, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { CategoryBadge, ExplainPanel } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CompanyMark, EmptyState, Field, Input, Modal, PageLoader, ScoreRing, Select, Textarea, Toggle } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useCatalog } from "@/lib/catalog";
import { ago, FORMAT_NAMES, GRADE_NAMES, salaryRange } from "@/lib/format";

export default function Jobs({ publicMode }: { publicMode?: boolean }) {
  const { id } = useParams();
  const nav = useNavigate();
  const { data: cat } = useCatalog();
  const { user } = useAuth();
  const isCand = user?.role === "candidate";
  const [flt, setFlt] = useState<any>({ specialization: "", grade: "", format: "", q: "", mine: isCand && !publicMode });
  const { data, isLoading } = useQuery({ queryKey: ["vacancies", flt], queryFn: () => api("/vacancies", { query: { ...flt, limit: 60 } }) });
  const base = publicMode ? "/jobs" : "/c/jobs";
  const items = data?.items ?? [];
  const activeId = id ? Number(id) : null;
  const body = (
    <div className={publicMode ? "mx-auto max-w-7xl px-4 py-10 sm:px-6" : ""}>
      <PageHeader title="Вакансии" subtitle={isCand ? "Дополнительный сценарий: пока приглашений нет, можно проявить инициативу. Вакансии отсортированы по соответствию вашему подтверждённому профилю." : "Опубликованные вакансии компаний. Вилка зарплаты указана всегда."} />
      <Card className="mb-5 p-4">
        <div className="grid gap-3 md:grid-cols-[1.4fr_1fr_1fr_1fr_auto] md:items-end">
          <Field label="Поиск"><div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-4" /><Input className="pl-9" value={flt.q} onChange={(e) => setFlt({ ...flt, q: e.target.value })} placeholder="Название, навык…" /></div></Field>
          <Field label="Специализация"><Select value={flt.specialization} onChange={(e) => setFlt({ ...flt, specialization: e.target.value })}><option value="">Все</option>{cat?.specializations.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}</Select></Field>
          <Field label="Грейд"><Select value={flt.grade} onChange={(e) => setFlt({ ...flt, grade: e.target.value })}><option value="">Любой</option>{cat?.grades.map((g) => <option key={g.code} value={g.code}>{g.name}</option>)}</Select></Field>
          <Field label="Формат"><Select value={flt.format} onChange={(e) => setFlt({ ...flt, format: e.target.value })}><option value="">Любой</option>{Object.entries(FORMAT_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
          {isCand && !publicMode && <div className="pb-2"><Toggle checked={flt.mine} onChange={(v) => setFlt({ ...flt, mine: v })} label="Моя специализация" /></div>}
        </div>
      </Card>
      {isLoading ? <PageLoader /> : items.length === 0 ? <Card><EmptyState icon={<Briefcase />} title="Вакансий не найдено" text="Измените фильтры." /></Card> : (
        <div className="grid gap-5 lg:grid-cols-[1fr_1.15fr]">
          <div className="space-y-3">
            <div className="text-[13px] text-ink-3">Найдено: {data.total}</div>
            {items.map((v: any) => (
              <button key={v.id} onClick={() => nav(`${base}/${v.id}`)} className={clsx("w-full rounded-2xl border bg-white p-4 text-left transition", activeId === v.id ? "border-brand-500 shadow-lift" : "border-line hover:border-brand-200")}>
                <div className="flex items-start gap-3">
                  <CompanyMark name={v.company.name} accent={v.company.accent} size={40} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] text-ink-3">{v.company.name}</div>
                    <div className="text-[15px] font-semibold leading-snug">{v.title}</div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2"><CategoryBadge label={v.category} /><span className="num text-[13.5px] font-semibold text-brand-700">{salaryRange(v.salary_from, v.salary_to)}</span>
                      {v.applied && <Badge tone="ok">вы откликнулись</Badge>}</div>
                  </div>
                  {v.match && <ScoreRing value={v.match.score} size={48} label="Соответствие вашему профилю" />}
                </div>
              </button>
            ))}
          </div>
          <div className="lg:sticky lg:top-24 lg:self-start">{activeId ? <JobDetail id={activeId} publicMode={publicMode} /> : <Card><EmptyState icon={<Briefcase />} title="Выберите вакансию" text="Слева — список; здесь появятся подробности и оценка соответствия." /></Card>}</div>
        </div>
      )}
    </div>
  );
  return body;
}

function JobDetail({ id, publicMode }: { id: number; publicMode?: boolean }) {
  const qc = useQueryClient();
  const { user } = useAuth();
  const nav = useNavigate();
  const { data: v, isLoading } = useQuery({ queryKey: ["vacancy", id], queryFn: () => api(`/vacancies/${id}`) });
  const [open, setOpen] = useState(false);
  const [letter, setLetter] = useState("");
  const apply = useMutation({
    mutationFn: () => api("/candidate/applications", { body: { vacancy_id: id, cover_letter: letter || null } }),
    onSuccess: () => { toast.success("Отклик отправлен — работодатель увидит ваш верифицированный профиль и контакты"); setOpen(false); qc.invalidateQueries(); },
    onError: (e: ApiError) => toast.error(e.message),
  });
  if (isLoading || !v) return <PageLoader />;
  const canApply = user?.role === "candidate";
  return (
    <Card className="animate-fade-in">
      <div className="border-b border-line p-6">
        <div className="flex items-center gap-3"><CompanyMark name={v.company.name} accent={v.company.accent} /><div><div className="text-[14px] font-medium">{v.company.name}</div><div className="flex items-center gap-1 text-[12.5px] text-ink-3"><ShieldCheck className="h-3.5 w-3.5" />Индекс доверия {v.company.trust_score}</div></div></div>
        <h2 className="mt-4 font-sans text-[22px] font-bold leading-tight">{v.title}</h2>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <CategoryBadge label={v.category} large />
          <span className="rounded-lg bg-night px-3 py-1.5 font-mono text-[15px] font-bold text-white">{salaryRange(v.salary_from, v.salary_to)}</span>
          {v.work_formats?.map((f: string) => <Badge key={f}>{FORMAT_NAMES[f]}</Badge>)}
          {v.city && <span className="inline-flex items-center gap-1 text-[13px] text-ink-3"><MapPin className="h-3.5 w-3.5" />{v.city}</span>}
        </div>
      </div>
      <div className="space-y-5 p-6">
        {v.match && (
          <div className="rounded-xl border border-brand-100 bg-brand-50/40 p-4">
            <div className="mb-3 flex items-center gap-3"><ScoreRing value={v.match.score} size={44} /><div className="text-[14px] font-semibold">Соответствие вашему подтверждённому профилю</div></div>
            <ExplainPanel match={v.match} compact />
          </div>
        )}
        <div>
          <div className="kicker mb-2">Требования</div>
          <div className="flex flex-wrap gap-1.5">{v.must_skills.map((s: string) => <Badge key={s} tone="brand">{s}</Badge>)}{v.nice_skills.map((s: string) => <Badge key={s}>{s} · плюс</Badge>)}</div>
        </div>
        <p className="whitespace-pre-line text-[14.5px] leading-relaxed text-ink-2">{v.description}</p>
        <div className="text-[12.5px] text-ink-3">Опубликовано {ago(v.created_at)} · грейд {GRADE_NAMES[v.grade]}</div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface/50 px-6 py-4">
        <span className="text-[12.5px] text-ink-3">При отклике работодатель сразу видит ваши контакты</span>
        {v.applied ? <Badge tone="ok" icon={<CheckCircle2 className="h-3.5 w-3.5" />}>Вы откликнулись</Badge> : canApply ? <Button onClick={() => setOpen(true)}>Откликнуться</Button>
          : <Button onClick={() => nav(`/login?next=/c/jobs/${id}`)}>Войти, чтобы откликнуться</Button>}
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title="Отклик на вакансию"
        footer={<><Button variant="ghost" onClick={() => setOpen(false)}>Отмена</Button><Button loading={apply.isPending} onClick={() => apply.mutate()}>Отправить отклик</Button></>}>
        <Alert tone="brand">Работодатель увидит вашу категорию, подтверждённые навыки, достижения ФСП и контакты.</Alert>
        <Field label="Сопроводительное письмо (необязательно)" className="mt-4"><Textarea rows={4} value={letter} onChange={(e) => setLetter(e.target.value)} /></Field>
      </Modal>
    </Card>
  );
}
