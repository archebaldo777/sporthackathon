import clsx from "clsx";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CheckCircle2, Clock, FlaskConical, History, Layers, Lock, Play, Plus, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { CategoryBadge, StatusBadge } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CardHeader, ChoiceChips, Field, Input, Meter, PageLoader, Select, TagInput, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { date, dateTime, GRADE_NAMES } from "@/lib/format";

export default function Assessment() {
  const { data: me, isLoading } = useQuery({ queryKey: ["cand-me"], queryFn: () => api("/candidate/me") });
  const [editSurvey, setEditSurvey] = useState(false);
  if (isLoading || !me) return <PageLoader />;
  const needSurvey = !me.survey_completed_at || editSurvey;
  return (
    <div className="space-y-6">
      <PageHeader title="Категория и тестирование"
        subtitle="Категорию видят работодатели: специализация × грейд. Она определяется обязательным путём — опрос, выбор предполагаемого грейда и адаптивный тест на этот грейд." />
      {needSurvey ? <Survey me={me} onDone={() => setEditSurvey(false)} canCancel={!!me.survey_completed_at} /> : <TestHub me={me} onEditSurvey={() => setEditSurvey(true)} />}
    </div>
  );
}

/* ------------------------------------------------------------------ опрос */
function Survey({ me, onDone, canCancel }: { me: any; onDone: () => void; canCancel: boolean }) {
  const { data: cat } = useCatalog();
  const qc = useQueryClient();
  const [step, setStep] = useState(0);
  const [f, setF] = useState<any>({
    direction: me.direction || "", specialization: me.specialization || "", primary_lang: me.primary_lang || "", framework: me.framework || "",
    stack: me.skills || [], experience_years: me.experience_years ?? 1, declared_grade: me.declared_grade || "", team_role: me.team_role || "developer",
    domains: me.domains || [], work_formats: me.work_formats || [], motivation: "",
  });
  const spec = cat?.specializations.find((s) => s.code === f.specialization);
  const m = useMutation({
    mutationFn: () => api("/candidate/survey", { body: { ...f, primary_lang: f.primary_lang || null, framework: f.framework || null } }),
    onSuccess: () => { toast.success("Опрос сохранён"); qc.invalidateQueries(); onDone(); },
    onError: (e: ApiError) => toast.error(e.message),
  });
  if (!cat) return <PageLoader />;
  const steps = ["Направление", "Специализация", "Опыт и стек", "Грейд"];
  const canNext = [!!f.direction, !!f.specialization && (!spec || spec.langs.length < 2 || !!f.primary_lang), f.stack.length > 0, !!f.declared_grade][step];
  const yearsHint = (g: string) => cat.grades.find((x) => x.code === g)?.years;
  // подсказка по опыту (в т. ч. распознанному из резюме): только ориентир, грейд выбирает кандидат и подтверждает тест
  const y = Number(f.experience_years) || 0;
  const hinted = y < 1 ? "intern" : y < 2 ? "junior" : y < 5 ? "middle" : "senior";
  return (
    <Card className="overflow-hidden">
      <div className="flex gap-1 border-b border-line bg-surface/60 p-2">
        {steps.map((s, i) => (
          <div key={s} className={clsx("flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium", i === step ? "bg-white text-ink shadow-card" : i < step ? "text-brand-600" : "text-ink-4")}>
            <span className={clsx("grid h-6 w-6 place-items-center rounded-full font-mono text-[12px]", i < step ? "bg-brand-500 text-white" : i === step ? "bg-night text-white" : "bg-line")}>{i < step ? "✓" : i + 1}</span>
            <span className="hidden sm:inline">{s}</span>
          </div>
        ))}
      </div>
      <div className="p-6">
        {step === 0 && (
          <div>
            <h2 className="text-[20px] font-bold">Ваше направление (отрасль ИТ)</h2>
            <p className="mt-1 text-[14px] text-ink-3">От направления зависит набор специализаций и компетенций теста.</p>
            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {cat.directions.map((d) => (
                <button key={d.code} onClick={() => setF({ ...f, direction: d.code, specialization: cat.specializations.find((s) => s.direction === d.code)?.code === f.specialization ? f.specialization : "" })}
                  className={clsx("rounded-xl border p-4 text-left transition", f.direction === d.code ? "border-brand-500 bg-brand-50" : "border-line hover:border-brand-200")}>
                  <div className="text-[15px] font-semibold">{d.name}</div>
                  <div className="mt-1 text-[12.5px] text-ink-3">{cat.specializations.filter((s) => s.direction === d.code).map((s) => s.short).join(" · ")}</div>
                </button>
              ))}
            </div>
          </div>
        )}
        {step === 1 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-[20px] font-bold">Специализация</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {cat.specializations.filter((s) => s.direction === f.direction).map((s) => (
                  <button key={s.code} onClick={() => setF({ ...f, specialization: s.code, primary_lang: s.langs.length === 1 ? s.langs[0] : "", framework: s.code === "frontend" ? "react" : "" })}
                    className={clsx("rounded-xl border p-4 text-left transition", f.specialization === s.code ? "border-brand-500 bg-brand-50" : "border-line hover:border-brand-200")}>
                    <div className="text-[15px] font-semibold">{s.name}</div>
                    <div className="mt-1 text-[12.5px] text-ink-3">{s.core_skills.slice(0, 5).join(", ")}</div>
                  </button>
                ))}
              </div>
            </div>
            {spec && spec.langs.length > 1 && (
              <Field label="Основной язык" hint="Задания на трассировку кода будут на этом языке">
                <ChoiceChips options={spec.langs.map((l) => ({ code: l, name: cat.langs.find((x) => x.code === l)?.name ?? l }))} value={f.primary_lang} onChange={(v) => setF({ ...f, primary_lang: v })} />
              </Field>
            )}
            {spec?.frameworks?.length ? (
              <Field label="Основной UI-фреймворк">
                <ChoiceChips options={spec.frameworks.map((x) => ({ code: x, name: x[0].toUpperCase() + x.slice(1) }))} value={f.framework} onChange={(v) => setF({ ...f, framework: v })} />
              </Field>
            ) : null}
          </div>
        )}
        {step === 2 && (
          <div className="grid gap-5 lg:grid-cols-2">
            <Field label="Основной стек" required hint="Навыки из онтологии платформы — тест подтвердит часть из них" className="lg:col-span-2">
              <TagInput value={f.stack} onChange={(v) => setF({ ...f, stack: v })} suggestions={[...(spec?.core_skills ?? []), ...cat.skills.map((s) => s.name)]} placeholder="Python, PostgreSQL, Docker…" />
            </Field>
            <Field label="Коммерческий опыт, лет"><Input type="number" min={0} max={50} step={0.5} value={f.experience_years} onChange={(e) => setF({ ...f, experience_years: Number(e.target.value) })} /></Field>
            <Field label="Роль в команде"><ChoiceChips options={cat.team_roles} value={f.team_role} onChange={(v) => setF({ ...f, team_role: v })} /></Field>
            <Field label="Отраслевой опыт" hint="Финтех, ритейл, госсектор…" className="lg:col-span-2"><ChoiceChips multi options={cat.domains} value={f.domains} onChange={(v) => setF({ ...f, domains: v })} /></Field>
            <Field label="Формат работы"><ChoiceChips multi options={cat.work_formats} value={f.work_formats} onChange={(v) => setF({ ...f, work_formats: v })} /></Field>
            <Field label="Что для вас важно в работе (необязательно)"><Textarea rows={2} value={f.motivation} onChange={(e) => setF({ ...f, motivation: e.target.value })} /></Field>
          </div>
        )}
        {step === 3 && (
          <div>
            <h2 className="text-[20px] font-bold">Ваш предполагаемый грейд</h2>
            <p className="mt-1 text-[14px] text-ink-3">Тест будет на этот уровень. Если не получится — грейд не понижается принудительно: сразу можно пройти тест на уровень ниже. Справитесь уверенно — предложим сразу пройти отдельный тест на грейд выше.</p>
            <p className="mt-3 text-[13.5px] text-ink-2">Подсказка по опыту ({y} {y === 1 ? "год" : (y > 1 && y < 5) || !Number.isInteger(y) ? "года" : "лет"}): обычно это <b>{GRADE_NAMES[hinted]}</b>. Это только ориентир — выбор за вами, грейд определит тест.</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {cat.grades.map((g) => (
                <button key={g.code} onClick={() => setF({ ...f, declared_grade: g.code })}
                  className={clsx("rounded-xl border p-4 text-left transition", f.declared_grade === g.code ? "border-brand-500 bg-brand-50 shadow-lift" : "border-line hover:border-brand-200")}>
                  <div className="flex items-center justify-between gap-2"><span className="font-mono text-[18px] font-bold">{g.name}</span>{g.code === hinted && <Badge>подсказка</Badge>}</div>
                  <div className="mt-1 text-[12.5px] text-ink-3">{yearsHint(g.code)}</div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
      <div className="flex items-center justify-between border-t border-line bg-surface/40 px-6 py-4">
        <div>{step > 0 ? <Button variant="ghost" icon={<ArrowLeft className="h-4 w-4" />} onClick={() => setStep(step - 1)}>Назад</Button> : canCancel && <Button variant="ghost" onClick={onDone}>Отмена</Button>}</div>
        {step < 3 ? <Button disabled={!canNext} onClick={() => setStep(step + 1)}>Далее <ArrowRight className="h-4 w-4" /></Button>
          : <Button disabled={!canNext} loading={m.isPending} onClick={() => m.mutate()}>Сохранить и перейти к тесту</Button>}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ выбор теста */
function TestHub({ me, onEditSurvey }: { me: any; onEditSurvey: () => void }) {
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: el, isLoading } = useQuery({ queryKey: ["eligibility"], queryFn: () => api("/candidate/assessment/eligibility") });
  const { data: hist } = useQuery({ queryKey: ["cand-history"], queryFn: () => api("/candidate/history") });
  const { data: cat } = useCatalog();
  const [target, setTarget] = useState<string>("");
  useEffect(() => {
    if (!el) return;
    const allowed = Object.entries(el.grades).filter(([, v]: any) => v.allowed).map(([k]) => k);
    setTarget(allowed.includes(me.declared_grade) ? me.declared_grade : allowed[allowed.length - 1] ?? "");
  }, [el, me.declared_grade, me.specialization]); // eslint-disable-line
  const start = useMutation({
    mutationFn: () => api("/candidate/assessment/attempts", { body: { target_grade: target } }),
    onSuccess: (r: any) => { qc.invalidateQueries({ queryKey: ["eligibility"] }); nav(`/c/assessment/test/${r.attempt_id}`); },
    onError: (e: ApiError) => toast.error(e.message),
  });
  if (isLoading || !el) return <PageLoader />;
  const spec = cat?.specializations.find((s) => s.code === me.specialization);
  return (
    <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
      <div className="space-y-6">
        <Card>
          <CardHeader icon={<FlaskConical className="h-5 w-5" />} title={me.grade ? "Подтверждённая категория" : "Тест на заявленный грейд"}
            subtitle={`${spec?.name ?? ""}${me.primary_lang ? ` · ${cat?.langs.find((l) => l.code === me.primary_lang)?.name}` : ""}${me.framework ? ` · ${me.framework}` : ""}`}
            action={<Button size="sm" variant="ghost" icon={<RefreshCw className="h-4 w-4" />} onClick={onEditSurvey}>Изменить опрос</Button>} />
          <div className="space-y-5 px-5 pb-5">
            {me.grade && <div className="flex flex-wrap items-center gap-3"><CategoryBadge label={me.category} large /><span className="text-[13px] text-ink-3">подтверждён {date(me.grade_confirmed_at)}</span></div>}
            {el.in_progress_attempt_id && (
              <Alert tone="warn" icon={<Clock className="h-4 w-4" />} title="Есть незавершённая попытка">
                <Link className="link" to={`/c/assessment/test/${el.in_progress_attempt_id}`}>Продолжить тест →</Link>
              </Alert>
            )}
            {el.locked_until && <Alert tone="brand" icon={<Lock className="h-4 w-4" />}>Смена грейда доступна не чаще раза в 90 дней — следующая возможность с <b>{date(el.locked_until)}</b>.</Alert>}
            <div>
              <div className="kicker mb-2">Выберите грейд для теста</div>
              <div className="grid gap-2.5 sm:grid-cols-2">
                {Object.entries(el.grades).map(([g, v]: any) => (
                  <button key={g} disabled={!v.allowed} onClick={() => setTarget(g)}
                    className={clsx("rounded-xl border p-3.5 text-left transition disabled:cursor-not-allowed",
                      target === g ? "border-brand-500 bg-brand-50" : "border-line hover:border-brand-200", !v.allowed && "bg-surface opacity-70")}>
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[16px] font-bold">{GRADE_NAMES[g]}</span>
                      {g === me.declared_grade && <Badge tone="brand">заявлен</Badge>}
                      {g === me.grade && <Badge tone="ok">подтверждён</Badge>}
                      {v.allowed && v.mode === "upgrade" && <Badge tone="ok">вне очереди</Badge>}
                      {v.allowed && v.mode === "step_down" && <Badge>не расходует попытку</Badge>}
                      {v.allowed && v.mode === "confirm" && <Badge tone="warn">контрольная форма</Badge>}
                    </div>
                    <div className="mt-1 text-[12.5px] text-ink-3">{v.allowed ? (v.mode === "upgrade" ? "Тест на повышение по результату прошлой попытки" : v.mode === "confirm" ? "6–10 новых заданий для подтверждения результата" : "Доступен сейчас") : `${v.reason}${v.available_at ? ` · с ${date(v.available_at)}` : ""}`}</div>
                  </button>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button size="lg" disabled={!target || !!el.in_progress_attempt_id} loading={start.isPending} icon={<Play className="h-4 w-4" />} onClick={() => start.mutate()}>
                Начать тест{target ? ` на ${GRADE_NAMES[target]}` : ""}
              </Button>
              <span className="text-[13px] text-ink-3">от {el.config?.min_items} до {el.config?.max_items} заданий (обычно 13–16) · до {el.config?.minutes} мин · попыток за 30 дней: {el.attempts_30d}/{el.attempts_limit}</span>
            </div>
          </div>
        </Card>
        {el.plan && (
          <Card>
            <CardHeader title="Из чего состоит тест" subtitle="Доли компетенций (контентная балансировка адаптивного теста)" />
            <div className="space-y-3 px-5 pb-5">
              {el.plan.map((p: any) => (
                <div key={p.competency} className="grid grid-cols-[minmax(0,1fr)_140px_70px] items-center gap-3 text-[13.5px]">
                  <div className="min-w-0"><div className="truncate font-medium">{p.name}</div><div className="truncate text-[12px] text-ink-3">{p.families} семейств заданий · {p.examples.slice(0, 2).join(", ")}</div></div>
                  <Meter value={p.weight / 0.35} />
                  <span className="num text-right text-ink-3">~{Math.round(p.expected_items)} шт.</span>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
      <div className="space-y-6">
        <Categories busy={!!el.in_progress_attempt_id} />
        <Card className="p-5">
          <div className="flex items-center gap-2 text-[15px] font-semibold"><ShieldCheck className="h-5 w-5 text-brand-500" />Как устроен тест</div>
          <ul className="mt-3 space-y-2.5 text-[13.5px] text-ink-2">
            {["Адаптивный: следующее задание подбирается под ваш уровень по модели IRT; тест заканчивается, как только грейд определён надёжно — у пограничных результатов заданий больше.",
              "Уникальный: задания генерируются заново для каждого кандидата — данные, код и варианты отличаются, трудность та же.",
              "На каждое задание свой таймер. Уходы со вкладки и вставки текста фиксируются для контроля честности.",
              "Не прошли — грейд не понижается принудительно; тест на уровень ниже доступен сразу и не расходует попытку, повтор того же — через 14 дней.",
              "Справились уверенно — предложим отдельный тест на грейд выше без ожидания. Автоматического повышения нет. Смена грейда — не чаще раза в 90 дней."].map((t) => (
              <li key={t} className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok-500" />{t}</li>
            ))}
          </ul>
          <Link to="/mechanics" className="link mt-4 inline-block text-[13px]">Подробнее о механике тестирования →</Link>
        </Card>
        <Card>
          <CardHeader icon={<History className="h-5 w-5" />} title="История" />
          <div className="space-y-2 px-5 pb-5">
            {(hist?.attempts ?? []).length === 0 && <p className="text-[13px] text-ink-3">Попыток пока не было.</p>}
            {(hist?.attempts ?? []).slice(0, 6).map((a: any) => (
              <Link key={a.id} to={a.status === "completed" ? `/c/assessment/result/${a.id}` : `/c/assessment/test/${a.id}`} className="flex items-center justify-between gap-3 rounded-xl border border-line px-3 py-2.5 hover:border-brand-300">
                <div><div className="text-[14px] font-medium">Тест на {GRADE_NAMES[a.target_grade]}</div><div className="text-[12px] text-ink-3">{dateTime(a.started_at)} · {a.items} заданий</div></div>
                {a.status !== "completed" ? <StatusBadge status="sent" name="в процессе" /> : a.passed ? <Badge tone="ok">подтверждён</Badge> : <Badge tone="danger">не подтверждён</Badge>}
              </Link>
            ))}
            {(hist?.grade_changes ?? []).length > 0 && (
              <div className="pt-2">
                <div className="kicker mb-2">Изменения грейда</div>
                {hist.grade_changes.map((g: any, i: number) => (
                  <div key={i} className="flex justify-between py-1 text-[13px]"><span>{g.from ? `${GRADE_NAMES[g.from] ?? g.from} → ` : ""}{GRADE_NAMES[g.to] ?? "сброс"}</span><span className="text-ink-3">{date(g.created_at)}</span></div>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ несколько категорий */
export function Categories({ busy }: { busy: boolean }) {
  const qc = useQueryClient();
  const { data: cat } = useCatalog();
  const { data } = useQuery({ queryKey: ["cand-categories"], queryFn: () => api("/candidate/categories") });
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState({ specialization: "", declared_grade: "" });
  const after = (msg: string) => ({
    onSuccess: () => { toast.success(msg); qc.invalidateQueries(); setAdding(false); setF({ specialization: "", declared_grade: "" }); },
    onError: (e: ApiError) => toast.error(e.message),
  });
  const add = useMutation({ mutationFn: () => api("/candidate/categories", { body: f }), ...after("Категория добавлена — подтвердите грейд тестом") });
  const main = useMutation({ mutationFn: (spec: string) => api(`/candidate/categories/${spec}/main`, { method: "POST" }), ...after("Категория стала основной — тест теперь по ней") });
  const del = useMutation({ mutationFn: (spec: string) => api(`/candidate/categories/${spec}`, { method: "DELETE" }), ...after("Категория удалена") });
  if (!data || !cat) return null;
  const taken = new Set(data.items.map((c: any) => c.specialization));
  const extras = data.items.filter((c: any) => !c.main).length;
  return (
    <Card>
      <CardHeader icon={<Layers className="h-5 w-5" />} title="Мои категории"
        subtitle={`Основная и до ${data.max_extra} дополнительных. Грейд в каждой подтверждается только тестом; работодатели находят вас во всех категориях.`} />
      <div className="space-y-2 px-5 pb-5">
        {data.items.map((c: any) => (
          <div key={c.specialization} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line px-3 py-2.5">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-[14px] font-medium">
                {c.label}{c.main && <Badge tone="dark">основная</Badge>}{c.confirmed ? <Badge tone="ok">подтверждён</Badge> : <Badge tone="warn">не подтверждён</Badge>}
              </div>
              <div className="text-[12px] text-ink-3">{c.main ? "Тест проходится по основной категории" : c.confirmed ? `Подтверждён ${date(c.grade_confirmed_at)}` : "Сделайте основной, чтобы пройти тест"}</div>
            </div>
            {!c.main && (
              <div className="flex gap-1.5">
                <Button size="sm" variant="outline" disabled={busy} loading={main.isPending && main.variables === c.specialization} onClick={() => main.mutate(c.specialization)}>
                  {c.confirmed ? "Сделать основной" : "Пройти тест"}
                </Button>
                <Button size="sm" variant="ghost" aria-label={`Удалить категорию ${c.label}`} icon={<Trash2 className="h-4 w-4" />} onClick={() => del.mutate(c.specialization)} />
              </div>
            )}
          </div>
        ))}
        {busy && extras > 0 && <p className="text-[12px] text-ink-3">Сменить основную категорию можно после завершения начатого теста.</p>}
        {adding ? (
          <div className="grid gap-2 rounded-xl bg-surface p-3 sm:grid-cols-[1fr_120px_auto]">
            <Field label="Специализация">
              <Select value={f.specialization} onChange={(e) => setF({ ...f, specialization: e.target.value })}>
                <option value="">Выберите…</option>
                {cat.specializations.filter((s) => !taken.has(s.code)).map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
              </Select>
            </Field>
            <Field label="Грейд">
              <Select value={f.declared_grade} onChange={(e) => setF({ ...f, declared_grade: e.target.value })}>
                <option value="">—</option>
                {cat.grades.map((g) => <option key={g.code} value={g.code}>{g.name}</option>)}
              </Select>
            </Field>
            <div className="flex items-end gap-1.5">
              <Button disabled={!f.specialization || !f.declared_grade} loading={add.isPending} onClick={() => add.mutate()}>Добавить</Button>
              <Button variant="ghost" onClick={() => setAdding(false)}>Отмена</Button>
            </div>
          </div>
        ) : extras < data.max_extra && (
          <Button size="sm" variant="ghost" icon={<Plus className="h-4 w-4" />} onClick={() => setAdding(true)}>Добавить категорию</Button>
        )}
      </div>
    </Card>
  );
}
