import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, ClipboardCheck, Lightbulb, Star } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { StatusBadge } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CardHeader, EmptyState, PageLoader, Stat, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { date } from "@/lib/format";

const ST: Record<string, string> = { submitted: "На проверке", reviewed: "Оценено", expired: "Просрочено", skipped: "Пропущено" };

export default function Tasks() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["cand-tasks"], queryFn: () => api("/candidate/tasks") });
  const [answer, setAnswer] = useState("");
  const req = useMutation({ mutationFn: () => api("/candidate/tasks/request", { method: "POST" }), onSuccess: () => qc.invalidateQueries({ queryKey: ["cand-tasks"] }), onError: (e: ApiError) => toast.error(e.message) });
  const submit = useMutation({
    mutationFn: () => api(`/candidate/tasks/${data.current.id}/submit`, { body: { answer } }),
    onSuccess: (r: any) => { toast.success("Решение отправлено", { description: `Предварительная автопроверка: ${Math.round((r.auto_score ?? 0) * 100)}%. Итоговую оценку поставит работодатель.` }); setAnswer(""); qc.invalidateQueries(); },
    onError: (e: ApiError) => toast.error(e.message),
  });
  const skip = useMutation({ mutationFn: () => api(`/candidate/tasks/${data.current.id}/skip`, { method: "POST" }), onSuccess: () => qc.invalidateQueries() });
  if (isLoading || !data) return <PageLoader />;
  const cur = data.current;
  return (
    <div className="space-y-6">
      <PageHeader title="Регулярные задачи" subtitle="Раз в неделю система предлагает короткую задачу от работодателя вашей категории: решите её или опишите подход. Оценки повышают актуальность профиля и дают компаниям свежий сигнал." />
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Решено и оценено" value={data.tasks_done ?? 0} />
        <Stat label="Средняя оценка" value={data.task_score ? data.task_score.toFixed(1) : "—"} hint="байесовское среднее по 5-балльной шкале" />
        <Stat label="Влияние на выдачу" value="+актуальность" hint="компонент «Актуальность» в ранжировании" accent />
      </div>
      {!data.available ? (
        <Card><EmptyState icon={<ClipboardCheck />} title="Задачи доступны после присвоения категории" action={<Link to="/c/assessment"><Button>Пройти тест</Button></Link>} /></Card>
      ) : cur ? (
        <Card>
          <CardHeader icon={<Lightbulb className="h-5 w-5" />} title={cur.task.title}
            subtitle={<>{cur.task.company} · ~{cur.task.est_minutes} мин · {cur.task.kind === "approach" ? "предложите подход к решению" : "решите задачу"}</>}
            action={<Badge tone="warn" icon={<CalendarClock className="h-3 w-3" />}>до {date(cur.due_at)}</Badge>} />
          <div className="space-y-4 px-5 pb-5">
            <p className="whitespace-pre-line rounded-xl bg-surface p-4 text-[14.5px] leading-relaxed">{cur.task.description}</p>
            {cur.task.skills?.length > 0 && <div className="flex flex-wrap gap-1.5">{cur.task.skills.map((s: string) => <Badge key={s} tone="brand">{s}</Badge>)}</div>}
            <Textarea rows={8} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Опишите решение: ключевые шаги, компромиссы, как проверите результат. Можно приложить код." />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-[12.5px] text-ink-3">{answer.length} символов · рекомендуем от 300</span>
              <div className="flex gap-2"><Button variant="ghost" onClick={() => skip.mutate()}>Пропустить</Button><Button disabled={answer.trim().length < 30} loading={submit.isPending} onClick={() => submit.mutate()}>Отправить решение</Button></div>
            </div>
          </div>
        </Card>
      ) : (
        <Card><EmptyState icon={<ClipboardCheck />} title="Активной задачи нет" text="Новая задача появится автоматически в течение недели. Можно запросить её прямо сейчас." action={<Button loading={req.isPending} onClick={() => req.mutate()}>Получить задачу</Button>} /></Card>
      )}
      {data.history?.length > 0 && (
        <Card>
          <CardHeader title="История" />
          <div className="divide-y divide-line">
            {data.history.map((a: any) => (
              <div key={a.id} className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1"><div className="font-medium">{a.task.title}</div><div className="text-[12.5px] text-ink-3">{a.task.company} · {date(a.submitted_at || a.assigned_at)}</div>{a.feedback && <div className="mt-1 text-[13px] text-ink-2">«{a.feedback}»</div>}</div>
                <div className="flex items-center gap-2">
                  {a.score && <span className="inline-flex items-center gap-1 font-mono font-bold"><Star className="h-4 w-4 fill-warn-500 text-warn-500" />{a.score}/5</span>}
                  <StatusBadge status={a.status} name={ST[a.status] ?? a.status} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
      <Alert tone="brand">Задачи составляют работодатели. Автор сильного решения часто получает приглашение от компании-автора задачи.</Alert>
    </div>
  );
}
