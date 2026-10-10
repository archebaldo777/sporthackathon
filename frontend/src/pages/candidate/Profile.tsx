import clsx from "clsx";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileUp, Plus, Sparkles, Trash2, Wand2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CardHeader, Checkbox, ChoiceChips, Field, Input, Modal, PageLoader, Select, TagInput, Textarea, Toggle } from "@/components/ui";
import { api, ApiError, download } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { GROSS_HINT } from "@/lib/format";

const FIELD_NAMES: Record<string, string> = {
  full_name: "ФИО", email: "E-mail", phone: "Телефон", telegram: "Telegram", github: "GitHub", city: "Город", headline: "Должность",
  skills: "Стек", experience_years: "Стаж, лет", declared_grade: "Грейд", specialization: "Специализация", roles: "Роли", team_role: "Роль в команде",
  soft_skills: "Софт-скиллы", domains: "Отрасли", education: "Образование", about: "О себе",
};

export default function Profile() {
  const qc = useQueryClient();
  const { data: me, isLoading } = useQuery({ queryKey: ["cand-me"], queryFn: () => api("/candidate/me") });
  const { data: cat } = useCatalog();
  const [f, setF] = useState<any>(null);
  const [parsed, setParsed] = useState<any>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (me && !f) setF({
      full_name: me.contacts?.full_name ?? "", headline: me.headline ?? "", phone: me.contacts?.phone ?? "", telegram: me.contacts?.telegram ?? "",
      github: me.contacts?.github ?? "", city: me.city ?? "", relocation: me.relocation, about: me.about ?? "", experience_years: me.experience_years ?? "",
      work_formats: me.work_formats ?? [], salary_from: me.salary_from ?? "", salary_to: me.salary_to ?? "", search_status: me.search_status,
      skills: me.skills ?? [], soft_skills: me.soft_skills ?? [], domains: me.domains ?? [], experience: me.experience ?? [], education: me.education ?? [],
    });
  }, [me]); // eslint-disable-line
  const save = useMutation({
    mutationFn: () => api("/candidate/profile", {
      method: "PUT",
      body: { ...f, experience_years: f.experience_years === "" ? null : Number(f.experience_years), salary_from: f.salary_from === "" ? null : Number(f.salary_from),
        salary_to: f.salary_to === "" ? null : Number(f.salary_to) },
    }),
    onSuccess: () => { toast.success("Профиль сохранён"); qc.invalidateQueries(); },
    onError: (e: ApiError) => toast.error(e.message),
  });
  const upload = useMutation({
    mutationFn: (file: File) => { const fd = new FormData(); fd.append("file", file); return api("/candidate/resume/parse", { form: fd }); },
    onSuccess: (r: any) => setParsed(r),
    onError: (e: ApiError) => toast.error(e.message),
  });
  if (isLoading || !f || !cat) return <PageLoader />;
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e?.target ? e.target.value : e });
  return (
    <div className="space-y-6">
      <PageHeader title="Профиль и резюме" subtitle="Заполните вручную или загрузите PDF — поля распознаются автоматически. Категорию определяет тест, но профиль помогает в ранжировании и объяснении выдачи."
        action={<><Button variant="outline" icon={<Download className="h-4 w-4" />} onClick={() => download("/candidate/profile/pdf", `draft-profile-${me.code}.pdf`)}>Стандартизированный PDF</Button>
          <Button loading={save.isPending} onClick={() => save.mutate()}>Сохранить</Button></>} />

      <Card className="overflow-hidden">
        <div className="flex flex-col items-start gap-4 bg-gradient-to-r from-brand-500 to-brand-700 p-6 text-white sm:flex-row sm:items-center">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-white/15"><Wand2 /></div>
          <div className="flex-1">
            <div className="text-[17px] font-semibold">Загрузите резюме в PDF</div>
            <div className="mt-0.5 text-[14px] text-white/75">Распознаём ФИО, контакты, стек, стаж, грейд, роли и софт-скиллы. Вы проверите результат перед сохранением.</div>
          </div>
          <input ref={fileRef} type="file" accept="application/pdf" className="hidden" onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])} />
          <Button variant="dark" loading={upload.isPending} icon={<FileUp className="h-4 w-4" />} onClick={() => fileRef.current?.click()}>Выбрать PDF</Button>
        </div>
        {me.resume_filename && <div className="px-6 py-2.5 text-[13px] text-ink-3">Последнее загруженное резюме: {me.resume_filename}</div>}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Основное" subtitle="Контакты раскрываются работодателю только после принятия приглашения" />
          <div className="grid gap-4 px-5 pb-5 sm:grid-cols-2">
            <Field label="ФИО" className="sm:col-span-2"><Input value={f.full_name} onChange={set("full_name")} /></Field>
            <Field label="Должность / заголовок" className="sm:col-span-2"><Input value={f.headline} onChange={set("headline")} placeholder="Backend-разработчик · Python" /></Field>
            <Field label="Телефон"><Input value={f.phone} onChange={set("phone")} placeholder="+7…" /></Field>
            <Field label="Telegram"><Input value={f.telegram} onChange={set("telegram")} placeholder="@username" /></Field>
            <Field label="GitHub" className="sm:col-span-2"><Input value={f.github} onChange={set("github")} placeholder="https://github.com/…" /></Field>
            <Field label="Город">
              <Input list="cities" value={f.city} onChange={set("city")} />
              <datalist id="cities">{cat.cities.map((c) => <option key={c} value={c} />)}</datalist>
            </Field>
            <Field label="Стаж, лет"><Input type="number" step={0.5} min={0} value={f.experience_years} onChange={set("experience_years")} /></Field>
            <div className="sm:col-span-2"><Toggle checked={!!f.relocation} onChange={(v) => setF({ ...f, relocation: v })} label="Готов к переезду" /></div>
          </div>
        </Card>
        <Card>
          <CardHeader title="Условия" subtitle="Ожидания по зарплате помогают работодателю сделать реалистичное предложение" />
          <div className="grid gap-4 px-5 pb-5 sm:grid-cols-2">
            <Field label="Зарплата от, ₽ gross" hint={GROSS_HINT}><Input type="number" value={f.salary_from} onChange={set("salary_from")} /></Field>
            <Field label="до, ₽"><Input type="number" value={f.salary_to} onChange={set("salary_to")} /></Field>
            <Field label="Формат работы" className="sm:col-span-2"><ChoiceChips multi options={cat.work_formats} value={f.work_formats} onChange={(v) => setF({ ...f, work_formats: v })} /></Field>
            <Field label="Статус поиска" className="sm:col-span-2"><ChoiceChips options={cat.search_statuses} value={f.search_status} onChange={(v) => setF({ ...f, search_status: v })} /></Field>
            <Field label="Отраслевой опыт" className="sm:col-span-2"><ChoiceChips multi options={cat.domains} value={f.domains} onChange={(v) => setF({ ...f, domains: v })} /></Field>
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Навыки" subtitle="Синонимы приводятся к единой онтологии («postgres» → PostgreSQL). Подтверждённые тестом навыки отмечаются автоматически." />
        <div className="grid gap-5 px-5 pb-5 lg:grid-cols-2">
          <Field label="Технический стек"><TagInput value={f.skills} onChange={(v) => setF({ ...f, skills: v })} suggestions={cat.skills.map((s) => s.name)} placeholder="Начните вводить навык…" /></Field>
          <Field label="Софт-скиллы"><ChoiceChips multi options={cat.soft_skills.map((s) => ({ code: s, name: s }))} value={f.soft_skills} onChange={(v) => setF({ ...f, soft_skills: v })} /></Field>
          {me.verified_skills?.length > 0 && <div className="lg:col-span-2"><div className="kicker mb-2">Подтверждены тестом</div><div className="flex flex-wrap gap-1.5">{me.verified_skills.map((s: string) => <Badge key={s} tone="brand">✓ {s}</Badge>)}</div></div>}
          <Field label="О себе" className="lg:col-span-2"><Textarea rows={3} value={f.about} onChange={set("about")} /></Field>
        </div>
      </Card>

      <Card>
        <CardHeader title="Опыт работы" action={<Button size="sm" variant="secondary" icon={<Plus className="h-4 w-4" />} onClick={() => setF({ ...f, experience: [...f.experience, { company: "", title: "", start: "", end: "", description: "" }] })}>Добавить</Button>} />
        <div className="space-y-3 px-5 pb-5">
          {f.experience.length === 0 && <p className="text-[13.5px] text-ink-3">Опыт не указан.</p>}
          {f.experience.map((e: any, i: number) => (
            <div key={i} className="grid gap-3 rounded-xl border border-line p-4 sm:grid-cols-[1fr_1fr_110px_110px_auto]">
              <Input placeholder="Компания" value={e.company ?? ""} onChange={(x) => { const ex = [...f.experience]; ex[i] = { ...e, company: x.target.value }; setF({ ...f, experience: ex }); }} />
              <Input placeholder="Должность" value={e.title ?? ""} onChange={(x) => { const ex = [...f.experience]; ex[i] = { ...e, title: x.target.value }; setF({ ...f, experience: ex }); }} />
              <Input placeholder="С (год)" value={e.start ?? ""} onChange={(x) => { const ex = [...f.experience]; ex[i] = { ...e, start: x.target.value }; setF({ ...f, experience: ex }); }} />
              <Input placeholder="По (н.в.)" value={e.end ?? ""} onChange={(x) => { const ex = [...f.experience]; ex[i] = { ...e, end: x.target.value }; setF({ ...f, experience: ex }); }} />
              <Button variant="ghost" aria-label="Удалить" onClick={() => setF({ ...f, experience: f.experience.filter((_: any, j: number) => j !== i) })}><Trash2 className="h-4 w-4" /></Button>
              <Textarea rows={2} className="sm:col-span-5" placeholder="Задачи и достижения" value={e.description ?? ""} onChange={(x) => { const ex = [...f.experience]; ex[i] = { ...e, description: x.target.value }; setF({ ...f, experience: ex }); }} />
            </div>
          ))}
        </div>
      </Card>
      <div className="flex justify-end"><Button size="lg" loading={save.isPending} onClick={() => save.mutate()}>Сохранить профиль</Button></div>

      <ParsedModal parsed={parsed} onClose={() => setParsed(null)} onApply={(vals) => { setF({ ...f, ...vals }); setParsed(null); toast.success("Поля перенесены в форму — проверьте и сохраните"); }} />
    </div>
  );
}

function ParsedModal({ parsed, onClose, onApply }: { parsed: any; onClose: () => void; onApply: (v: any) => void }) {
  const [sel, setSel] = useState<Record<string, boolean>>({});
  const fields = parsed?.fields ?? {};
  useEffect(() => {
    if (!parsed) return;
    const s: Record<string, boolean> = {};
    Object.entries(fields).forEach(([k, v]: any) => { s[k] = v.value != null && (!Array.isArray(v.value) || v.value.length > 0) && v.confidence >= 0.5 && k !== "email"; });
    setSel(s);
  }, [parsed]); // eslint-disable-line
  if (!parsed) return null;
  const show = (v: any) => (Array.isArray(v) ? v.map((x) => (typeof x === "object" ? Object.values(x).join(" ") : x)).join(", ") : String(v));
  const apply = () => {
    const out: any = {};
    for (const [k, on] of Object.entries(sel)) {
      if (!on) continue;
      const v = fields[k].value;
      if (["full_name", "phone", "telegram", "github", "city", "headline", "about"].includes(k)) out[k] = v;
      if (k === "skills") out.skills = v;
      if (k === "soft_skills") out.soft_skills = v;
      if (k === "domains") out.domains = v;
      if (k === "experience_years") out.experience_years = v;
      if (k === "education") out.education = v;
    }
    onApply(out);
  };
  return (
    <Modal open={!!parsed} onClose={onClose} wide title="Распознанные данные резюме"
      footer={<><Button variant="ghost" onClick={onClose}>Отмена</Button><Button icon={<Sparkles className="h-4 w-4" />} onClick={apply}>Перенести выбранное в профиль</Button></>}>
      <Alert tone="brand">Отметьте поля, которые нужно перенести. Уверенность распознавания указана справа. Специализация и грейд из резюме используются только как подсказка — категорию определяет тест.</Alert>
      <div className="mt-4 divide-y divide-line">
        {Object.entries(fields).map(([k, v]: any) => {
          const empty = v.value == null || (Array.isArray(v.value) && !v.value.length);
          return (
            <div key={k} className={clsx("flex items-start gap-3 py-3", empty && "opacity-50")}>
              <Checkbox checked={!!sel[k]} disabled={empty || ["specialization", "declared_grade", "roles", "team_role", "email"].includes(k)} onChange={(x) => setSel({ ...sel, [k]: x })} label="" />
              <div className="w-36 shrink-0 text-[13px] font-medium text-ink-2">{FIELD_NAMES[k] ?? k}</div>
              <div className="min-w-0 flex-1 text-[13.5px]">{empty ? <span className="text-ink-4">не найдено</span> : show(v.value)}</div>
              {!empty && <Badge tone={v.confidence >= 0.8 ? "ok" : v.confidence >= 0.5 ? "warn" : "neutral"}>{Math.round(v.confidence * 100)}%</Badge>}
            </div>
          );
        })}
      </div>
    </Modal>
  );
}
