import clsx from "clsx";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, Phone, Send } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Chat } from "@/components/Chat";
import { CategoryBadge, ExplainPanel, StatusBadge } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CardHeader, EmptyState, PageLoader, Tabs } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { ago, dateTime, FORMAT_NAMES, salaryRange } from "@/lib/format";

const STAGES = [["contact", "Знакомство"], ["interview", "Интервью"], ["offer", "Оффер"], ["hired", "Выход на работу"], ["closed", "Закрыто"]];

export default function EmployerInvitations() {
  const { id } = useParams();
  const nav = useNavigate();
  const [tab, setTab] = useState("all");
  const { data, isLoading } = useQuery({ queryKey: ["emp-invitations"], queryFn: () => api("/employer/invitations") });
  if (isLoading) return <PageLoader />;
  const all = data?.items ?? [];
  const items = tab === "all" ? all : all.filter((i: any) => (tab === "waiting" ? ["sent", "viewed"].includes(i.status) : i.status === tab));
  const count = (s: string[]) => all.filter((i: any) => s.includes(i.status)).length;
  const a = data.analytics;
  return (
    <div className="space-y-5">
      <PageHeader title="Приглашения" subtitle="Статусы обновляются в реальном времени: отправлено → просмотрено → принято / отклонено. Контакты кандидата видны после принятия."
        action={<div className="flex gap-4 text-[13px] text-ink-3"><span>Конверсия в принятие: <b className="text-ink">{a.acceptance_rate != null ? `${Math.round(a.acceptance_rate * 100)}%` : "—"}</b></span><span>Медиана ответа: <b className="text-ink">{a.median_response_hours ?? "—"} ч</b></span></div>} />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "all", label: "Все", count: all.length }, { id: "waiting", label: "Ждут ответа", count: count(["sent", "viewed"]) },
        { id: "accepted", label: "Приняты", count: count(["accepted"]) }, { id: "declined", label: "Отклонены", count: count(["declined"]) }, { id: "expired", label: "Истекли", count: count(["expired"]) }]} />
      {all.length === 0 ? <Card><EmptyState icon={<Send />} title="Вы ещё не отправляли приглашений" text="Найдите кандидатов в подборке по потребности или в банке кандидатов." action={<Link to="/e/needs"><Button>К подборкам</Button></Link>} /></Card> : (
        <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
          <Card className="divide-y divide-line overflow-hidden">
            {items.map((i: any) => (
              <button key={i.id} onClick={() => nav(`/e/invitations/${i.id}`)} className={clsx("flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface/70", Number(id) === i.id && "bg-brand-50/60")}>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2"><span className="font-mono text-[13px] font-semibold">{i.candidate?.code}</span><CategoryBadge label={i.candidate?.category ?? ""} /></div>
                  <div className="mt-0.5 truncate text-[13.5px] text-ink-2">{i.title}</div>
                  <div className="text-[12px] text-ink-3">{salaryRange(i.salary_from, i.salary_to)} · {ago(i.created_at)}</div>
                </div>
                <div className="text-right"><StatusBadge status={i.status} name={i.status_name} />{i.stage_name && <div className="mt-1 text-[11.5px] text-ink-3">{i.stage_name}</div>}
                  {i.unread_messages > 0 && <div className="mt-1 inline-block rounded-full bg-brand-500 px-1.5 text-[11px] font-semibold text-white" title="Новые сообщения">{i.unread_messages} нов.</div>}</div>
              </button>
            ))}
          </Card>
          <div className="lg:sticky lg:top-24 lg:self-start">{id ? <Detail id={Number(id)} /> : <Card><EmptyState title="Выберите приглашение" text="Подробности, статус, контакты и этапы найма." /></Card>}</div>
        </div>
      )}
    </div>
  );
}

function Detail({ id }: { id: number }) {
  const qc = useQueryClient();
  const { data: i, isLoading } = useQuery({ queryKey: ["emp-invitation", id], queryFn: () => api(`/employer/invitations/${id}`) });
  const stage = useMutation({ mutationFn: (s: string) => api(`/employer/invitations/${id}/stage`, { method: "PUT", body: { stage: s } }), onSuccess: () => { qc.invalidateQueries(); toast.success("Этап обновлён — кандидат видит изменение"); } });
  const withdraw = useMutation({ mutationFn: () => api(`/employer/invitations/${id}/withdraw`, { method: "POST" }), onSuccess: () => { qc.invalidateQueries(); toast.success("Приглашение отозвано"); }, onError: (e: ApiError) => toast.error(e.message) });
  if (isLoading || !i) return <PageLoader />;
  return (
    <Card className="animate-fade-in">
      <CardHeader title={i.title} subtitle={<>Кандидат <Link className="link" to={`/e/candidates/${i.candidate.id}`}>{i.candidate.code}</Link> · {i.candidate.category}</>} action={<StatusBadge status={i.status} name={i.status_name} />} />
      <div className="space-y-4 px-5 pb-5">
        <div className="flex flex-wrap gap-2 text-[13px]"><Badge tone="dark">{salaryRange(i.salary_from, i.salary_to)}</Badge>{i.work_format && <Badge>{FORMAT_NAMES[i.work_format]}</Badge>}<Badge>до {dateTime(i.expires_at)}</Badge></div>
        <div className="grid gap-2 text-[13px] text-ink-3 sm:grid-cols-3">
          <div>Отправлено<br /><b className="text-ink">{dateTime(i.created_at)}</b></div>
          <div>Просмотрено<br /><b className="text-ink">{i.viewed_at ? dateTime(i.viewed_at) : "—"}</b></div>
          <div>Ответ<br /><b className="text-ink">{i.responded_at ? dateTime(i.responded_at) : "—"}</b></div>
        </div>
        {i.status === "accepted" && i.contacts && (
          <div className="rounded-xl border border-ok-500/30 bg-ok-50 p-4">
            <div className="text-[14px] font-semibold text-ok-700">Кандидат принял приглашение — контакты открыты</div>
            <div className="mt-2 space-y-1 text-[14px]"><div className="font-semibold">{i.contacts.full_name}</div>
              {i.contacts.email && <div className="flex items-center gap-2"><Mail className="h-4 w-4" />{i.contacts.email}</div>}
              {i.contacts.phone && <div className="flex items-center gap-2"><Phone className="h-4 w-4" />{i.contacts.phone}</div>}
              {i.contacts.telegram && <div className="flex items-center gap-2"><Send className="h-4 w-4" />{i.contacts.telegram}</div>}</div>
            {i.candidate_message && <p className="mt-2 text-[13.5px] text-ink-2">«{i.candidate_message}»</p>}
          </div>
        )}
        {i.status === "accepted" && !i.contacts_open && (
          <Alert tone="warn" title="Кандидат закрыл доступ к контактам">Контакты скрыты, в том числе в ATS-выгрузке. Продолжить общение можно в переписке на платформе.</Alert>
        )}
        {i.chat_available && <Chat base={`/employer/invitations/${id}`} counterpart={`кандидатом ${i.candidate.code}`} />}
        {i.status === "accepted" && (
          <div>
            <div className="kicker mb-2">Этап найма (виден кандидату)</div>
            <div className="flex flex-wrap gap-2">{STAGES.map(([s, n]) => <button key={s} onClick={() => stage.mutate(s)} className={clsx("rounded-xl border px-3 py-1.5 text-[13px] font-medium", i.stage === s ? "border-brand-500 bg-brand-500 text-white" : "border-line hover:border-brand-300")}>{n}</button>)}</div>
          </div>
        )}
        {i.status === "declined" && <Alert tone="danger" title={`Отказ: ${i.decline_reason_name}`}>{i.decline_comment}</Alert>}
        {["sent", "viewed"].includes(i.status) && <Alert>Кандидат видит условия и способ связи; ваши данные о нём ограничены профилем до принятия приглашения.</Alert>}
        <div><div className="kicker mb-1.5">Описание</div><p className="whitespace-pre-line text-[14px] text-ink-2">{i.description}</p></div>
        {i.explanation?.components && <div className="rounded-xl bg-surface p-4"><div className="kicker mb-3">Соответствие на момент приглашения: {Math.round(i.match_score)}</div><ExplainPanel match={i.explanation} compact /></div>}
        {["sent", "viewed"].includes(i.status) && <Button variant="danger" loading={withdraw.isPending} onClick={() => withdraw.mutate()}>Отозвать приглашение</Button>}
      </div>
    </Card>
  );
}
