import clsx from "clsx";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight, BarChart3, Bell, Briefcase, Building2, ClipboardCheck, FileText, FlaskConical, Inbox, LayoutDashboard, LogOut, Map, Menu,
  Plug, Search, Send, Settings, Sparkles, Target, TrendingUp, Trophy, UserRound, X,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { homeFor, useAuth } from "@/lib/auth";
import { ago } from "@/lib/format";
import { Button, FspLogo, Logo, PatternStrip } from "@/components/ui";

/* ------------------------------------------------------------------ публичная часть */
const DEVELOPERS = [
  { name: "archebaldo777", url: "https://github.com/archebaldo777" },
  { name: "RealZel", url: "https://github.com/RealZel" },
];

export function PublicLayout() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  const links = [
    { to: "/how", label: "Как это работает" },
    { to: "/mechanics", label: "Механика тестирования" },
    { to: "/validation", label: "Валидация" },
    { to: "/jobs", label: "Вакансии" },
  ];
  return (
    <div className="min-h-screen bg-surface">
      <header className="sticky top-0 z-40 border-b border-white/5 bg-night/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
          <Link to="/" aria-label="На главную"><Logo dark /></Link>
          <nav className="hidden items-center gap-1 lg:flex">
            {links.map((l) => (
              <NavLink key={l.to} to={l.to} className={({ isActive }) => clsx("rounded-lg px-3 py-2 text-[14px] transition", isActive ? "text-white" : "text-white/60 hover:text-white")}>{l.label}</NavLink>
            ))}
          </nav>
          <div className="hidden items-center gap-2 sm:flex">
            {user ? (
              <Link to={homeFor(user)}><Button size="sm">Личный кабинет</Button></Link>
            ) : (
              <>
                <Link to="/login"><Button size="sm" variant="ghost" className="text-white/80 hover:bg-white/10 hover:text-white">Войти</Button></Link>
                <Link to="/register"><Button size="sm">Регистрация</Button></Link>
              </>
            )}
          </div>
          <button className="rounded-lg p-2 text-white lg:hidden" onClick={() => setOpen(!open)} aria-label="Меню">{open ? <X /> : <Menu />}</button>
        </div>
        {open && (
          <div className="border-t border-white/10 px-4 pb-4 lg:hidden">
            {links.map((l) => <Link key={l.to} to={l.to} className="block rounded-lg px-2 py-3 text-white/80">{l.label}</Link>)}
            <div className="mt-2 flex gap-2">
              {user ? <Link to={homeFor(user)} className="flex-1"><Button className="w-full">Кабинет</Button></Link> : (
                <><Link to="/login" className="flex-1"><Button variant="dark" className="w-full border border-white/20">Войти</Button></Link>
                  <Link to="/register" className="flex-1"><Button className="w-full">Регистрация</Button></Link></>
              )}
            </div>
          </div>
        )}
      </header>
      <Outlet />
      <footer className="bg-night text-white">
        <PatternStrip className="h-7 opacity-90" />
        <div className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-10 sm:px-6 md:flex-row md:items-end md:justify-between">
          <div>
            <Logo dark fsp={false} />
            <p className="mt-4 max-w-md text-[13px] leading-relaxed text-white/55">Платформа ИТ-найма с обратной механикой: работодатель приходит к кандидату с подтверждённым грейдом и достижениями ФСП. Данные на стенде демонстрационные.</p>
            <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 font-mono text-[12px] uppercase tracking-[0.08em] text-white/55">
              <Link to="/how" className="hover:text-white">Как это работает</Link>
              <Link to="/mechanics" className="hover:text-white">Механика</Link>
              <Link to="/validation" className="hover:text-white">Валидация</Link>
              <a href="/api/docs" className="hover:text-white">API (Swagger)</a>
            </div>
          </div>
          <div className="md:text-right">
            <div className="kicker mb-3 text-white/40">Проект Федерации</div>
            <FspLogo dark variant="full" className="h-9 max-w-full md:ml-auto" />
          </div>
        </div>
        <div className="border-t border-white/10">
          <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 text-[12px] text-white/55 sm:px-6 md:flex-row md:items-center md:justify-between">
            <p className="max-w-2xl leading-relaxed">
              Проект разработан в рамках хакатона «Лидеры цифровой трансформации 2026» по задаче Федерации спортивного
              программирования России «Цифровая платформа-агрегатор ИТ-вакансий с верифицированным профилем достижений участника ФСП».
            </p>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono uppercase tracking-[0.08em] md:justify-end">
              <span className="text-white/40">Разработчики</span>
              {DEVELOPERS.map((d) => (
                <a key={d.name} href={d.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 normal-case tracking-normal text-white/70 hover:text-white">
                  {d.name}<ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
                </a>
              ))}
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ------------------------------------------------------------------ кабинеты */
type NavItem = { to: string; label: string; icon: ReactNode; end?: boolean; badge?: number };

function useNav(role: string): NavItem[] {
  const { data } = useQuery({
    queryKey: ["nav-counters", role],
    queryFn: () => (role === "candidate" ? api("/candidate/me") : api("/employer/dashboard")),
    enabled: role === "candidate" || role === "employer",
    staleTime: 30_000,
  });
  if (role === "candidate")
    return [
      { to: "/c", label: "Обзор", icon: <LayoutDashboard />, end: true },
      { to: "/c/invitations", label: "Приглашения", icon: <Inbox />, badge: data?.pending_invitations },
      { to: "/c/assessment", label: "Категория и тест", icon: <Target /> },
      { to: "/c/profile", label: "Профиль и резюме", icon: <UserRound /> },
      { to: "/c/tasks", label: "Задачи", icon: <ClipboardCheck /> },
      { to: "/c/growth", label: "Рост и зарплаты", icon: <TrendingUp /> },
      { to: "/c/jobs", label: "Вакансии", icon: <Briefcase /> },
      { to: "/c/applications", label: "Мои отклики", icon: <Send /> },
      { to: "/c/settings", label: "Настройки и ФСП ID", icon: <Settings /> },
    ];
  return [
    { to: "/e", label: "Обзор", icon: <LayoutDashboard />, end: true },
    { to: "/e/needs", label: "Потребности и подборки", icon: <Sparkles /> },
    { to: "/e/talent", label: "Банк кандидатов", icon: <Map /> },
    { to: "/e/invitations", label: "Приглашения", icon: <Send /> },
    { to: "/e/vacancies", label: "Вакансии", icon: <Briefcase />, badge: data?.new_applications },
    { to: "/e/tasks", label: "Задачи кандидатам", icon: <ClipboardCheck />, badge: data?.submissions_to_review },
    { to: "/e/company", label: "Компания", icon: <Building2 /> },
    { to: "/e/integrations", label: "Интеграции (ATS)", icon: <Plug /> },
  ];
}

export function CabinetLayout({ role }: { role: "candidate" | "employer" }) {
  const { user, logout } = useAuth();
  const nav = useNav(role);
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center px-5"><Link to="/"><Logo dark /></Link></div>
      <div className="mx-3 mb-3 rounded-xl bg-white/5 px-3 py-2.5">
        <div className="kicker text-white/40">{role === "candidate" ? "Кабинет кандидата" : "Кабинет работодателя"}</div>
        <div className="mt-1 truncate text-[14px] font-medium text-white">{user?.display_name || user?.email}</div>
      </div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3">
        {nav.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end}
            className={({ isActive }) => clsx("group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[14px] transition [&_svg]:h-[18px] [&_svg]:w-[18px]",
              isActive ? "bg-brand-500 text-white shadow-lift" : "text-white/65 hover:bg-white/5 hover:text-white")}>
            {n.icon}<span className="flex-1">{n.label}</span>
            {!!n.badge && <span className="rounded-full bg-accent-500 px-1.5 text-[11px] font-semibold text-white num">{n.badge}</span>}
          </NavLink>
        ))}
      </nav>
      <PatternStrip className="mx-3 mb-1 h-4 opacity-50" />
      <div className="space-y-0.5 border-t border-white/10 p-3">
        <Link to="/mechanics" className="flex items-center gap-3 rounded-xl px-3 py-2 text-[13px] text-white/50 hover:text-white [&_svg]:h-4 [&_svg]:w-4"><FlaskConical />Механика тестирования</Link>
        <Link to="/validation" className="flex items-center gap-3 rounded-xl px-3 py-2 text-[13px] text-white/50 hover:text-white [&_svg]:h-4 [&_svg]:w-4"><BarChart3 />Валидация</Link>
        <button onClick={logout} className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-[13px] text-white/50 hover:text-white [&_svg]:h-4 [&_svg]:w-4"><LogOut />Выйти</button>
      </div>
    </div>
  );
  return (
    <div className="min-h-screen bg-surface">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 bg-night lg:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-night/60" />
          <aside className="absolute inset-y-0 left-0 w-72 bg-night" onClick={(e) => e.stopPropagation()}>{sidebar}</aside>
        </div>
      )}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-line bg-white/85 px-4 backdrop-blur sm:px-6">
          <div className="flex items-center gap-3">
            <button className="rounded-lg p-2 lg:hidden" onClick={() => setOpen(true)} aria-label="Меню"><Menu /></button>
            <div className="lg:hidden"><Logo compact /></div>
            {role === "employer" && (
              <Link to="/e/talent" className="hidden items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2 text-[13px] text-ink-3 hover:border-brand-300 md:flex">
                <Search className="h-4 w-4" />Найти кандидатов по категории и стеку
              </Link>
            )}
            {role === "candidate" && (
              <span className="hidden items-center gap-2 text-[13px] text-ink-3 md:flex"><Trophy className="h-4 w-4 text-brand-500" />Компании сами приглашают вас — откликаться не обязательно</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Notifications />
          </div>
        </header>
        <main className="mx-auto max-w-[1240px] px-4 py-6 sm:px-6 sm:py-8"><Outlet /></main>
      </div>
    </div>
  );
}

function Notifications() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();
  const nav = useNavigate();
  const { data } = useQuery({ queryKey: ["notifications"], queryFn: () => api("/notifications"), refetchInterval: 30_000 });
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const readAll = async () => { await api("/notifications/read-all", { method: "POST" }); qc.invalidateQueries({ queryKey: ["notifications"] }); };
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} className="relative rounded-xl p-2.5 text-ink-2 hover:bg-surface" aria-label="Уведомления">
        <Bell className="h-5 w-5" />
        {!!data?.unread && <span className="absolute right-1.5 top-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-accent-500 px-1 text-[10px] font-bold text-white">{data.unread}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-[min(380px,calc(100vw-24px))] overflow-hidden rounded-2xl border border-line bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <span className="text-[14px] font-semibold">Уведомления</span>
            {!!data?.unread && <button className="text-[12px] text-brand-600 hover:underline" onClick={readAll}>Прочитать все</button>}
          </div>
          <div className="max-h-[420px] overflow-y-auto">
            {(data?.items ?? []).length === 0 && <div className="px-4 py-8 text-center text-[13px] text-ink-3">Пока нет уведомлений</div>}
            {(data?.items ?? []).map((n: any) => (
              <button key={n.id} onClick={() => { setOpen(false); if (n.link) nav(n.link); }}
                className={clsx("block w-full border-b border-line px-4 py-3 text-left hover:bg-surface", !n.read && "bg-brand-50/50")}>
                <div className="flex items-start gap-2">
                  {!n.read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand-500" />}
                  <div className="min-w-0">
                    <div className="text-[13.5px] font-medium leading-snug">{n.title}</div>
                    {n.body && <div className="mt-0.5 line-clamp-2 text-[12.5px] text-ink-3">{n.body}</div>}
                    <div className="mt-1 text-[11px] text-ink-4">{ago(n.created_at)}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function PageHeader({ title, subtitle, action, back }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode; back?: { to: string; label: string } }) {
  return (
    <div className="mb-6">
      {back && <Link to={back.to} className="mb-3 inline-flex items-center gap-1 text-[13px] text-ink-3 hover:text-brand-600">← {back.label}</Link>}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[24px] font-bold leading-tight sm:text-[28px]">{title}</h1>
          {subtitle && <p className="mt-1.5 max-w-3xl text-[14.5px] text-ink-3">{subtitle}</p>}
        </div>
        {action && <div className="flex flex-wrap gap-2">{action}</div>}
      </div>
    </div>
  );
}

export function FileTextIcon() { return <FileText />; }
