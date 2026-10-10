import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BadgeCheck, CheckCircle2, Circle, ClipboardCheck, Download, Inbox, Lock, Sparkles, Trophy } from "lucide-react";
import { Link } from "react-router-dom";
import { CategoryBadge, DemoReset, FspPanel, StatusBadge, TopicRadar } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CardHeader, CompanyMark, EmptyState, Meter, PageLoader, Stat } from "@/components/ui";
import { api, download } from "@/lib/api";
import { date, salaryRange } from "@/lib/format";

export default function CandidateDashboard() {
  const { data: me, isLoading } = useQuery({ queryKey: ["cand-me"], queryFn: () => api("/candidate/me") });
  const { data: inv } = useQuery({ queryKey: ["cand-invitations"], queryFn: () => api("/candidate/invitations") });
  const { data: tasks } = useQuery({ queryKey: ["cand-tasks"], queryFn: () => api("/candidate/tasks"), enabled: !!me?.grade });
  if (isLoading || !me) return <PageLoader />;
  const pending = (inv?.items ?? []).filter((i: any) => ["sent", "viewed"].includes(i.status));
  const nextStep = me.onboarding.find((s: any) => !s.done && !s.optional);
  const stepLink: Record<string, string> = { profile: "/c/profile", survey: "/c/assessment", test: "/c/assessment", publish: "/c/settings", fsp: "/c/settings" };
  return (
    <div className="space-y-6">
      <PageHeader title={`Здравствуйте${me.contacts?.full_name ? `, ${me.contacts.full_name.split(" ")[0]}` : ""}!`}
        subtitle={me.grade ? "Ваш профиль в базе: работодатели видят категорию, подтверждённые навыки и достижения — и приглашают сами." : (me.declared_grade && me.visible ? "Работодатели уже видят вас со статусом «грейд не подтверждён» — ниже кандидатов с подтверждённым грейдом. Пройдите тест, чтобы подняться в выдаче." : "Пройдите опрос и тест, чтобы попасть в категорию — после этого вас начнут находить работодатели.")}
        action={me.grade && <Button variant="outline" icon={<Download className="h-4 w-4" />} onClick={() => download("/candidate/profile/pdf", `draft-profile-${me.code}.pdf`)}>PDF-профиль</Button>} />
      <DemoReset me={me} />

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card className="overflow-hidden">
          <div className="bg-night p-6 text-white">
            <div className="kicker text-white/50">Ваша категория</div>
            {me.grade ? (
              <>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <span className="rounded-xl bg-brand-500 px-4 py-2 font-mono text-[22px] font-bold">{me.category}</span>
                  {me.fsp?.count > 0 && <Badge tone="fsp" icon={<Trophy className="h-3 w-3" />}>ФСП · {me.fsp.count}</Badge>}
                </div>
                <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-white/60">
                  <span className="inline-flex items-center gap-1.5"><BadgeCheck className="h-4 w-4 text-brand-300" />Подтверждён тестом {date(me.grade_confirmed_at)}</span>
                  {me.grade_locked_until && <span className="inline-flex items-center gap-1.5"><Lock className="h-4 w-4" />Смена грейда — с {date(me.grade_locked_until)}</span>}
                </div>
              </>
            ) : (
              <div className="mt-3 text-[20px] font-semibold">Категория пока не присвоена</div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-px bg-line sm:grid-cols-4">
            <MiniStat label="Сила профиля" value={Math.round(me.strength)} hint="из 100" />
            <MiniStat label="В категории" value={me.category_percentile != null ? `топ-${Math.max(1, 100 - Math.round(me.category_percentile))}%` : "—"} hint="по силе профиля" />
            <MiniStat label="Приглашения" value={pending.length} hint="ждут ответа" />
            <MiniStat label="Задачи" value={me.tasks?.done ?? 0} hint={me.tasks?.avg_score ? `ср. оценка ${me.tasks.avg_score.toFixed(1)}` : "решено"} />
          </div>
          {nextStep && (
            <div className="p-5">
              <Alert tone="brand" icon={<Sparkles className="h-4 w-4" />} title={`Следующий шаг: ${nextStep.title}`}>
                <Link to={stepLink[nextStep.key]} className="link">Перейти →</Link>
              </Alert>
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="Путь кандидата" subtitle="Категорию определяет тест, а не резюме" />
          <ol className="space-y-1 px-5 pb-5">
            {me.onboarding.map((s: any) => (
              <li key={s.key}>
                <Link to={stepLink[s.key]} className="flex items-center gap-3 rounded-xl px-2 py-2.5 hover:bg-surface">
                  {s.done ? <CheckCircle2 className="h-5 w-5 text-ok-500" /> : <Circle className="h-5 w-5 text-ink-4" />}
                  <span className={"flex-1 text-[14px] " + (s.done ? "text-ink-3 line-through decoration-ink-4/50" : "font-medium")}>{s.title}</span>
                  {s.optional && !s.done && <Badge>по желанию</Badge>}
                </Link>
              </li>
            ))}
          </ol>
          <div className="border-t border-line px-5 py-4">
            <div className="mb-1.5 flex justify-between text-[13px]"><span className="text-ink-3">Заполненность профиля</span><span className="num font-medium">{Math.round(me.completeness * 100)}%</span></div>
            <Meter value={me.completeness} />
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader icon={<Inbox className="h-5 w-5" />} title="Приглашения от компаний" subtitle="Условия и вилка — до начала общения"
            action={<Link to="/c/invitations"><Button size="sm" variant="ghost">Все <ArrowRight className="h-4 w-4" /></Button></Link>} />
          <div className="px-5 pb-5">
            {pending.length === 0 ? (
              <EmptyState title="Новых приглашений нет" text={me.grade ? "Работодатели видят ваш профиль в категории. Решайте регулярные задачи — это поднимает вас в выдаче." : "Получите категорию, чтобы работодатели могли вас найти."} />
            ) : (
              <div className="space-y-2.5">
                {pending.slice(0, 4).map((i: any) => (
                  <Link key={i.id} to={`/c/invitations/${i.id}`} className="flex items-center gap-3 rounded-xl border border-line p-3 transition hover:border-brand-300">
                    <CompanyMark name={i.company.name} accent={i.company.accent} />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[14px] font-semibold">{i.title}</div>
                      <div className="text-[12.5px] text-ink-3">{i.company.name}</div>
                    </div>
                    <div className="text-right">
                      <div className="num text-[14px] font-semibold">{salaryRange(i.salary_from, i.salary_to)}</div>
                      <StatusBadge status={i.status} name={i.status_name} />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader title="Профиль компетенций" subtitle="По результатам последнего теста" action={<Link to="/c/assessment"><Button size="sm" variant="ghost">Тест <ArrowRight className="h-4 w-4" /></Button></Link>} />
          <div className="px-3 pb-3">
            {Object.keys(me.topic_scores || {}).length ? <TopicRadar topics={me.topic_scores} /> : <EmptyState title="Нет результатов" text="Пройдите тест, чтобы увидеть сильные стороны." action={<Link to="/c/assessment"><Button>Пройти тест</Button></Link>} />}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader icon={<ClipboardCheck className="h-5 w-5" />} title="Регулярная задача" subtitle="Короткая задача от работодателя держит профиль актуальным"
            action={<Link to="/c/tasks"><Button size="sm" variant="ghost">Открыть <ArrowRight className="h-4 w-4" /></Button></Link>} />
          <div className="px-5 pb-5">
            {tasks?.current ? (
              <div className="rounded-xl bg-surface p-4">
                <div className="text-[15px] font-semibold">{tasks.current.task.title}</div>
                <div className="mt-1 text-[13px] text-ink-3">{tasks.current.task.company} · ~{tasks.current.task.est_minutes} мин · до {date(tasks.current.due_at)}</div>
                <Link to="/c/tasks"><Button size="sm" className="mt-3">Решить</Button></Link>
              </div>
            ) : <p className="text-[14px] text-ink-3">{me.grade ? "Активной задачи нет — новая появится в течение недели, или запросите её сейчас на странице задач." : "Задачи станут доступны после присвоения категории."}</p>}
          </div>
        </Card>
        <Card>
          <CardHeader icon={<Trophy className="h-5 w-5" />} title="Достижения ФСП" subtitle={me.fsp?.linked ? `ФСП ID: ${me.fsp.fsp_id}` : "Связь с ФСП ID необязательна"} />
          <div className="max-h-[360px] overflow-y-auto px-5 pb-5"><FspPanel fsp={me.fsp} own /></div>
        </Card>
      </div>
    </div>
  );
}

function MiniStat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="bg-white px-5 py-4">
      <div className="kicker">{label}</div>
      <div className="mt-1.5 font-mono text-[22px] font-bold num">{value}</div>
      {hint && <div className="text-[12px] text-ink-3">{hint}</div>}
    </div>
  );
}
