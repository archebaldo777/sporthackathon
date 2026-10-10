import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BadgeCheck, Building2, Eye, FlaskConical, Lock, Repeat, Search, Send, ShieldCheck, Sparkles, Target, Trophy, UserRound, Wallet } from "lucide-react";
import { Link } from "react-router-dom";
import { CategoryBadge } from "@/components/domain";
import { Badge, Button, CompanyMark, PatternStrip } from "@/components/ui";
import { DISCIPLINE_COLORS } from "@/lib/format";
import { api } from "@/lib/api";

export default function Landing() {
  const { data: s } = useQuery({ queryKey: ["public-stats"], queryFn: () => api("/public/stats", { auth: false }) });
  const { data: vr } = useQuery({ queryKey: ["validation"], queryFn: () => api("/validation/report", { auth: false }), retry: false });
  const acc = vr?.testing?.accuracy;
  const accText = acc ? ` На проверочной популяции тест совпадает с истинным уровнем в ${Math.round(acc.exact_grade_agreement * 100)}% случаев против ${Math.round(acc.self_declared_agreement * 100)}% у самоописания.` : "";
  return (
    <div>
      {/* hero */}
      <section className="relative overflow-hidden bg-night text-white">
        {/* фон по брендбуку: графит #1B1C21 и digital-акцент #0A006B */}
        <div className="absolute inset-0 bg-gradient-to-br from-night via-night to-digital" />
        <div className="grid-bg absolute inset-0 opacity-25" />
        <div className="absolute -bottom-40 left-1/3 h-[360px] w-[360px] rounded-full bg-accent-500/15 blur-[120px]" />
        <div className="relative mx-auto grid max-w-7xl gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:py-24">
          <div>
            <div className="kicker text-white/50"><span className="text-accent-500">_</span>Проект ФСП · платформа ИТ-найма</div>
            <h1 className="mt-5 text-[38px] font-extrabold leading-[1.05] sm:text-[54px]">
              ИТ-найм наоборот:<br /><span className="text-brand-300">компании приходят</span> к тем, кто подтвердил уровень
            </h1>
            <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-white/70">
              Кандидат проходит опрос и адаптивный тест — и попадает в категорию «специализация × грейд». Работодатель выбирает категорию,
              видит подтверждённые навыки и достижения ФСП и сам отправляет приглашение с зарплатной вилкой.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/register?role=candidate"><Button size="lg" icon={<UserRound className="h-4 w-4" />}>Я ищу работу</Button></Link>
              <Link to="/register?role=employer"><Button size="lg" variant="dark" className="border border-white/20" icon={<Building2 className="h-4 w-4" />}>Я нанимаю</Button></Link>
            </div>
            <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-white/50">
              <span className="inline-flex items-center gap-1.5"><Wallet className="h-4 w-4" />Зарплата видна до начала общения</span>
              <span className="inline-flex items-center gap-1.5"><Lock className="h-4 w-4" />Контакты — только после вашего согласия</span>
            </div>
          </div>
          {/* иллюстрация: приглашение кандидату */}
          <div className="relative hidden lg:block">
            <div className="absolute left-6 top-4 w-[88%] rotate-[-3deg] rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur">
              <div className="kicker text-white/40">Категория</div>
              <div className="mt-2 flex items-center gap-2"><CategoryBadge label="Backend · Middle" large /><Badge tone="fsp" icon={<Trophy className="h-3 w-3" />}>Призёр ФСП</Badge></div>
              <div className="mt-4 grid grid-cols-3 gap-2 text-[12px] text-white/60">
                {["SQL 86%", "Python 81%", "HTTP 74%"].map((x) => <div key={x} className="rounded-lg bg-white/5 px-2 py-1.5 font-mono">{x}</div>)}
              </div>
            </div>
            <div className="relative mt-28 rounded-2xl bg-white p-5 text-ink shadow-2xl">
              <div className="flex items-center gap-3">
                <CompanyMark name="ФинПоток Банк" accent="#0E9F6E" />
                <div><div className="text-[15px] font-semibold">Приглашение от «ФинПоток Банк»</div><div className="text-[13px] text-ink-3">Python-разработчик в команду платежей</div></div>
              </div>
              <div className="mt-4 flex items-end justify-between rounded-xl bg-surface p-4">
                <div><div className="kicker">Зарплата</div><div className="mt-1 font-mono text-[24px] font-bold">240–310 тыс. ₽</div></div>
                <Badge tone="ok">гибрид</Badge>
              </div>
              <div className="mt-3 space-y-1.5 text-[13px] text-ink-2">
                <div className="flex gap-2"><BadgeCheck className="h-4 w-4 text-brand-500" />Вас выбрали по подтверждённому грейду Middle</div>
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1"><Trophy className="h-4 w-4 text-accent-500" />и результатам Чемпионата России ФСП
                  <span className="inline-flex items-center gap-1.5 rounded-md bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink-2"><span className="h-2 w-2 rounded-full" style={{ background: DISCIPLINE_COLORS.product }} />продуктовое программирование</span></div>
              </div>
              <div className="mt-4 flex gap-2"><Button className="flex-1">Принять</Button><Button variant="outline" className="flex-1">Отклонить</Button></div>
            </div>
          </div>
        </div>
        <PatternStrip className="relative h-8" />
      </section>

      {/* статистика */}
      <section className="border-b border-line bg-white">
        <div className="mx-auto grid max-w-7xl grid-cols-2 gap-px bg-line px-0 sm:grid-cols-4">
          {[
            [s?.candidates_verified, "кандидатов с подтверждённой категорией"],
            [s?.with_fsp, "с достижениями ФСП"],
            [s?.templates, "семейств заданий-генераторов"],
            [s?.companies, "компаний ищут сотрудников"],
          ].map(([v, l], i) => (
            <div key={i} className="bg-white px-6 py-7">
              <div className="font-pixel text-[38px] leading-none text-ink tabular-nums">{v ?? "—"}</div>
              <div className="mt-1 text-[13px] text-ink-3">{l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* две стороны */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <div className="grid gap-6 lg:grid-cols-2">
          <Side tone="dark" kicker="Кандидату" title="Подтвердите уровень один раз — и получайте предложения"
            steps={[
              [<Target key="1" />, "Опрос и выбор грейда", "Направление, специализация, стек, предполагаемый грейд."],
              [<FlaskConical key="2" />, "Адаптивный тест 20–30 минут", "Уникальные задания под ваш язык. Не прошли — грейд не понижается, можно пройти уровень ниже."],
              [<Send key="3" />, "Приглашения с вилкой", "Компании находят вас в категории и пишут первыми. Условия видны сразу, контакты — после вашего «да»."],
            ]} />
          <Side kicker="Работодателю" title="Опишите, кто нужен, — система соберёт подборку и объяснит выбор"
            steps={[
              [<Sparkles key="1" />, "Потребность простым текстом", "NLP разберёт стек, грейд, вилку и формат. Уточните фильтры — подборка сохранится."],
              [<Search key="2" />, "Категории и ранжирование", "Кандидаты из категорий, присвоенных тестом, а не резюме. У каждого — «почему в подборке»."],
              [<Send key="3" />, "Приглашение конкретному человеку", "Описание, вилка, способ связи. Статусы: отправлено → просмотрено → принято."],
            ]} />
        </div>
      </section>

      {/* отличия */}
      <section className="bg-white">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
          <div className="kicker"><span className="text-accent-500">_</span>Чем «Драфт» отличается от досок вакансий</div>
          <h2 className="brand-title mt-3 max-w-3xl text-[26px] leading-tight sm:text-[30px]">Отбор по проверяемым данным, а не по совпадению ключевых слов</h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              [<ShieldCheck key="a" />, "Категория — из теста", `Грейд присваивает адаптивный тест (IRT), а не самоописание.${accText}`],
              [<Repeat key="b" />, "Задания не утекают", `${s?.templates ?? "200+"} шаблонов-генераторов: у каждого кандидата свои данные и формулировки, ответ вычисляется. «Слитые» ответы почти не помогают.`],
              [<Trophy key="c" />, "Достижения ФСП — в рейтинге", "Связь с ФСП ID (OIDC, Keycloak-совместимо). Результаты соревнований подтверждены реестром и поднимают кандидата внутри категории."],
              [<Eye key="d" />, "Объяснимая выдача", "Каждый кандидат в подборке — с разложением оценки: уровень, навыки с типом доказательства, ФСП, актуальность, условия."],
              [<Wallet key="e" />, "Зарплата — обязательно", "Вилка указывается и в вакансии, и в приглашении. Кандидат видит условия до начала общения."],
              [<Lock key="f" />, "Приватность по 152-ФЗ", "Профиль анонимен до принятия приглашения, журнал согласий, выгрузка и удаление данных."],
            ].map(([icon, t, d], i) => (
              <div key={i} className="rounded-2xl border border-line p-5 transition hover:border-brand-200 hover:shadow-lift">
                <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600 [&_svg]:h-5 [&_svg]:w-5">{icon}</div>
                <h3 className="mt-4 font-sans text-[16px] font-semibold">{t}</h3>
                <p className="mt-1.5 text-[14px] leading-relaxed text-ink-3">{d}</p>
              </div>
            ))}
          </div>
          <div className="mt-10 flex flex-wrap gap-3">
            <Link to="/how"><Button variant="outline" icon={<ArrowRight className="h-4 w-4" />}>Подробно о механике подбора</Button></Link>
            <Link to="/mechanics"><Button variant="outline" icon={<FlaskConical className="h-4 w-4" />}>Механика тестирования</Button></Link>
            <Link to="/validation"><Button variant="outline">Результаты валидации</Button></Link>
          </div>
        </div>
      </section>

      {/* демо */}
      {s?.demo_mode && (
        <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
          <div className="overflow-hidden rounded-2xl bg-night text-white">
            <PatternStrip className="h-6 opacity-80" />
            <div className="p-6 sm:p-10">
            <div className="kicker text-white/50"><span className="text-accent-500">_</span>Для жюри и тестирования</div>
            <h2 className="mt-2 text-[24px] font-bold">Демо-аккаунты (пароль <span className="text-brand-300">Demo2026!</span>)</h2>
            <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["employer@draft.demo", "Работодатель «ТехноВектор»", "потребности, подборки, приглашения"],
                ["candidate@draft.demo", "Кандидат Backend · Middle", "с достижениями ФСП и приглашениями"],
                ["candidate2@draft.demo", "Кандидат Frontend · Junior", "без истории ФСП"],
                ["newbie@draft.demo", "Новый кандидат", "пройти путь с нуля: опрос → тест"],
              ].map(([e, t, d]) => (
                <Link key={e} to={`/login?email=${encodeURIComponent(e)}`} className="rounded-xl border border-white/10 bg-white/5 p-4 transition hover:border-brand-400">
                  <div className="font-mono text-[13px] text-brand-300">{e}</div>
                  <div className="mt-2 text-[14px] font-medium">{t}</div>
                  <div className="mt-0.5 text-[12.5px] text-white/50">{d}</div>
                </Link>
              ))}
            </div>
            <p className="mt-5 text-[13px] text-white/50">Регистрация нового пользователя требует подтверждения e-mail: письма на демо-стенде приходят в веб-почту Mailpit
              {s.demo_mailbox_url && <> (<a className="text-brand-300 underline" href={s.demo_mailbox_url} target="_blank" rel="noreferrer">{s.demo_mailbox_url}</a>)</>}.</p>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function Side({ kicker, title, steps, tone }: { kicker: string; title: string; steps: [React.ReactNode, string, string][]; tone?: "dark" }) {
  const dark = tone === "dark";
  return (
    <div className={dark ? "rounded-2xl bg-brand-500 p-7 text-white" : "rounded-2xl border border-line bg-white p-7"}>
      <div className={dark ? "kicker text-white/60" : "kicker"}><span className={dark ? "text-white" : "text-accent-500"}>_</span>{kicker}</div>
      <h2 className="mt-2 text-[22px] font-bold leading-snug">{title}</h2>
      <ol className="mt-6 space-y-5">
        {steps.map(([icon, t, d], i) => (
          <li key={i} className="flex gap-4">
            <div className={(dark ? "bg-white/15 text-white" : "bg-brand-50 text-brand-600") + " grid h-10 w-10 shrink-0 place-items-center rounded-xl [&_svg]:h-5 [&_svg]:w-5"}>{icon}</div>
            <div><div className="text-[15px] font-semibold">{i + 1}. {t}</div><div className={(dark ? "text-white/75" : "text-ink-3") + " mt-0.5 text-[14px] leading-relaxed"}>{d}</div></div>
          </li>
        ))}
      </ol>
    </div>
  );
}
