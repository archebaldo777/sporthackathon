import { useMutation, useQuery } from "@tanstack/react-query";
import { Building2, Mail, ShieldCheck, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Alert, Button, Card, Checkbox, Field, FspLogo, Input, Logo, PageLoader, PatternStrip, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { homeFor, useAuth, type TokenOut } from "@/lib/auth";

export default function Auth({ mode }: { mode: "login" | "register" | "verify" | "fsp" }) {
  return (
    <div className="grid min-h-[calc(100vh-64px)] bg-surface lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <BrandPanel />
      <div className="grid place-items-center px-4 py-12">
        <div className="w-full max-w-[460px]">
          {mode === "login" && <Login />}
          {mode === "register" && <Register />}
          {mode === "verify" && <Verify />}
          {mode === "fsp" && <FspCallback />}
        </div>
      </div>
    </div>
  );
}

/** Фирменная панель ФСП (только на широких экранах): логотип Федерации, паттерн, голос бренда. */
function BrandPanel() {
  return (
    <aside className="relative hidden overflow-hidden bg-night text-white lg:flex lg:flex-col">
      <div className="absolute inset-0 bg-gradient-to-b from-night via-night to-digital" />
      <PatternStrip className="relative h-7" />
      <div className="relative flex flex-1 flex-col justify-center px-12 py-12 xl:px-16">
        <FspLogo dark variant="full" className="h-8 self-start" />
        <h2 className="brand-title mt-12 text-[30px] leading-tight xl:text-[34px]">Код — это спорт.<br />Результат — это резюме.</h2>
        <ul className="mt-8 space-y-3 font-mono text-[14px] leading-relaxed text-white/75">
          {["Грейд подтверждает адаптивный тест, а не анкета", "Достижения ФСП — из реестра по ФСП ID", "Компании приходят сами и сразу называют вилку", "Контакты — только после вашего «да»"].map((t) => (
            <li key={t}><span className="text-accent-500">_</span>{t}</li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

/** В карточке формы логотип ФСП показывается только там, где нет фирменной панели (узкие экраны). */
function CardLogo() {
  return (<><div className="lg:hidden"><Logo /></div><div className="hidden lg:block"><Logo fsp={false} /></div></>);
}

function FspButton({ label = "Войти через ФСП ID" }: { label?: string }) {
  const m = useMutation({
    mutationFn: () => api<{ authorize_url: string }>("/auth/fsp/login", { auth: false }),
    onSuccess: (r) => (window.location.href = r.authorize_url),
    onError: (e: ApiError) => toast.error(e.message),
  });
  return (
    <Button variant="dark" size="lg" className="w-full" loading={m.isPending} onClick={() => m.mutate()} icon={<FspLogo dark variant="star" className="h-5" />}>{label}</Button>
  );
}

function Login() {
  const [sp] = useSearchParams();
  const [email, setEmail] = useState(sp.get("email") || "");
  const [password, setPassword] = useState(sp.get("email")?.endsWith("@draft.demo") ? "Demo2026!" : "");
  const { login } = useAuth();
  const nav = useNavigate();
  const { data: stats } = useQuery({ queryKey: ["public-stats"], queryFn: () => api("/public/stats", { auth: false }) });
  const m = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: (u) => nav(sp.get("next") && u.email_verified ? sp.get("next")! : homeFor(u)),
    onError: (e: ApiError) => toast.error(e.message),
  });
  const quick = [["candidate@draft.demo", "Кандидат"], ["newbie@draft.demo", "Новый кандидат"], ["employer@draft.demo", "Работодатель"]];
  return (
    <Card className="p-7">
      <CardLogo />
      <h1 className="mt-6 text-[24px] font-bold">Вход</h1>
      <p className="mt-1 text-[14px] text-ink-3">Нет аккаунта? <Link to="/register" className="link">Зарегистрируйтесь</Link></p>
      <form className="mt-6 space-y-4" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        <Field label="E-mail"><Input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
        <Field label="Пароль"><Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></Field>
        <Button type="submit" size="lg" className="w-full" loading={m.isPending}>Войти</Button>
      </form>
      <div className="my-5 flex items-center gap-3 text-[12px] text-ink-4"><div className="h-px flex-1 bg-line" />или<div className="h-px flex-1 bg-line" /></div>
      <FspButton />
      <p className="mt-2 text-center text-[12px] text-ink-3">Для кандидатов — участников соревнований ФСП</p>
      {stats?.demo_mode && (
        <div className="mt-6 rounded-xl bg-surface p-4">
          <div className="kicker mb-2">Демо-доступ · пароль Demo2026!</div>
          <div className="flex flex-wrap gap-2">
            {quick.map(([e, l]) => (
              <button key={e} type="button" onClick={() => { setEmail(e); setPassword("Demo2026!"); }} className="rounded-lg border border-line bg-white px-2.5 py-1.5 text-[12.5px] hover:border-brand-300">{l}</button>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function Register() {
  const [sp] = useSearchParams();
  const [role, setRole] = useState<"candidate" | "employer">(sp.get("role") === "employer" ? "employer" : "candidate");
  const [f, setF] = useState({ email: "", password: "", company_name: "", consent_pd: false, consent_publication: true, age_group: "adult", guardian_consent: false });
  const nav = useNavigate();
  const m = useMutation({
    mutationFn: () => api("/auth/register", { body: { ...f, role, company_name: role === "employer" ? f.company_name : null }, auth: false }),
    onSuccess: (r: any) => nav(`/verify-email?email=${encodeURIComponent(r.email)}${r.demo_mailbox_url ? `&mailbox=${encodeURIComponent(r.demo_mailbox_url)}` : ""}`),
    onError: (e: ApiError) => toast.error(e.message, { description: Array.isArray(e.details) ? e.details.map((d: any) => d.msg).join("; ") : undefined }),
  });
  const pwOk = f.password.length >= 8 && /\d/.test(f.password) && /\D/.test(f.password);
  return (
    <Card className="p-7">
      <CardLogo />
      <h1 className="mt-6 text-[24px] font-bold">Регистрация</h1>
      <p className="mt-1 text-[14px] text-ink-3">Уже есть аккаунт? <Link to="/login" className="link">Войти</Link></p>
      <div className="mt-6 grid grid-cols-2 gap-2">
        {([["candidate", "Я кандидат", <UserRound key="u" className="h-5 w-5" />], ["employer", "Я работодатель", <Building2 key="b" className="h-5 w-5" />]] as const).map(([r, l, i]) => (
          <button key={r} type="button" onClick={() => setRole(r)} className={"flex flex-col items-start gap-2 rounded-xl border p-3.5 text-left transition " + (role === r ? "border-brand-500 bg-brand-50 text-brand-800" : "border-line hover:border-brand-200")}>
            {i}<span className="text-[14px] font-semibold">{l}</span>
          </button>
        ))}
      </div>
      <form className="mt-5 space-y-4" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        {role === "employer" && <Field label="Название компании" required><Input value={f.company_name} onChange={(e) => setF({ ...f, company_name: e.target.value })} required /></Field>}
        <Field label="E-mail" required hint={role === "employer" ? "Корпоративная почта на домене компании повышает индекс доверия" : undefined}>
          <Input type="email" autoComplete="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required />
        </Field>
        <Field label="Пароль" required hint="Не короче 8 символов, буквы и цифры" error={f.password && !pwOk ? "Пароль должен быть не короче 8 символов и содержать буквы и цифры" : null}>
          <Input type="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required />
        </Field>
        {role === "candidate" && (
          <Field label="Возраст" hint="Платформа доступна с 15 лет">
            <div className="grid grid-cols-2 gap-2">
              {[["adult", "18 лет и старше"], ["minor", "15–17 лет"]].map(([v, n]) => (
                <button key={v} type="button" onClick={() => setF({ ...f, age_group: v })}
                  className={"rounded-xl border px-3 py-2 text-[13.5px] font-medium transition " + (f.age_group === v ? "border-brand-500 bg-brand-50" : "border-line hover:border-brand-200")}>{n}</button>
              ))}
            </div>
          </Field>
        )}
        <div className="space-y-3 rounded-xl bg-surface p-4">
          <Checkbox checked={f.consent_pd} onChange={(v) => setF({ ...f, consent_pd: v })}
            label={<>Даю согласие на обработку персональных данных в соответствии с 152-ФЗ <span className="text-accent-500">*</span></>} />
          {role === "candidate" && (
            <Checkbox checked={f.consent_publication} onChange={(v) => setF({ ...f, consent_publication: v })} label="Публиковать мой профиль для работодателей платформы"
              description="Без контактов: они раскрываются только после того, как вы примете приглашение. Можно изменить в настройках." />
          )}
          {role === "candidate" && f.age_group === "minor" && (
            <Checkbox checked={f.guardian_consent} onChange={(v) => setF({ ...f, guardian_consent: v })}
              label={<>Родитель или законный представитель дал согласие на обработку моих персональных данных <span className="text-accent-500">*</span></>}
              description="Работодатели увидят, что вам 15–17 лет: по ТК РФ доступен только лёгкий труд с сокращённым рабочим временем." />
          )}
        </div>
        <Button type="submit" size="lg" className="w-full" disabled={!f.consent_pd || !pwOk || (role === "candidate" && f.age_group === "minor" && !f.guardian_consent)} loading={m.isPending}>Создать аккаунт</Button>
      </form>
      {role === "candidate" && (
        <>
          <div className="my-5 flex items-center gap-3 text-[12px] text-ink-4"><div className="h-px flex-1 bg-line" />или<div className="h-px flex-1 bg-line" /></div>
          <FspButton label="Зарегистрироваться через ФСП ID" />
          <p className="mt-2 text-center text-[12px] text-ink-3">Достижения ФСП подтянутся в профиль автоматически</p>
        </>
      )}
    </Card>
  );
}

function Verify() {
  const [sp] = useSearchParams();
  const token = sp.get("token");
  const [email, setEmail] = useState(sp.get("email") || "");
  const [code, setCode] = useState("");
  const { acceptTokens, user } = useAuth();
  const nav = useNavigate();
  const done = useRef(false);
  const m = useMutation({
    mutationFn: (body: any) => api<TokenOut>("/auth/verify-email", { body, auth: false }),
    onSuccess: (t) => { const u = acceptTokens(t); toast.success("E-mail подтверждён"); nav(homeFor(u)); },
    onError: (e: ApiError) => toast.error(e.message),
  });
  const resend = useMutation({
    mutationFn: () => api("/auth/resend-verification", { body: { email }, auth: false }),
    onSuccess: () => toast.success("Письмо отправлено повторно"),
  });
  useEffect(() => {
    if (token && !done.current) { done.current = true; m.mutate({ token }); }
  }, [token]); // eslint-disable-line
  const mailbox = sp.get("mailbox");
  if (token) return <Card className="p-8 text-center">{m.isError ? <Alert tone="danger">{(m.error as ApiError).message}</Alert> : <><Spinner className="mx-auto" /><p className="mt-3 text-ink-3">Подтверждаем e-mail…</p></>}</Card>;
  return (
    <Card className="p-7">
      <div className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand-600"><Mail /></div>
      <h1 className="mt-5 text-[24px] font-bold">Подтвердите e-mail</h1>
      <p className="mt-1.5 text-[14px] text-ink-3">Мы отправили 6-значный код{email ? <> на <b className="text-ink">{email}</b></> : ""}. Введите его или перейдите по ссылке из письма.</p>
      {mailbox && (
        <Alert tone="brand" icon={<ShieldCheck className="h-4 w-4" />} title="Демо-стенд">
          Письма доставляются в веб-почту Mailpit: <a className="link" href={mailbox} target="_blank" rel="noreferrer">{mailbox}</a>
        </Alert>
      )}
      <form className="mt-5 space-y-4" onSubmit={(e) => { e.preventDefault(); m.mutate({ email, code }); }}>
        {!sp.get("email") && <Field label="E-mail"><Input type="email" value={email || user?.email || ""} onChange={(e) => setEmail(e.target.value)} required /></Field>}
        <Field label="Код из письма">
          <Input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            className="text-center font-mono text-[24px] tracking-[0.5em]" placeholder="••••••" required />
        </Field>
        <Button type="submit" size="lg" className="w-full" disabled={code.length !== 6} loading={m.isPending}>Подтвердить</Button>
      </form>
      <button className="mt-4 text-[13px] text-brand-600 hover:underline" onClick={() => resend.mutate()} disabled={!email || resend.isPending}>Отправить код ещё раз</button>
    </Card>
  );
}

function FspCallback() {
  const [sp] = useSearchParams();
  const { acceptTokens } = useAuth();
  const nav = useNavigate();
  const [err, setErr] = useState<string | null>(null);
  const done = useRef(false);
  useEffect(() => {
    if (done.current) return;
    done.current = true;
    const code = sp.get("code"), state = sp.get("state");
    if (!code || !state) { setErr("Некорректный ответ ФСП ID"); return; }
    api("/auth/fsp/callback", { body: { code, state } })
      .then((r: any) => {
        if (r.intent === "login" && r.tokens) {
          const u = acceptTokens(r.tokens);
          toast.success("Вход через ФСП ID выполнен", { description: r.achievements ? `Подтянуто достижений: ${r.achievements}` : undefined });
          nav(homeFor(u));
        } else {
          toast.success("ФСП ID связан с профилем", { description: `Получено достижений: ${r.achievements}` });
          nav("/c/settings");
        }
      })
      .catch((e: ApiError) => setErr(e.message));
  }, []); // eslint-disable-line
  if (err) return <Card className="p-7"><Alert tone="danger" title="Не удалось войти через ФСП ID">{err}</Alert><Link to="/login" className="link mt-4 inline-block">Вернуться ко входу</Link></Card>;
  return <PageLoader />;
}
