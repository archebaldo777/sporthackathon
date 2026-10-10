import { ArrowDown, ArrowRight, BadgeCheck, Eye, Filter, Lock, Scale, Send, ShieldAlert, Sparkles, Target, Trophy, Wallet } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Button } from "@/components/ui";

const COMPONENTS = [
  ["L", "Подтверждённый уровень", "30%", "Положение θ внутри полосы грейда по адаптивному тесту. Целевая категория — 0.55…1.0, соседний грейд — ниже и с пометкой."],
  ["S", "Навыки с доказательствами", "30%", "Покрытие обязательных (80%) и желательных (20%) навыков. Сила доказательства: тест 1.0 · ФСП 0.9 · задача 0.8 · резюме 0.5 · смежный навык 0.3."],
  ["F", "Достижения ФСП", "4–20%", "Уровень соревнования × место × давность × релевантность дисциплины. Вес задаёт работодатель. Нет истории ФСП — нет бонуса, но нет и штрафа."],
  ["C", "Условия", "15%", "Ожидания vs вилка, формат и город. Ожидания выше вилки на 10%+ и несовместимый формат — дополнительный понижающий множитель."],
  ["A", "Актуальность", "8%", "Свежая активность, решённые регулярные задачи и их оценки работодателями."],
  ["D", "Контекст", "7%", "Отраслевой опыт и текстовая близость описания потребности и профиля (TF-IDF)."],
];

export default function How() {
  return (
    <div>
      <section className="bg-night text-white">
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
          <div className="kicker text-white/50">Механика подбора</div>
          <h1 className="mt-3 max-w-4xl text-[34px] font-extrabold leading-tight sm:text-[44px]">Работодатель выходит на контакт первым — с конкретным предложением и зарплатой</h1>
          <p className="mt-4 max-w-3xl text-[16px] text-white/65">На досках вакансий кандидат откликается вслепую, а работодатель вручную разбирает сотни резюме. В «Драфте» наоборот: кандидат один раз подтверждает уровень, а компании находят его в категории и приглашают.</p>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
        <div className="grid gap-4 lg:grid-cols-5">
          {[
            [<Target key="1" />, "1. Категория из теста", "Опрос → выбор грейда → адаптивный тест. Категория = специализация × грейд, присвоенные тестом, а не резюме."],
            [<Sparkles key="2" />, "2. Потребность", "Работодатель описывает, кто нужен: текстом (NLP-разбор) или формой. Вилка обязательна."],
            [<Filter key="3" />, "3. Подборка", "Сначала целевые категории, затем смежные. Ранжирование по силе подтверждённого профиля и соответствию."],
            [<Eye key="4" />, "4. Объяснение", "У каждого кандидата: вклад компонент, навыки с типом доказательства, предупреждения, вероятность ответа."],
            [<Send key="5" />, "5. Приглашение", "Описание, вилка, компания, способ связи. Контакты кандидата — только после его согласия."],
          ].map(([icon, t, d], i) => (
            <div key={i} className="relative rounded-2xl border border-line bg-white p-5">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-500 text-white [&_svg]:h-5 [&_svg]:w-5">{icon}</div>
              <h3 className="mt-4 font-sans text-[15px] font-semibold">{t}</h3>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-3">{d}</p>
              {i < 4 && <ArrowRight className="absolute -right-3.5 top-1/2 z-10 hidden h-6 w-6 -translate-y-1/2 rounded-full bg-surface p-1 text-brand-500 lg:block" />}
            </div>
          ))}
        </div>
      </section>

      <section className="bg-white">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1fr_1.1fr]">
          <div>
            <div className="kicker">Ранжирование</div>
            <h2 className="mt-2 text-[28px] font-bold leading-tight">Интерпретируемая формула вместо «чёрного ящика»</h2>
            <p className="mt-3 text-[15px] leading-relaxed text-ink-3">Score = Σ wᵢ·компонентаᵢ, затем «гейт» по обязательным навыкам: ×(0.5 + 0.5·покрытие). Без обязательных навыков высокий грейд и хорошие условия не выводят кандидата наверх. Каждая компонента возвращает человекочитаемые причины — это и есть объяснение выдачи.</p>
            <div className="mt-6 rounded-2xl bg-night p-5 font-mono text-[13px] leading-relaxed text-surface-2">
              score = 100 × (0.30·L + 0.30·S + w<sub>F</sub>·F + 0.15·C + 0.08·A + 0.07·D)<br />
              &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;× (0.5 + 0.5·must_coverage)<br />
              &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;× 0.85 если дороже вилки на 10%+ · × 0.85 если формат не совпадает<br />
              порядок: целевая категория → смежный грейд → смежная специализация
            </div>
            <div className="mt-6 flex flex-wrap gap-2"><Link to="/validation"><Button variant="outline">Как мы это проверили</Button></Link><a href="/api/docs"><Button variant="ghost">API подбора</Button></a></div>
          </div>
          <div className="space-y-2.5">
            {COMPONENTS.map(([k, n, w, d]) => (
              <div key={k} className="flex gap-4 rounded-2xl border border-line p-4">
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand-50 font-mono text-[18px] font-bold text-brand-600">{k}</div>
                <div><div className="flex items-center gap-2"><span className="text-[15px] font-semibold">{n}</span><Badge tone="brand">{w}</Badge></div><p className="mt-1 text-[13.5px] text-ink-3">{d}</p></div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
        <div className="kicker">Сравнение</div>
        <h2 className="mt-2 text-[28px] font-bold">Чем сценарий отличается от отклика на вакансию</h2>
        <div className="mt-6 overflow-x-auto rounded-2xl border border-line bg-white">
          <table className="w-full min-w-[720px] text-[14px]">
            <thead><tr className="border-b border-line bg-surface text-left"><th className="px-5 py-3 font-semibold"></th><th className="px-5 py-3 font-semibold">Доска вакансий</th><th className="px-5 py-3 font-semibold text-brand-700">Драфт</th></tr></thead>
            <tbody>
              {[
                ["Кто проявляет инициативу", "Кандидат откликается", "Работодатель приглашает конкретного человека"],
                ["Основа отбора", "Самоописанное резюме, ключевые слова", "Категория по тесту, подтверждённые навыки, ФСП"],
                ["Зарплата", "Часто «по договорённости»", "Вилка обязательна в каждом приглашении"],
                ["Контакты кандидата", "Видны в резюме", "Раскрываются только после принятия"],
                ["Обратная связь", "Тишина", "Статусы и причина отказа — работодатель видит, почему кандидаты отказываются"],
                ["Объяснимость", "Нет", "Разложение оценки и типы доказательств навыков"],
              ].map(([a, b, c]) => <tr key={a} className="border-b border-line last:border-0"><td className="px-5 py-3 font-medium">{a}</td><td className="px-5 py-3 text-ink-3">{b}</td><td className="px-5 py-3">{c}</td></tr>)}
            </tbody>
          </table>
        </div>
      </section>

      <section className="bg-white">
        <div className="mx-auto grid max-w-7xl gap-6 px-4 py-14 sm:px-6 md:grid-cols-2 lg:grid-cols-4">
          {[
            [<Wallet key="w" />, "Условия до общения", "Кандидат принимает решение, видя вилку, формат и компанию — а не после трёх собеседований."],
            [<Lock key="l" />, "Анонимность по умолчанию", "До принятия приглашения работодатель видит код кандидата, а не имя — меньше предвзятости."],
            [<ShieldAlert key="s" />, "Антифрод", "Индекс доверия компании (ИНН, домен почты, жалобы, доля принятых), лимиты приглашений, флаги «предоплаты» и нереалистичных вилок."],
            [<Trophy key="t" />, "Без истории ФСП — без штрафа", "Достижения поднимают внутри категории, но отсутствие ФСП не исключает кандидата из выдачи."],
          ].map(([icon, t, d], i) => (
            <div key={i}><div className="grid h-10 w-10 place-items-center rounded-xl bg-night text-white [&_svg]:h-5 [&_svg]:w-5">{icon}</div><h3 className="mt-3 font-sans text-[15px] font-semibold">{t}</h3><p className="mt-1 text-[13.5px] text-ink-3">{d}</p></div>
          ))}
        </div>
      </section>
    </div>
  );
}
