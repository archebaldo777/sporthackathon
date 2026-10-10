import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, Clock, Lock, Mail, MapPin, Phone, Send, Star, Trophy } from "lucide-react";
import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { CategoryBadge, ExplainPanel, FspPanel, InfoRow, InviteModal, OtherCategories, SkillChips, StatusBadge, TopicRadar } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CardHeader, Meter, PageLoader, ScoreRing } from "@/components/ui";
import { api } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { ago, date, FORMAT_NAMES, salaryRange } from "@/lib/format";

export default function CandidateView() {
  const { id } = useParams();
  const [sp] = useSearchParams();
  const needId = sp.get("need");
  const { data: cat } = useCatalog();
  const { data: c, isLoading } = useQuery({ queryKey: ["emp-candidate", id, needId], queryFn: () => api(`/employer/candidates/${id}`, { query: { need_id: needId } }) });
  const { data: need } = useQuery({ queryKey: ["emp-need", needId], queryFn: () => api(`/employer/needs/${needId}`), enabled: !!needId });
  const [invite, setInvite] = useState(false);
  if (isLoading || !c) return <PageLoader />;
  const active = (c.invitations ?? []).find((i: any) => ["sent", "viewed", "accepted"].includes(i.status));
  const sp_ = c.strength_parts || {};
  return (
    <div className="space-y-6">
      <PageHeader back={needId ? { to: `/e/needs/${needId}`, label: "К подборке" } : { to: "/e/talent", label: "Банк кандидатов" }} title={c.name}
        subtitle={<span className="flex flex-wrap items-center gap-2"><CategoryBadge label={c.category} large /><OtherCategories c={c} />{c.headline && <span>{c.headline}</span>}</span>}
        action={active ? <StatusBadge status={active.status} name={`Приглашение: ${active.status_name.toLowerCase()}`} /> : <Button icon={<Send className="h-4 w-4" />} onClick={() => setInvite(true)}>Пригласить</Button>} />
      {c.age_group === "minor" && (
        <Alert tone="warn" title="Кандидату 15–17 лет">По ТК РФ с несовершеннолетним заключается трудовой договор только на лёгкий труд, не вредящий здоровью и учёбе,
          с сокращённым рабочим временем (ст. 63, 92, 265). Согласие законного представителя на обработку персональных данных получено при регистрации.</Alert>
      )}
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6">
          {c.match && (
            <Card>
              <CardHeader title="Почему кандидат в подборке" subtitle={need?.title} action={<ScoreRing value={c.match.score} />} />
              <div className="px-5 pb-5"><ExplainPanel match={c.match} /></div>
            </Card>
          )}
          <Card>
            <CardHeader title={c.grade_status === "unconfirmed" ? "Уровень не подтверждён" : "Подтверждённый уровень"}
              subtitle={c.grade_status === "unconfirmed" ? "Грейд заявлен кандидатом в опросе, тестом пока не подтверждён — в выдаче кандидат ниже подтверждённых" : `Грейд подтверждён адаптивным тестом ${date(c.grade_confirmed_at)}`} />
            <div className="grid gap-4 px-5 pb-5 md:grid-cols-[1fr_1fr]">
              <div>{Object.keys(c.topic_scores || {}).length ? <TopicRadar topics={c.topic_scores} height={240} /> : <p className="text-ink-3">Нет данных</p>}</div>
              <div className="space-y-3">
                <div className="rounded-xl bg-night p-4 text-white">
                  <div className="kicker text-white/50">Сила профиля</div>
                  <div className="mt-1 font-mono text-[30px] font-bold">{Math.round(c.strength)}<span className="text-[14px] text-white/50"> / 100</span></div>
                  {c.category_percentile != null && <div className="text-[12.5px] text-white/60">сильнее {Math.round(c.category_percentile)}% кандидатов категории</div>}
                </div>
                {[["Результат теста", sp_.test], ["Достижения ФСП", sp_.fsp], ["Актуальность (задачи)", sp_.activity], ["Полнота профиля", sp_.profile]].map(([l, v]: any) => (
                  <div key={l}><div className="mb-1 flex justify-between text-[12.5px]"><span className="text-ink-3">{l}</span><span className="num">{Math.round((v ?? 0) * 100)}%</span></div><Meter value={v ?? 0} /></div>
                ))}
              </div>
            </div>
          </Card>
          <Card>
            <CardHeader title="Навыки" subtitle="Синие — подтверждены результатами теста, белые — заявлены кандидатом" />
            <div className="px-5 pb-5"><SkillChips verified={c.verified_skills} declared={c.skills} limit={40} /></div>
          </Card>
          <Card>
            <CardHeader icon={<Trophy className="h-5 w-5" />} title="Достижения ФСП" subtitle={c.fsp?.linked ? "Данные из реестра ФСП — подтверждены" : undefined} />
            <div className="px-5 pb-5"><FspPanel fsp={c.fsp} /></div>
          </Card>
          {c.task_results?.length > 0 && (
            <Card>
              <CardHeader title="Регулярные задачи" subtitle="Свежий сигнал о кандидате от других работодателей" />
              <div className="divide-y divide-line px-5 pb-3">
                {c.task_results.map((t: any, i: number) => (
                  <div key={i} className="flex items-center justify-between py-2.5 text-[14px]"><div><div className="font-medium">{t.title}</div><div className="text-[12.5px] text-ink-3">{t.company} · {date(t.date)}</div></div><span className="inline-flex items-center gap-1 font-mono font-bold"><Star className="h-4 w-4 fill-warn-500 text-warn-500" />{t.score}/5</span></div>
                ))}
              </div>
            </Card>
          )}
          {c.experience?.length > 0 && (
            <Card>
              <CardHeader title="Опыт (со слов кандидата)" />
              <div className="space-y-3 px-5 pb-5">
                {c.experience.map((e: any, i: number) => (
                  <div key={i} className="rounded-xl border border-line p-3.5"><div className="font-medium">{e.title}{e.company ? ` · ${e.company}` : <span className="text-ink-4"> · компания скрыта</span>}</div><div className="text-[12.5px] text-ink-3">{e.start} — {e.end || "н.в."}</div>{e.description && <p className="mt-1 text-[13.5px] text-ink-2">{e.description}</p>}</div>
                ))}
              </div>
            </Card>
          )}
        </div>
        <div className="space-y-6">
          <Card className="p-5">
            {c.contacts_revealed && c.contacts ? (
              <>
                <div className="flex items-center gap-2 text-[15px] font-semibold text-ok-700"><BadgeCheck className="h-5 w-5" />Контакты открыты</div>
                <div className="mt-3 space-y-2 text-[14px]">
                  <div className="font-semibold">{c.contacts.full_name}</div>
                  {c.contacts.email && <div className="flex items-center gap-2"><Mail className="h-4 w-4 text-ink-3" />{c.contacts.email}</div>}
                  {c.contacts.phone && <div className="flex items-center gap-2"><Phone className="h-4 w-4 text-ink-3" />{c.contacts.phone}</div>}
                  {c.contacts.telegram && <div className="flex items-center gap-2"><Send className="h-4 w-4 text-ink-3" />{c.contacts.telegram}</div>}
                </div>
              </>
            ) : (
              <Alert tone="brand" icon={<Lock className="h-4 w-4" />} title="Контакты скрыты">Откроются, когда кандидат примет ваше приглашение (или откликнется на вашу вакансию).</Alert>
            )}
          </Card>
          <Card className="px-5 py-2">
            <InfoRow label="Ожидания">{salaryRange(c.salary_from, c.salary_to)}</InfoRow>
            <InfoRow label="Формат">{c.work_formats?.map((f: string) => FORMAT_NAMES[f]).join(", ") || "—"}</InfoRow>
            <InfoRow label="Город"><span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{c.city || "—"}{c.relocation ? " · переезд" : ""}</span></InfoRow>
            <InfoRow label="Стаж">{c.experience_years != null ? `${c.experience_years} лет` : "—"}</InfoRow>
            <InfoRow label="Роль в команде">{cat?.team_roles.find((r) => r.code === c.team_role)?.name ?? "—"}</InfoRow>
            <InfoRow label="Статус поиска">{cat?.search_statuses.find((s) => s.code === c.search_status)?.name}</InfoRow>
            <InfoRow label="Активность"><span className="inline-flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{ago(c.last_activity_at)}</span></InfoRow>
            {c.domains?.length > 0 && <InfoRow label="Отрасли">{c.domains.map((d: string) => cat?.domains.find((x) => x.code === d)?.name).join(", ")}</InfoRow>}
          </Card>
          {c.soft_skills?.length > 0 && <Card className="p-5"><div className="kicker mb-2">Софт-скиллы</div><div className="flex flex-wrap gap-1.5">{c.soft_skills.map((s: string) => <Badge key={s}>{s}</Badge>)}</div></Card>}
          {c.about && <Card className="p-5"><div className="kicker mb-2">О себе</div><p className="text-[14px] text-ink-2">{c.about}</p></Card>}
          {c.invitations?.length > 0 && (
            <Card className="p-5"><div className="kicker mb-2">Ваши приглашения</div>{c.invitations.map((i: any) => <div key={i.id} className="flex items-center justify-between py-1.5 text-[13.5px]"><span className="truncate">{i.title}</span><StatusBadge status={i.status} name={i.status_name} /></div>)}</Card>
          )}
        </div>
      </div>
      <InviteModal open={invite} onClose={() => setInvite(false)} candidates={[c]} need={need} />
    </div>
  );
}
