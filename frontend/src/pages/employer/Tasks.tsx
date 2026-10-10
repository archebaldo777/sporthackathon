import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardCheck, Plus, Send, Star } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { CategoryBadge, InviteModal, StatusBadge } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, ChoiceChips, EmptyState, Field, Input, Meter, Modal, PageLoader, Select, TagInput, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { ago } from "@/lib/format";

export default function EmployerTasks() {
  const { id } = useParams();
  return id ? <TaskDetail id={Number(id)} /> : <TaskList />;
}

function TaskList() {
  const { data, isLoading } = useQuery({ queryKey: ["emp-tasks"], queryFn: () => api("/employer/tasks") });
  const [open, setOpen] = useState(false);
  if (isLoading) return <PageLoader />;
  return (
    <div>
      <PageHeader title="Задачи для кандидатов" subtitle="Короткие задачи, которые система раз в неделю предлагает кандидатам нужной категории. Вы получаете свежий сигнал о людях и видите, кто решает ваши задачи лучше всех."
        action={<Button icon={<Plus className="h-4 w-4" />} onClick={() => setOpen(true)}>Новая задача</Button>} />
      {(data?.items ?? []).length === 0 ? <Card><EmptyState icon={<ClipboardCheck />} title="Задач нет" action={<Button onClick={() => setOpen(true)}>Создать задачу</Button>} /></Card> : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.items.map((t: any) => (
            <Link key={t.id} to={`/e/tasks/${t.id}`} className="card block p-5 transition hover:border-brand-300">
              <div className="flex items-start justify-between gap-3"><h3 className="font-sans text-[16px] font-semibold">{t.title}</h3>{t.stats.submitted ? <Badge tone="warn">на проверке: {t.stats.submitted}</Badge> : null}</div>
              <p className="mt-1.5 line-clamp-2 text-[13.5px] text-ink-3">{t.description}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-[12.5px] text-ink-3"><Badge tone="dark">{t.specialization}</Badge><span>назначено: {Object.values(t.stats).reduce((a: number, b: any) => a + b, 0) as number}</span><span>оценено: {t.stats.reviewed ?? 0}</span></div>
            </Link>
          ))}
        </div>
      )}
      <TaskForm open={open} onClose={() => setOpen(false)} />
    </div>
  );
}

function TaskForm({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: cat } = useCatalog();
  const qc = useQueryClient();
  const [f, setF] = useState<any>({ title: "", description: "", specialization: "backend", grades: ["junior", "middle", "senior"], kind: "approach", est_minutes: 30, key_points: [], skills: [] });
  const save = useMutation({ mutationFn: () => api("/employer/tasks", { body: { ...f, est_minutes: Number(f.est_minutes) } }), onSuccess: () => { toast.success("Задача создана — система начнёт предлагать её кандидатам"); qc.invalidateQueries(); onClose(); }, onError: (e: ApiError) => toast.error(e.message) });
  if (!cat) return null;
  return (
    <Modal open={open} onClose={onClose} wide title="Новая короткая задача" footer={<><Button variant="ghost" onClick={onClose}>Отмена</Button><Button loading={save.isPending} onClick={() => save.mutate()}>Создать</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Название" className="sm:col-span-2"><Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Условие" className="sm:col-span-2"><Textarea rows={4} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        <Field label="Специализация"><Select value={f.specialization} onChange={(e) => setF({ ...f, specialization: e.target.value })}>{cat.specializations.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}</Select></Field>
        <Field label="Формат ответа"><ChoiceChips options={[{ code: "approach", name: "Подход к решению" }, { code: "solution", name: "Решение" }]} value={f.kind} onChange={(v) => setF({ ...f, kind: v })} /></Field>
        <Field label="Для грейдов" className="sm:col-span-2"><ChoiceChips multi options={cat.grades} value={f.grades} onChange={(v) => setF({ ...f, grades: v })} /></Field>
        <Field label="Скрытая рубрика: ключевые пункты" hint="Используются для автоматической предварительной оценки, кандидат их не видит" className="sm:col-span-2"><TagInput value={f.key_points} onChange={(v) => setF({ ...f, key_points: v })} placeholder="идемпотентность, ретраи…" /></Field>
        <Field label="Проверяемые навыки"><TagInput value={f.skills} onChange={(v) => setF({ ...f, skills: v })} suggestions={cat.skills.map((s) => s.name)} /></Field>
        <Field label="Время на решение, мин"><Input type="number" value={f.est_minutes} onChange={(e) => setF({ ...f, est_minutes: e.target.value })} /></Field>
      </div>
    </Modal>
  );
}

function TaskDetail({ id }: { id: number }) {
  const qc = useQueryClient();
  const { data: t, isLoading } = useQuery({ queryKey: ["emp-task", id], queryFn: () => api(`/employer/tasks/${id}`) });
  const [scores, setScores] = useState<Record<number, { score: number; feedback: string }>>({});
  const [invite, setInvite] = useState<any[] | null>(null);
  const review = useMutation({ mutationFn: ({ aid, score, feedback }: any) => api(`/employer/tasks/${id}/submissions/${aid}/review`, { body: { score, feedback } }), onSuccess: () => { toast.success("Оценка сохранена — профиль кандидата обновлён"); qc.invalidateQueries(); } });
  if (isLoading || !t) return <PageLoader />;
  return (
    <div className="space-y-5">
      <PageHeader back={{ to: "/e/tasks", label: "Задачи" }} title={t.title} subtitle={t.description} />
      {t.key_points?.length > 0 && <Alert>Рубрика автопроверки: {t.key_points.join(" · ")}</Alert>}
      {t.submissions.length === 0 ? <Card><EmptyState icon={<ClipboardCheck />} title="Решений пока нет" text="Система назначает задачу кандидатам категории раз в неделю." /></Card> : t.submissions.map((s: any) => (
        <Card key={s.id} className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2"><Link to={`/e/candidates/${s.candidate.id}`} className="font-semibold hover:text-brand-600">{s.candidate.name}</Link><CategoryBadge label={s.candidate.category} /><span className="text-[12.5px] text-ink-3">{ago(s.submitted_at)}</span></div>
            <div className="flex items-center gap-3">
              <div className="w-40"><div className="mb-1 text-[11.5px] text-ink-3">Автопроверка {Math.round((s.auto_score ?? 0) * 100)}%</div><Meter value={s.auto_score ?? 0} /></div>
              <StatusBadge status={s.status} name={s.status === "reviewed" ? `оценено ${s.score}/5` : "ждёт оценки"} />
            </div>
          </div>
          <p className="mt-3 whitespace-pre-line rounded-xl bg-surface p-4 text-[14px]">{s.answer}</p>
          {s.auto_details?.missing?.length > 0 && <div className="mt-2 text-[12.5px] text-ink-3">Не раскрыто по рубрике: {s.auto_details.missing.join(", ")}</div>}
          {s.auto_details?.similar?.length > 0 && (
            <div className="mt-2 rounded-lg bg-warn-50 px-3 py-2 text-[12.5px] text-warn-700">
              Возможное списывание: почти совпадает с решением {s.auto_details.similar.map((x: any) => `${x.candidate_code} (${x.similarity}%)`).join(", ")}
            </div>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <div className="flex gap-1">{[1, 2, 3, 4, 5].map((n) => (
              <button key={n} aria-label={`${n} из 5`} onClick={() => setScores({ ...scores, [s.id]: { score: n, feedback: scores[s.id]?.feedback ?? "" } })}>
                <Star className={"h-6 w-6 " + ((scores[s.id]?.score ?? s.score ?? 0) >= n ? "fill-warn-500 text-warn-500" : "text-ink-4")} />
              </button>
            ))}</div>
            <Input className="max-w-sm" placeholder="Комментарий кандидату" value={scores[s.id]?.feedback ?? s.feedback ?? ""} onChange={(e) => setScores({ ...scores, [s.id]: { score: scores[s.id]?.score ?? s.score ?? 3, feedback: e.target.value } })} />
            <Button size="sm" disabled={!scores[s.id]} onClick={() => review.mutate({ aid: s.id, ...scores[s.id] })}>Сохранить оценку</Button>
            {(s.score ?? scores[s.id]?.score ?? 0) >= 4 && <Button size="sm" variant="secondary" icon={<Send className="h-4 w-4" />} onClick={() => setInvite([{ id: s.candidate.id, name: s.candidate.name }])}>Пригласить автора</Button>}
          </div>
        </Card>
      ))}
      <InviteModal open={!!invite} onClose={() => setInvite(null)} candidates={invite ?? []} />
    </div>
  );
}
