import clsx from "clsx";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Flag, Inbox, MapPin, MessageSquare, ShieldCheck, Wallet } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { StatusBadge } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CompanyMark, EmptyState, Field, Modal, PageLoader, Select, Tabs, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { Chat } from "@/components/Chat";
import { useCatalog } from "@/lib/catalog";
import { ago, dateTime, FORMAT_NAMES, salaryRange } from "@/lib/format";

export default function CandidateInvitations() {
  const { id } = useParams();
  const nav = useNavigate();
  const [tab, setTab] = useState<"active" | "all">("active");
  const { data, isLoading } = useQuery({ queryKey: ["cand-invitations"], queryFn: () => api("/candidate/invitations") });
  if (isLoading) return <PageLoader />;
  const items = (data?.items ?? []).filter((i: any) => tab === "all" || ["sent", "viewed", "accepted"].includes(i.status));
  const activeId = id ? Number(id) : items[0]?.id;
  return (
    <div>
      <PageHeader title="Приглашения" subtitle="Компании нашли вас в категории и предлагают конкретные условия. Зарплата и способ связи видны сразу; ваши контакты откроются только после принятия." />
      {(data?.items ?? []).length === 0 ? (
        <Card><EmptyState icon={<Inbox />} title="Пока нет приглашений" text="Работодатели ищут кандидатов по категориям. Подтвердите грейд, свяжите ФСП ID и решайте регулярные задачи — это поднимает вас в выдаче."
          action={<Link to="/c/assessment"><Button>К тестированию</Button></Link>} /></Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
          <div className="space-y-3">
            <Tabs value={tab} onChange={setTab} tabs={[{ id: "active", label: "Актуальные" }, { id: "all", label: "Все", count: data.items.length }]} />
            {items.map((i: any) => (
              <button key={i.id} onClick={() => nav(`/c/invitations/${i.id}`)}
                className={clsx("w-full rounded-2xl border bg-white p-4 text-left transition", activeId === i.id ? "border-brand-500 shadow-lift" : "border-line hover:border-brand-200")}>
                <div className="flex items-start gap-3">
                  <CompanyMark name={i.company.name} accent={i.company.accent} size={36} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-[13px] text-ink-3">{i.company.name}</span>
                      {i.status === "sent" && <span className="h-2 w-2 shrink-0 rounded-full bg-accent-500" />}
                      {i.unread_messages > 0 && <span className="shrink-0 rounded-full bg-brand-500 px-1.5 text-[11px] font-semibold text-white" title="Новые сообщения">{i.unread_messages}</span>}
                    </div>
                    <div className="truncate text-[14.5px] font-semibold">{i.title}</div>
                    <div className="mt-1.5 flex items-center justify-between gap-2">
                      <span className="num text-[13.5px] font-semibold text-brand-700">{salaryRange(i.salary_from, i.salary_to)}</span>
                      <StatusBadge status={i.status} name={i.status_name} />
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
          {activeId ? <InvitationDetail id={activeId} /> : <Card><EmptyState title="Выберите приглашение" /></Card>}
        </div>
      )}
    </div>
  );
}

function InvitationDetail({ id }: { id: number }) {
  const qc = useQueryClient();
  const { data: cat } = useCatalog();
  const { data: inv, isLoading } = useQuery({ queryKey: ["cand-invitation", id], queryFn: () => api(`/candidate/invitations/${id}`) });
  const [modal, setModal] = useState<null | "accept" | "decline" | "report">(null);
  const [msg, setMsg] = useState("");
  const [reason, setReason] = useState("salary");
  const done = () => { setModal(null); setMsg(""); qc.invalidateQueries(); };
  const accept = useMutation({ mutationFn: () => api(`/candidate/invitations/${id}/accept`, { body: { message: msg || null } }), onSuccess: () => { toast.success("Приглашение принято — работодатель получил ваши контакты"); done(); }, onError: (e: ApiError) => toast.error(e.message) });
  const decline = useMutation({ mutationFn: () => api(`/candidate/invitations/${id}/decline`, { body: { reason, comment: msg || null } }), onSuccess: () => { toast.success("Вы отклонили приглашение. Спасибо за обратную связь!"); done(); }, onError: (e: ApiError) => toast.error(e.message) });
  const access = useMutation({
    mutationFn: (revoked: boolean) => api(`/candidate/invitations/${id}/contacts`, { body: { revoked } }),
    onSuccess: (r: any) => { toast.success(r.contacts_open ? "Контакты снова открыты работодателю" : "Доступ к контактам закрыт — переписка на платформе остаётся"); qc.invalidateQueries(); },
    onError: (e: ApiError) => toast.error(e.message),
  });
  const report = useMutation({ mutationFn: () => api(`/candidate/invitations/${id}/report`, { body: { reason, comment: msg || null } }), onSuccess: () => { toast.success("Жалоба отправлена модераторам"); done(); } });
  if (isLoading || !inv) return <PageLoader />;
  const open = ["sent", "viewed"].includes(inv.status);
  const steps = [
    { label: "Отправлено", at: inv.created_at, on: true },
    { label: "Просмотрено", at: inv.viewed_at, on: !!inv.viewed_at },
    { label: inv.status === "declined" ? "Отклонено" : inv.status === "expired" ? "Истекло" : inv.status === "withdrawn" ? "Отозвано" : "Принято", at: inv.responded_at, on: ["accepted", "declined"].includes(inv.status) },
    ...(inv.stage ? [{ label: `Этап: ${inv.stage_name}`, at: null, on: true }] : []),
  ];
  return (
    <Card className="animate-fade-in overflow-hidden">
      <div className="border-b border-line p-6">
        <div className="flex items-start gap-4">
          <CompanyMark name={inv.company.name} accent={inv.company.accent} size={52} />
          <div className="min-w-0 flex-1">
            <div className="text-[14px] text-ink-3">{inv.company.name}{inv.company.city ? ` · ${inv.company.city}` : ""}</div>
            <h2 className="mt-0.5 font-sans text-[22px] font-bold leading-tight">{inv.title}</h2>
            <div className="mt-2 flex flex-wrap gap-2">
              <StatusBadge status={inv.status} name={inv.status_name} />
              <Badge tone={inv.company.trust_score >= 70 ? "ok" : inv.company.trust_score >= 45 ? "warn" : "danger"} icon={<ShieldCheck className="h-3 w-3" />}>Индекс доверия {inv.company.trust_score}</Badge>
              <span className="text-[12.5px] text-ink-3">получено {ago(inv.created_at)}</span>
            </div>
          </div>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl bg-night p-4 text-white sm:col-span-2">
            <div className="kicker flex items-center gap-1.5 text-white/50"><Wallet className="h-3.5 w-3.5" />Зарплата</div>
            <div className="mt-1 font-mono text-[26px] font-bold">{salaryRange(inv.salary_from, inv.salary_to)}</div>
          </div>
          <div className="rounded-xl bg-surface p-4">
            <div className="kicker">Формат</div>
            <div className="mt-1.5 text-[15px] font-semibold">{inv.work_format ? FORMAT_NAMES[inv.work_format] : "не указан"}</div>
            {inv.city && <div className="mt-0.5 inline-flex items-center gap-1 text-[12.5px] text-ink-3"><MapPin className="h-3.5 w-3.5" />{inv.city}</div>}
          </div>
        </div>
      </div>
      <div className="space-y-5 p-6">
        {inv.risk_flags?.length > 0 && <Alert tone="warn" icon={<AlertTriangle className="h-4 w-4" />} title="Будьте внимательны">{inv.risk_flags.map((f: any) => f.message).join("; ")}</Alert>}
        {inv.why_you?.length > 0 && (
          <div className="rounded-xl border border-brand-100 bg-brand-50/50 p-4">
            <div className="text-[13px] font-semibold text-brand-800">Почему компания выбрала вас</div>
            <ul className="mt-2 space-y-1">{inv.why_you.map((r: string, i: number) => <li key={i} className="flex gap-2 text-[13.5px] text-ink-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />{r}</li>)}</ul>
          </div>
        )}
        <div>
          <div className="kicker mb-2">Описание предложения</div>
          <p className="whitespace-pre-line text-[14.5px] leading-relaxed text-ink-2">{inv.description}</p>
        </div>
        <div className="rounded-xl border border-line p-4">
          <div className="kicker mb-1.5">Способ связи с работодателем</div>
          <div className="text-[14.5px] font-medium">{inv.contact_method}</div>
          {inv.company.description && <p className="mt-3 text-[13px] text-ink-3">{inv.company.description}</p>}
        </div>
        <div>
          <div className="kicker mb-3">Статус</div>
          <ol className="flex flex-wrap gap-x-6 gap-y-2">
            {steps.map((s, i) => (
              <li key={i} className={clsx("flex items-center gap-2 text-[13px]", s.on ? "text-ink" : "text-ink-4")}>
                <span className={clsx("h-2.5 w-2.5 rounded-full", s.on ? "bg-brand-500" : "bg-line")} />{s.label}{s.at && <span className="text-ink-3">· {dateTime(s.at)}</span>}
              </li>
            ))}
          </ol>
        </div>
        {inv.status === "accepted" && (inv.contacts_open
          ? <Alert tone="ok" icon={<CheckCircle2 className="h-4 w-4" />} title="Вы приняли приглашение">Работодатель видит ваши контакты и свяжется с вами. Вы тоже можете написать: {inv.contact_method} — или в переписке ниже.
              <div className="mt-2"><Button size="sm" variant="outline" loading={access.isPending} onClick={() => access.mutate(true)}>Закрыть доступ к контактам</Button></div></Alert>
          : <Alert tone="warn" title="Доступ к контактам закрыт">Работодатель больше не видит ваши ФИО, телефон и e-mail (в том числе в выгрузке для ATS). Общение возможно в переписке на платформе.
              <div className="mt-2"><Button size="sm" variant="outline" loading={access.isPending} onClick={() => access.mutate(false)}>Снова открыть контакты</Button></div></Alert>)}
        {inv.chat_available && <Chat base={`/candidate/invitations/${id}`} counterpart={`«${inv.company.name}»`} />}
        {inv.status === "declined" && <Alert tone="danger">Вы отклонили приглашение: {inv.decline_reason_name}</Alert>}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface/50 px-6 py-4">
        <button onClick={() => { setReason("fake"); setModal("report"); }} className="inline-flex items-center gap-1.5 text-[13px] text-ink-3 hover:text-accent-600"><Flag className="h-4 w-4" />Пожаловаться</button>
        {open && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => { setReason("salary"); setModal("decline"); }}>Отклонить</Button>
            <Button onClick={() => setModal("accept")}>Принять и открыть контакты</Button>
          </div>
        )}
      </div>

      <Modal open={modal === "accept"} onClose={() => setModal(null)} title="Принять приглашение"
        footer={<><Button variant="ghost" onClick={() => setModal(null)}>Отмена</Button><Button loading={accept.isPending} onClick={() => accept.mutate()}>Принять</Button></>}>
        <Alert tone="brand" icon={<MessageSquare className="h-4 w-4" />}>«{inv.company.name}» получит ваши контакты: ФИО, e-mail, телефон, Telegram.</Alert>
        <Field label="Сообщение работодателю (необязательно)" className="mt-4"><Textarea rows={3} value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="Удобное время для созвона, вопросы по задачам…" /></Field>
      </Modal>
      <Modal open={modal === "decline"} onClose={() => setModal(null)} title="Отклонить приглашение"
        footer={<><Button variant="ghost" onClick={() => setModal(null)}>Отмена</Button><Button variant="danger" loading={decline.isPending} onClick={() => decline.mutate()}>Отклонить</Button></>}>
        <p className="text-[14px] text-ink-3">Причина поможет работодателю сделать более точные предложения. Контакты не передаются.</p>
        <Field label="Причина" className="mt-4"><Select value={reason} onChange={(e) => setReason(e.target.value)}>{cat?.decline_reasons.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}</Select></Field>
        <Field label="Комментарий (необязательно)" className="mt-3"><Textarea rows={2} value={msg} onChange={(e) => setMsg(e.target.value)} /></Field>
      </Modal>
      <Modal open={modal === "report"} onClose={() => setModal(null)} title="Пожаловаться на приглашение"
        footer={<><Button variant="ghost" onClick={() => setModal(null)}>Отмена</Button><Button variant="danger" loading={report.isPending} onClick={() => report.mutate()}>Отправить жалобу</Button></>}>
        <Field label="Что не так?">
          <Select value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="fake">Фиктивная вакансия</option><option value="payment">Просят оплату или личные данные</option>
            <option value="spam">Спам / массовая рассылка</option><option value="rude">Некорректное общение</option><option value="other">Другое</option>
          </Select>
        </Field>
        <Field label="Комментарий" className="mt-3"><Textarea rows={2} value={msg} onChange={(e) => setMsg(e.target.value)} /></Field>
      </Modal>
    </Card>
  );
}
