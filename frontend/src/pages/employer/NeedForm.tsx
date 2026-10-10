import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles, Wand2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CardHeader, ChoiceChips, Field, Input, PageLoader, Select, TagInput, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { GROSS_HINT } from "@/lib/format";

const EXAMPLE = `Ищем бэкенд-разработчика уровня Middle в команду платёжных сервисов.
Стек: Python, PostgreSQL, Docker, обязательно опыт с асинхронностью. Будет плюсом: Kafka, Redis, Kubernetes.
Финтех, высокая нагрузка. Гибрид или удалённо, Москва. Зарплата 220 000 – 300 000 ₽.`;

export default function NeedForm() {
  const { id } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: cat } = useCatalog();
  const { data: existing } = useQuery({ queryKey: ["emp-need", id], queryFn: () => api(`/employer/needs/${id}`), enabled: !!id });
  const [text, setText] = useState("");
  const [parsedNote, setParsedNote] = useState<string | null>(null);
  const [f, setF] = useState<any>({ title: "", description: "", specialization: "backend", grades: ["middle"], must_skills: [], nice_skills: [], work_formats: [], city: "",
    salary_from: "", salary_to: "", fsp_weight: 0.5, domains: [] });
  useEffect(() => { if (existing) setF({ ...existing, city: existing.city ?? "" }); }, [existing]);
  const parse = useMutation({
    mutationFn: () => api("/employer/needs/parse", { body: { text } }),
    onSuccess: (r: any) => {
      setF((p: any) => ({ ...p, title: r.title || p.title, description: text, specialization: r.specialization, grades: r.grades, must_skills: r.must_skills, nice_skills: r.nice_skills,
        work_formats: r.work_formats.length ? r.work_formats : p.work_formats, city: r.city ?? p.city, salary_from: r.salary_from ?? p.salary_from,
        salary_to: r.salary_to ?? p.salary_to, domains: r.domains }));
      setParsedNote(`Распознано: ${r.spec_name}, грейд ${r.grades.join("/")}, обязательные навыки — ${r.must_skills.length}, желательные — ${r.nice_skills.length}${r.salary_from ? (r.salary_converted_from_net ? ", вилка (указана «на руки» — пересчитана в gross по ставке НДФЛ 13%)" : ", вилка") : ""}. Проверьте и при необходимости поправьте.`);
    },
    onError: (e: ApiError) => toast.error(e.message),
  });
  const save = useMutation({
    mutationFn: () => api(id ? `/employer/needs/${id}` : "/employer/needs", { method: id ? "PUT" : "POST", body: { ...f, city: f.city || null, salary_from: Number(f.salary_from), salary_to: Number(f.salary_to), fsp_weight: Number(f.fsp_weight) } }),
    onSuccess: (r: any) => { qc.invalidateQueries(); toast.success("Подборка сформирована", { description: `Подходящих кандидатов: ${r.run?.total_matched ?? "—"}` }); nav(`/e/needs/${r.id}`); },
    onError: (e: ApiError) => toast.error(e.message, { description: Array.isArray(e.details) ? e.details.map((d: any) => d.msg).join("; ") : undefined }),
  });
  if (!cat || (id && !existing)) return <PageLoader />;
  const spec = cat.specializations.find((s) => s.code === f.specialization);
  const market = f.grades.map((g: string) => cat.market_salary[f.specialization]?.[g]).filter(Boolean);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e?.target ? e.target.value : e });
  const valid = f.title.length >= 3 && f.grades.length > 0 && Number(f.salary_from) > 0 && Number(f.salary_to) >= Number(f.salary_from);
  return (
    <div className="space-y-6">
      <PageHeader back={{ to: "/e/needs", label: "Потребности" }} title={id ? "Изменить потребность" : "Кого вы ищете?"}
        subtitle="Опишите потребность — на её основе формируется подборка из категорий, присвоенных тестом. Вилка зарплаты обязательна: кандидат увидит её в приглашении." />
      {!id && (
        <Card className="overflow-hidden">
          <div className="bg-night p-5 text-white">
            <div className="flex items-center gap-2 text-[15px] font-semibold"><Wand2 className="h-5 w-5 text-brand-300" />Опишите простым текстом — заполним форму автоматически</div>
            <Textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} placeholder={EXAMPLE} className="mt-3 border-white/10 bg-white/5 text-white placeholder:text-white/30" />
            <div className="mt-3 flex flex-wrap gap-2">
              <Button loading={parse.isPending} disabled={text.length < 10} icon={<Sparkles className="h-4 w-4" />} onClick={() => parse.mutate()}>Разобрать текст</Button>
              <Button variant="ghost" className="text-white/70 hover:bg-white/10 hover:text-white" onClick={() => setText(EXAMPLE)}>Подставить пример</Button>
            </div>
          </div>
          {parsedNote && <div className="p-4"><Alert tone="ok">{parsedNote}</Alert></div>}
        </Card>
      )}
      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <Card>
          <CardHeader title="Потребность" />
          <div className="grid gap-4 px-5 pb-5">
            <Field label="Название" required><Input value={f.title} onChange={set("title")} placeholder="Backend-разработчик в команду биллинга" /></Field>
            <Field label="Чем занимается команда, задачи" hint="Используется в объяснении и для текстовой близости с профилями"><Textarea rows={4} value={f.description ?? ""} onChange={set("description")} /></Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Специализация" required><Select value={f.specialization} onChange={set("specialization")}>{cat.specializations.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}</Select></Field>
              <Field label="Город"><Input list="cities-n" value={f.city} onChange={set("city")} /><datalist id="cities-n">{cat.cities.map((c) => <option key={c} value={c} />)}</datalist></Field>
            </div>
            <Field label="Грейд (категории подборки)" required hint="Можно выбрать несколько соседних грейдов"><ChoiceChips multi options={cat.grades} value={f.grades} onChange={(v) => setF({ ...f, grades: v })} /></Field>
            <Field label="Обязательные навыки" hint="Без них кандидат теряет релевантность — проверяем по тесту, ФСП, задачам и резюме"><TagInput value={f.must_skills} onChange={(v) => setF({ ...f, must_skills: v })} suggestions={[...(spec?.core_skills ?? []), ...cat.skills.map((s) => s.name)]} /></Field>
            <Field label="Желательные навыки"><TagInput value={f.nice_skills} onChange={(v) => setF({ ...f, nice_skills: v })} suggestions={cat.skills.map((s) => s.name)} /></Field>
            <Field label="Отрасль проекта"><ChoiceChips multi options={cat.domains} value={f.domains} onChange={(v) => setF({ ...f, domains: v })} /></Field>
          </div>
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader title="Условия" />
            <div className="grid gap-4 px-5 pb-5">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Зарплата от, ₽ gross" hint={GROSS_HINT} required><Input type="number" value={f.salary_from} onChange={set("salary_from")} /></Field>
                <Field label="до, ₽" required><Input type="number" value={f.salary_to} onChange={set("salary_to")} /></Field>
              </div>
              {market.length > 0 && <div className="text-[12.5px] text-ink-3">Медиана рынка для выбранных категорий: {market.map((m: number) => `${Math.round(m / 1000)} тыс.`).join(" / ")}</div>}
              <Field label="Формат работы"><ChoiceChips multi options={cat.work_formats} value={f.work_formats} onChange={(v) => setF({ ...f, work_formats: v })} /></Field>
            </div>
          </Card>
          <Card>
            <CardHeader title="Важность достижений ФСП" subtitle="Насколько поднимать в выдаче участников и призёров соревнований" />
            <div className="px-5 pb-5">
              <input type="range" min={0} max={1} step={0.1} value={f.fsp_weight} onChange={set("fsp_weight")} className="w-full accent-[#402FFF]" />
              <div className="mt-1 flex justify-between text-[12px] text-ink-3"><span>не важно</span><Badge tone="brand">{Math.round(f.fsp_weight * 100)}%</Badge><span>очень важно</span></div>
            </div>
          </Card>
          <Button size="lg" className="w-full" disabled={!valid} loading={save.isPending} onClick={() => save.mutate()}>{id ? "Сохранить и пересчитать подборку" : "Сформировать подборку"}</Button>
        </div>
      </div>
    </div>
  );
}
