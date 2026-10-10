import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Map, Plus, Send, ShieldCheck, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { StatusBadge } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Meter, PageLoader, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { ago, salaryRange } from "@/lib/format";

export default function EmployerDashboard() {
  const { data, isLoading } = useQuery({ queryKey: ["emp-dashboard"], queryFn: () => api("/employer/dashboard") });
  const { data: needs } = useQuery({ queryKey: ["emp-needs"], queryFn: () => api("/employer/needs") });
  if (isLoading || !data) return <PageLoader />;
  const a = data.analytics;
  const funnel = [
    { name: "Отправлено", v: a.total },
    { name: "Просмотрено", v: Math.round((a.view_rate ?? 0) * a.total) },
    { name: "Принято", v: a.by_status.accepted ?? 0 },
    { name: "Интервью+", v: (a.pipeline.interview ?? 0) + (a.pipeline.offer ?? 0) + (a.pipeline.hired ?? 0) },
  ];
  return (
    <div className="space-y-6">
      <PageHeader title={data.company.name} subtitle="Опишите, кто нужен, — система соберёт подборку по категориям и объяснит выбор. Приглашайте конкретных людей с вилкой зарплаты."
        action={<><Link to="/e/talent"><Button variant="outline" icon={<Map className="h-4 w-4" />}>Карта категорий</Button></Link><Link to="/e/needs/new"><Button icon={<Plus className="h-4 w-4" />}>Описать потребность</Button></Link></>} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Активные потребности" value={data.needs} hint="подборки обновляются автоматически" />
        <Stat label="Приглашений отправлено" value={a.total} hint={`ждут ответа: ${(a.by_status.sent ?? 0) + (a.by_status.viewed ?? 0)}`} />
        <Stat label="Принимают приглашения" value={a.acceptance_rate != null ? `${Math.round(a.acceptance_rate * 100)}%` : "—"} hint="от отвеченных" accent />
        <Stat label="Новые отклики / решения" value={`${data.new_applications} / ${data.submissions_to_review}`} hint="на вакансии / на задачи" />
      </div>
      {data.company.trust_score < 70 && (
        <Alert tone="warn" icon={<ShieldCheck className="h-4 w-4" />} title={`Индекс доверия ${data.company.trust_score} — лимит ${data.company.daily_invite_limit} приглашений в сутки`}>
          Заполните профиль компании, укажите ИНН и корпоративную почту на домене сайта, чтобы повысить доверие кандидатов и лимит. <Link to="/e/company" className="link">Профиль компании →</Link>
        </Alert>
      )}
      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <Card>
          <CardHeader icon={<Sparkles className="h-5 w-5" />} title="Потребности и подборки" action={<Link to="/e/needs"><Button size="sm" variant="ghost">Все <ArrowRight className="h-4 w-4" /></Button></Link>} />
          <div className="space-y-2.5 px-5 pb-5">
            {(needs?.items ?? []).length === 0 && <EmptyState title="Нет потребностей" text="Опишите, кого ищете, — получите подборку за секунды." action={<Link to="/e/needs/new"><Button>Описать потребность</Button></Link>} />}
            {(needs?.items ?? []).slice(0, 5).map((n: any) => (
              <Link key={n.id} to={`/e/needs/${n.id}`} className="flex items-center gap-4 rounded-xl border border-line p-3.5 transition hover:border-brand-300">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[14.5px] font-semibold">{n.title}</div>
                  <div className="mt-1 flex flex-wrap gap-1.5">{n.categories.map((c: string) => <Badge key={c} tone="dark">{c}</Badge>)}<span className="text-[12.5px] text-ink-3">{salaryRange(n.salary_from, n.salary_to)}</span></div>
                </div>
                <div className="text-right text-[12.5px] text-ink-3"><div className="font-mono text-[18px] font-bold text-ink">{n.shortlist.total}</div>в подборке · {n.invited} приглаш.</div>
              </Link>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="Воронка приглашений" subtitle="Обратная механика: вы пишете первыми — кандидаты отвечают" />
          <div className="h-48 px-2">
            <ResponsiveContainer>
              <BarChart data={funnel} layout="vertical" margin={{ left: 20, right: 30 }}>
                <XAxis type="number" hide /><YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={90} />
                <Tooltip />
                <Bar dataKey="v" radius={[0, 8, 8, 0]} label={{ position: "right", fontSize: 12 }}>{funnel.map((_, i) => <Cell key={i} fill={["#C9C2FF", "#A497FF", "#402FFF", "#1B1C21"][i]} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {a.decline_reasons.length > 0 && (
            <div className="border-t border-line px-5 py-4">
              <div className="kicker mb-2">Почему отказываются</div>
              {a.decline_reasons.map((r: any) => (
                <div key={r.code} className="mb-1.5 grid grid-cols-[1fr_100px_24px] items-center gap-2 text-[13px]"><span className="truncate text-ink-2">{r.name}</span><Meter value={r.count / Math.max(...a.decline_reasons.map((x: any) => x.count))} tone="warn" /><span className="num text-right">{r.count}</span></div>
              ))}
            </div>
          )}
        </Card>
      </div>
      <Card>
        <CardHeader icon={<Send className="h-5 w-5" />} title="Последние приглашения" action={<Link to="/e/invitations"><Button size="sm" variant="ghost">Все <ArrowRight className="h-4 w-4" /></Button></Link>} />
        <div className="divide-y divide-line">
          {data.recent_invitations.map((i: any) => (
            <Link key={i.id} to={`/e/invitations/${i.id}`} className="flex flex-wrap items-center gap-3 px-5 py-3 hover:bg-surface/60">
              <div className="min-w-0 flex-1"><div className="truncate text-[14px] font-medium">{i.candidate?.code} · {i.candidate?.category}</div><div className="truncate text-[12.5px] text-ink-3">{i.title}</div></div>
              <span className="num text-[13px]">{salaryRange(i.salary_from, i.salary_to)}</span>
              <StatusBadge status={i.status} name={i.status_name} />
              <span className="w-24 text-right text-[12px] text-ink-3">{ago(i.created_at)}</span>
            </Link>
          ))}
        </div>
      </Card>
    </div>
  );
}
