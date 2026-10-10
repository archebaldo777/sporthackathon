import clsx from "clsx";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Award, BadgeCheck, CheckCircle2, Clock, Info, MapPin, Medal, ShieldCheck, Star, Trophy, Users } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from "recharts";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { DISCIPLINE_COLORS, DISCIPLINE_ON_DARK_ICON, FORMAT_NAMES, GROSS_HINT, STATUS_TONE, ago, date, salaryRange } from "@/lib/format";
import { Alert, Badge, Button, Field, Input, Meter, Modal, ScoreRing, Select, Textarea } from "@/components/ui";

export function StatusBadge({ status, name }: { status: string; name?: string }) {
  return <Badge tone={STATUS_TONE[status] ?? "neutral"}>{name ?? status}</Badge>;
}

export function CategoryBadge({ label, large }: { label: string; large?: boolean }) {
  return (
    <span className={clsx("inline-flex items-center gap-1.5 rounded-lg bg-night font-mono font-semibold text-white", large ? "px-3 py-1.5 text-[14px]" : "px-2 py-0.5 text-[12px]")}>
      <span className="h-1.5 w-1.5 rounded-full bg-brand-400" />{label}
    </span>
  );
}

/** Другие категории кандидата (у кандидата может быть основная и до двух дополнительных). */
export function OtherCategories({ c }: { c: any }) {
  const others = (c.categories ?? []).filter((x: any) => x.specialization !== c.specialization);
  if (!others.length) return null;
  return (
    <span className="text-[12px] text-ink-3" title="Другие категории кандидата; грейд в каждой подтверждается отдельным тестом">
      также: {others.map((x: any) => `${x.label}${x.confirmed ? "" : " (не подтв.)"}`).join(", ")}
    </span>
  );
}

export function SkillChips({ verified = [], declared = [], limit = 12, evidence }: { verified?: string[]; declared?: string[]; limit?: number; evidence?: Record<string, any> }) {
  const all = [...verified.map((s) => ({ s, v: true })), ...declared.filter((s) => !verified.includes(s)).map((s) => ({ s, v: false }))].slice(0, limit);
  return (
    <div className="flex flex-wrap gap-1.5">
      {all.map(({ s, v }) => (
        <span key={s} title={v ? "Подтверждено тестом" : "Заявлено кандидатом"}
          className={clsx("inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[12px] font-medium", v ? "bg-brand-500 text-white" : "border border-line bg-white text-ink-2")}>
          {v && <BadgeCheck className="h-3.5 w-3.5" />}{s}
        </span>
      ))}
    </div>
  );
}

const EVIDENCE_LABEL: Record<string, string> = { test: "тест", fsp: "ФСП", task: "задача", declared: "резюме", related: "смежный", none: "нет" };
const EVIDENCE_TONE: Record<string, string> = { test: "bg-brand-500 text-white", fsp: "bg-gradient-to-r from-brand-500 to-accent-500 text-white", task: "bg-ok-500 text-white",
  declared: "bg-surface text-ink-2 border border-line", related: "bg-warn-50 text-warn-700", none: "bg-accent-50 text-accent-700" };

export function ExplainPanel({ match, compact }: { match: any; compact?: boolean }) {
  if (!match) return null;
  return (
    <div className="space-y-4">
      {!compact && (
        <div className="space-y-2.5">
          {match.components?.map((c: any) => (
            <div key={c.key} className="grid grid-cols-[140px_1fr_44px] items-center gap-3 text-[13px]">
              <span className="text-ink-2">{c.name}</span>
              <Meter value={c.value} />
              <span className="num text-right text-ink-3">+{c.contribution}</span>
            </div>
          ))}
        </div>
      )}
      {match.skills && Object.keys(match.skills).length > 0 && (
        <div>
          <div className="kicker mb-2">Навыки из запроса и доказательства</div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(match.skills).map(([s, d]: any) => (
              <span key={s} className={clsx("inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[12px] font-medium", EVIDENCE_TONE[d.evidence] ?? EVIDENCE_TONE.none)}>
                {s}{d.must && <span className="opacity-70">*</span>}<span className="rounded bg-black/10 px-1 text-[10px] uppercase tracking-wide">{EVIDENCE_LABEL[d.evidence] ?? d.evidence}</span>
              </span>
            ))}
          </div>
        </div>
      )}
      <ul className="space-y-1.5">
        {match.reasons?.map((r: string, i: number) => (
          <li key={i} className="flex gap-2 text-[13.5px] text-ink-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok-500" />{r}</li>
        ))}
        {match.warnings?.map((r: string, i: number) => (
          <li key={`w${i}`} className="flex gap-2 text-[13.5px] text-warn-700"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{r}</li>
        ))}
      </ul>
      {match.acceptance && (
        <div className="flex items-center gap-2 rounded-xl bg-surface px-3 py-2 text-[13px] text-ink-2">
          <Info className="h-4 w-4 text-brand-500" />Вероятность, что кандидат примет приглашение: <b className="text-ink">{match.acceptance.label}</b>
          <span className="num text-ink-3">({Math.round(match.acceptance.p * 100)}%)</span>
        </div>
      )}
    </div>
  );
}

export function CandidateRow({ c, onInvite, onMark, needId, selected, onSelect }: {
  c: any; onInvite?: (c: any) => void; onMark?: (mark: string) => void; needId?: number; selected?: boolean; onSelect?: (v: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const m = c.match;
  const inv = c.invitation;
  return (
    <div className={clsx("card overflow-hidden transition", selected && "ring-2 ring-brand-400", c.mark === "hidden" && "opacity-60")}>
      <div className="flex flex-col gap-4 p-4 sm:flex-row sm:items-start">
        <div className="flex items-start gap-3">
          {onSelect && (
            <input type="checkbox" aria-label="Выбрать" checked={!!selected} onChange={(e) => onSelect(e.target.checked)} className="mt-4 h-4 w-4 accent-[#402FFF]" disabled={!!inv && ["sent", "viewed", "accepted"].includes(inv.status)} />
          )}
          {m ? <ScoreRing value={m.score ?? c.score} label="Соответствие потребности" /> : (
            <div className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-night font-mono text-[15px] font-bold text-white" title="Сила подтверждённого профиля">{Math.round(c.strength)}</div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link to={`/e/candidates/${c.id}${needId ? `?need=${needId}` : ""}`} className="text-[16px] font-semibold hover:text-brand-600">{c.name}</Link>
            <CategoryBadge label={c.grade_status === "unconfirmed" ? c.category?.replace(" · не подтверждён", "") : c.category} />
            {c.grade_status === "unconfirmed" && <Badge tone="warn">грейд не подтверждён тестом</Badge>}
            <OtherCategories c={c} />
            {c.age_group === "minor" && <Badge tone="warn">15–17 лет · лёгкий труд</Badge>}
            {c.fsp?.count > 0 && <Badge tone="fsp" icon={<Trophy className="h-3 w-3" />}>ФСП · {c.fsp.count}</Badge>}
            {m?.relation && m.relation !== "target" && <Badge tone="warn">{m.relation === "adjacent_grade" ? "смежный грейд" : "смежная специализация"}</Badge>}
            {c.search_status === "active" && <Badge tone="ok">активно ищет</Badge>}
            {c.mark === "starred" && <Star className="h-4 w-4 fill-warn-500 text-warn-500" />}
          </div>
          {c.headline && <div className="mt-0.5 text-[13.5px] text-ink-3">{c.headline}</div>}
          <div className="mt-2.5"><SkillChips verified={c.verified_skills} declared={c.skills} limit={9} /></div>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-ink-3">
            <span>Ожидания: <b className="font-medium text-ink-2">{salaryRange(c.salary_from, c.salary_to)}</b></span>
            {c.city && <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{c.city}{c.relocation ? " · переезд" : ""}</span>}
            {c.work_formats?.length > 0 && <span>{c.work_formats.map((f: string) => FORMAT_NAMES[f]).join(", ")}</span>}
            {c.category_percentile != null && <span>сильнее {Math.round(c.category_percentile)}% категории</span>}
            {c.tasks?.done > 0 && <span>задачи: {c.tasks.done} · {c.tasks.avg_score?.toFixed(1)}/5</span>}
            <span className="inline-flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{ago(c.last_activity_at)}</span>
          </div>
          {m && !open && m.reasons?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px]">
              {m.reasons.slice(0, 2).map((r: string, i: number) => <span key={i} className="inline-flex items-center gap-1 text-ok-700"><CheckCircle2 className="h-3.5 w-3.5" />{r}</span>)}
              {m.warnings?.slice(0, 1).map((r: string, i: number) => <span key={i} className="inline-flex items-center gap-1 text-warn-700"><AlertTriangle className="h-3.5 w-3.5" />{r}</span>)}
            </div>
          )}
        </div>
        <div className="flex shrink-0 flex-row flex-wrap gap-2 sm:flex-col sm:items-end">
          {inv ? <StatusBadge status={inv.status} name={`Приглашение: ${inv.status_name.toLowerCase()}`} /> : onInvite && <Button size="sm" onClick={() => onInvite(c)}>Пригласить</Button>}
          {m && <Button size="sm" variant="outline" onClick={() => setOpen(!open)}>{open ? "Скрыть" : "Почему в подборке"}</Button>}
          {onMark && (
            <div className="flex gap-1">
              <button title="В избранное" onClick={() => onMark(c.mark === "starred" ? "new" : "starred")} className={clsx("rounded-lg p-1.5 hover:bg-surface", c.mark === "starred" ? "text-warn-500" : "text-ink-4")}><Star className="h-4 w-4" /></button>
              <button title={c.mark === "hidden" ? "Вернуть" : "Скрыть из подборки"} onClick={() => onMark(c.mark === "hidden" ? "new" : "hidden")} className="rounded-lg p-1.5 text-[12px] text-ink-4 hover:bg-surface">{c.mark === "hidden" ? "вернуть" : "скрыть"}</button>
            </div>
          )}
        </div>
      </div>
      {open && m && <div className="border-t border-line bg-surface/60 p-4"><ExplainPanel match={m} /></div>}
    </div>
  );
}

export function FspPanel({ fsp, own }: { fsp: any; own?: boolean }) {
  if (!fsp) return null;
  if (fsp.hidden) return <p className="text-[13px] text-ink-3">Кандидат скрыл достижения в настройках приватности.</p>;
  if (!fsp.items?.length) {
    return (
      <div className="rounded-xl border border-dashed border-line p-4 text-[13.5px] text-ink-3">
        <div className="mb-1 font-medium text-ink-2">{fsp.linked ? "ФСП ID связан, результатов пока нет" : "Истории участия в ФСП нет"}</div>
        {fsp.note || "Категория определяется тестированием — отсутствие ФСП не снижает её."}
        {own && !fsp.linked && <div className="mt-2"><Link to="/c/settings" className="link">Связать профиль с ФСП ID →</Link></div>}
      </div>
    );
  }
  return (
    <div className="space-y-2.5">
      {fsp.profile && (fsp.profile.sport_rank || fsp.profile.rating) && (
        <div className="flex flex-wrap gap-2 text-[12.5px]">
          {fsp.profile.sport_rank && <Badge tone="dark" icon={<Medal className="h-3 w-3" />}>{fsp.profile.sport_rank}</Badge>}
          {fsp.profile.rating && <Badge tone="brand">Рейтинг ФСП: {fsp.profile.rating}</Badge>}
          {fsp.profile.region && <Badge>{fsp.profile.region}</Badge>}
        </div>
      )}
      {fsp.items.map((a: any, i: number) => (
        <div key={i} className="flex gap-3 rounded-xl border border-line bg-white p-3" style={{ borderLeft: `3px solid ${DISCIPLINE_COLORS[a.discipline_code] ?? "#402FFF"}` }}>
          {/* значок в цвете дисциплины ФСП (цветовой код брендбука) */}
          <div className={clsx("grid h-10 w-10 shrink-0 place-items-center rounded-xl", DISCIPLINE_ON_DARK_ICON[a.discipline_code] ? "text-night" : "text-white")}
            style={{ background: DISCIPLINE_COLORS[a.discipline_code] ?? "#402FFF" }}>
            {a.place && a.place <= 3 ? <Trophy className="h-5 w-5" /> : <Award className="h-5 w-5" />}
          </div>
          <div className="min-w-0">
            <div className="text-[14px] font-medium leading-snug">{a.event}</div>
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[12.5px] text-ink-3">
              <span className="font-medium text-ink-2">{a.result}{a.place ? ` · ${a.place} место${a.participants ? ` из ${a.participants}` : ""}` : ""}</span>
              <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: DISCIPLINE_COLORS[a.discipline_code] ?? "#402FFF" }} />{a.discipline}{a.fit && a.fit !== "profile" && <span className="text-ink-4"> · {a.fit_name}</span>}</span><span>{a.level} уровень</span><span>{date(a.date)}</span>
              {a.team && <span className="inline-flex items-center gap-1"><Users className="h-3.5 w-3.5" />«{a.team}», {a.role}</span>}
            </div>
            {a.stack?.length > 0 && <div className="mt-1.5 flex flex-wrap gap-1">{a.stack.map((s: string) => <span key={s} className="rounded-md bg-surface px-1.5 py-0.5 text-[11.5px] text-ink-2">{s}</span>)}</div>}
          </div>
          {a.verified && <ShieldCheck className="ml-auto h-4 w-4 shrink-0 text-ok-500" aria-label="Подтверждено реестром ФСП" />}
        </div>
      ))}
    </div>
  );
}

export function TopicRadar({ topics, height = 260 }: { topics: Record<string, any>; height?: number }) {
  const data = Object.values(topics || {}).map((t: any) => ({ name: t.name.length > 22 ? t.name.slice(0, 21) + "…" : t.name, score: Math.round(t.score * 100) }));
  if (data.length < 3) return <TopicBars topics={topics} />;
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke="#DCDCE0" />
          <PolarAngleAxis dataKey="name" tick={{ fontSize: 11, fill: "#3A3C46" }} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Radar dataKey="score" stroke="#402FFF" fill="#402FFF" fillOpacity={0.22} strokeWidth={2} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TopicBars({ topics }: { topics: Record<string, any> }) {
  const items = Object.values(topics || {}).sort((a: any, b: any) => b.score - a.score);
  return (
    <div className="space-y-2.5">
      {items.map((t: any) => (
        <div key={t.name} className="grid grid-cols-[minmax(0,1fr)_120px_64px] items-center gap-3 text-[13px]">
          <span className="truncate text-ink-2">{t.name}</span>
          <Meter value={t.score} tone={t.score >= 0.6 ? "brand" : t.score >= 0.35 ? "warn" : "danger"} />
          <span className="num text-right text-ink-3">{Math.round(t.score * 100)}% <span className="text-ink-4">{t.correct}/{t.n}</span></span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ приглашение */
export function InviteModal({ open, onClose, candidates, need, vacancy, onSent }: {
  open: boolean; onClose: () => void; candidates: any[]; need?: any; vacancy?: any; onSent?: () => void;
}) {
  const qc = useQueryClient();
  const { data: cat } = useCatalog();
  const base = need || vacancy;
  const [f, setF] = useState<any>({});
  useEffect(() => {
    if (!open) return;
    setF({
      title: base?.title ?? "",
      description: base?.description ? `${base.description}\n\nМы познакомились с вашим подтверждённым профилем на платформе и хотим предложить обсудить позицию.` : "",
      salary_from: base?.salary_from ?? "",
      salary_to: base?.salary_to ?? "",
      work_format: base?.work_formats?.[0] ?? "",
      contact_method: "",
      expires_in_days: 10,
    });
  }, [open, base]);
  const m = useMutation({
    mutationFn: () => api("/employer/invitations", {
      body: {
        candidate_ids: candidates.map((c) => c.id), title: f.title, description: f.description, salary_from: Number(f.salary_from),
        salary_to: Number(f.salary_to), work_format: f.work_format || null, contact_method: f.contact_method, need_id: need?.id ?? null,
        vacancy_id: vacancy?.id ?? null, expires_in_days: Number(f.expires_in_days) || 10,
      },
    }),
    onSuccess: (r: any) => {
      toast.success(r.sent > 1 ? `Отправлено приглашений: ${r.sent}` : "Приглашение отправлено", { description: "Кандидат видит условия и вилку до начала общения." });
      qc.invalidateQueries();
      onSent?.();
      onClose();
    },
    onError: (e: ApiError) => toast.error(e.message),
  });
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const valid = f.title?.length >= 3 && f.description?.length >= 20 && Number(f.salary_from) > 0 && Number(f.salary_to) >= Number(f.salary_from) && f.contact_method?.length >= 3;
  const spec = candidates[0]?.specialization;
  const grade = candidates[0]?.grade;
  const market = spec && grade ? cat?.market_salary?.[spec]?.[grade] : undefined;
  const expectations = candidates.map((c) => c.salary_from).filter(Boolean);
  const over = expectations.filter((x) => Number(f.salary_to) && x > Number(f.salary_to)).length;
  return (
    <Modal open={open} onClose={onClose} wide title={candidates.length > 1 ? `Пригласить ${candidates.length} кандидатов` : `Пригласить: ${candidates[0]?.name ?? ""}`}
      footer={<><Button variant="ghost" onClick={onClose}>Отмена</Button><Button loading={m.isPending} disabled={!valid} onClick={() => m.mutate()}>Отправить приглашение</Button></>}>
      <div className="space-y-4">
        <Alert tone="brand" icon={<Info className="h-4 w-4" />}>
          Кандидат увидит описание, вилку и название компании <b>до начала общения</b>. Его контакты откроются вам после принятия приглашения.
        </Alert>
        <Field label="Позиция / суть предложения" required><Input value={f.title || ""} onChange={set("title")} placeholder="Backend-разработчик в команду биллинга" /></Field>
        <Field label="Описание предложения" required hint="Задачи, команда, стек, формат, что предлагаете"><Textarea rows={5} value={f.description || ""} onChange={set("description")} /></Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Зарплата от, ₽ gross" hint={GROSS_HINT} required><Input type="number" inputMode="numeric" value={f.salary_from} onChange={set("salary_from")} /></Field>
          <Field label="Зарплата до, ₽ gross" required><Input type="number" inputMode="numeric" value={f.salary_to} onChange={set("salary_to")} /></Field>
          <Field label="Формат">
            <Select value={f.work_format || ""} onChange={set("work_format")}>
              <option value="">Не указан</option>
              {Object.entries(FORMAT_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </Field>
        </div>
        {(market || expectations.length > 0) && (
          <div className="flex flex-wrap gap-2 text-[12.5px]">
            {market && <Badge tone="neutral">Медиана рынка для категории: {Math.round(market / 1000)} тыс. ₽</Badge>}
            {expectations.length > 0 && <Badge tone={over ? "warn" : "ok"}>{over ? `У ${over} из ${expectations.length} ожидания выше вашей вилки` : "Ожидания кандидатов в пределах вилки"}</Badge>}
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-[1fr_160px]">
          <Field label="Способ связи" required hint="E-mail или Telegram рекрутера — виден кандидату сразу"><Input value={f.contact_method || ""} onChange={set("contact_method")} placeholder="Ольга, hr@company.ru, @company_hr" /></Field>
          <Field label="Срок ответа, дней"><Input type="number" min={1} max={30} value={f.expires_in_days} onChange={set("expires_in_days")} /></Field>
        </div>
      </div>
    </Modal>
  );
}

export function InfoRow({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-line py-2.5 text-[14px] last:border-0">
      <span className="text-ink-3">{label}</span><span className="text-right font-medium text-ink">{children}</span>
    </div>
  );
}
