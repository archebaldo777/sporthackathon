import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/Layouts";
import { Badge, Button, Card, CardHeader, CompanyMark, Field, Input, Meter, PageLoader, Select, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";

export default function Company() {
  const qc = useQueryClient();
  const { data: cat } = useCatalog();
  const { data, isLoading } = useQuery({ queryKey: ["emp-company"], queryFn: () => api("/employer/company") });
  const [f, setF] = useState<any>(null);
  useEffect(() => { if (data && !f) setF({ ...data }); }, [data]); // eslint-disable-line
  const save = useMutation({
    mutationFn: () => { const { name, description, industry, website, size, city, contact_name, contact_email, contact_phone, telegram, inn } = f;
      return api("/employer/company", { method: "PUT", body: { name, description, industry, website, size, city, contact_name, contact_email: contact_email || null, contact_phone, telegram, inn: inn || null } }); },
    onSuccess: (r: any) => { setF({ ...r }); qc.invalidateQueries(); toast.success("Профиль компании сохранён", { description: `Индекс доверия: ${r.trust_score}` }); },
    onError: (e: ApiError) => toast.error(e.message, { description: Array.isArray(e.details) ? e.details.map((d: any) => d.msg).join("; ") : undefined }),
  });
  if (isLoading || !f || !cat) return <PageLoader />;
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  return (
    <div className="space-y-6">
      <PageHeader title="Профиль компании" subtitle="Кандидат видит название, описание и индекс доверия в каждом приглашении." action={<Button loading={save.isPending} onClick={() => save.mutate()}>Сохранить</Button>} />
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader title="О компании" />
          <div className="grid gap-4 px-5 pb-5 sm:grid-cols-2">
            <div className="flex items-center gap-3 sm:col-span-2"><CompanyMark name={f.name} accent={f.accent} size={52} /><Field label="Название" className="flex-1"><Input value={f.name} onChange={set("name")} /></Field></div>
            <Field label="Описание" className="sm:col-span-2"><Textarea rows={4} value={f.description ?? ""} onChange={set("description")} /></Field>
            <Field label="Направление деятельности"><Select value={f.industry ?? ""} onChange={set("industry")}><option value="">—</option>{cat.domains.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}</Select></Field>
            <Field label="Размер"><Select value={f.size ?? ""} onChange={set("size")}><option value="">—</option>{["1–10", "10–50", "50–200", "200–500", "500–1000", "1000+"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
            <Field label="Сайт"><Input value={f.website ?? ""} onChange={set("website")} placeholder="https://" /></Field>
            <Field label="Город"><Input value={f.city ?? ""} onChange={set("city")} /></Field>
            <Field label="ИНН" hint="Проверяется контрольная сумма; в продакшене — сверка с ЕГРЮЛ"><Input value={f.inn ?? ""} onChange={set("inn")} /></Field>
          </div>
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader icon={<ShieldCheck className="h-5 w-5" />} title={`Индекс доверия: ${f.trust_score}`} subtitle={`Уровень «${{ low: "низкий", mid: "средний", high: "высокий" }[f.trust_tier as string]}» · до ${f.daily_invite_limit} приглашений в сутки (сегодня ${f.invites_today})`} />
            <div className="space-y-2 px-5 pb-5">
              <Meter value={f.trust_score / 100} tone={f.trust_score >= 70 ? "ok" : f.trust_score >= 45 ? "warn" : "danger"} />
              {(f.trust_factors ?? []).map((x: any, i: number) => <div key={i} className="flex justify-between gap-3 text-[13px]"><span className="text-ink-2">{x.label}</span><Badge tone={x.delta > 0 ? "ok" : x.delta < 0 ? "danger" : "neutral"}>{x.delta > 0 ? `+${x.delta}` : x.delta}</Badge></div>)}
            </div>
          </Card>
          <Card>
            <CardHeader title="Контакты для кандидатов" />
            <div className="grid gap-3 px-5 pb-5">
              <Field label="Контактное лицо"><Input value={f.contact_name ?? ""} onChange={set("contact_name")} /></Field>
              <Field label="E-mail"><Input value={f.contact_email ?? ""} onChange={set("contact_email")} /></Field>
              <Field label="Телефон"><Input value={f.contact_phone ?? ""} onChange={set("contact_phone")} /></Field>
              <Field label="Telegram"><Input value={f.telegram ?? ""} onChange={set("telegram")} /></Field>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
