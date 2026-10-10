import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, KeyRound, Trash2, Webhook } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CardHeader, Checkbox, Field, Input, PageLoader } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { dateTime } from "@/lib/format";

export default function Integrations() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["emp-integrations"], queryFn: () => api("/employer/integrations") });
  const [name, setName] = useState("ATS");
  const [created, setCreated] = useState<any>(null);
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<string[]>(["invitation.accepted", "application.created"]);
  const inv = () => qc.invalidateQueries({ queryKey: ["emp-integrations"] });
  const createKey = useMutation({ mutationFn: () => api("/employer/api-keys", { body: { name } }), onSuccess: (r) => { setCreated(r); inv(); } });
  const revoke = useMutation({ mutationFn: (id: number) => api(`/employer/api-keys/${id}`, { method: "DELETE" }), onSuccess: inv });
  const createHook = useMutation({ mutationFn: () => api("/employer/webhooks", { body: { url, events } }), onSuccess: (r: any) => { toast.success("Вебхук создан", { description: `Секрет подписи: ${r.secret}` }); setUrl(""); inv(); }, onError: (e: ApiError) => toast.error(e.message) });
  const delHook = useMutation({ mutationFn: (id: number) => api(`/employer/webhooks/${id}`, { method: "DELETE" }), onSuccess: inv });
  if (isLoading || !data) return <PageLoader />;
  return (
    <div className="space-y-6">
      <PageHeader title="Интеграция с ATS" subtitle="Синхронизация с вашей ATS (Huntflow, Potok, E-Staff и др.) без ручного дублирования: вакансии из ATS, отклики и кандидаты в ATS, статусы в обе стороны. API по ключу и вебхуки с HMAC-подписью." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader icon={<KeyRound className="h-5 w-5" />} title="API-ключи" subtitle="Заголовок X-API-Key · полный список — в документации API (раздел «ATS-интеграция»)" />
          <div className="mx-5 mb-3 grid gap-1 rounded-xl bg-surface p-3 font-mono text-[11.5px] text-ink-2">
            {[["PUT", "/ats/v1/vacancies/{external_id}", "вакансия из ATS"], ["GET", "/ats/v1/applications", "отклики с контактами"],
              ["PUT", "/ats/v1/applications/{id}/status", "статус отклика"], ["GET", "/ats/v1/candidates", "принявшие приглашение"],
              ["PUT", "/ats/v1/invitations/{id}/stage", "этап найма"]].map(([m, path, d]) => (
              <div key={path} className="flex flex-wrap gap-x-2"><b className="w-8">{m}</b><span>{path}</span><span className="font-sans text-ink-3">— {d}</span></div>
            ))}
          </div>
          <div className="space-y-3 px-5 pb-5">
            {created && <Alert tone="ok" title="Ключ создан — сохраните его, он показывается один раз"><code className="break-all font-mono text-[12.5px]">{created.key}</code>
              <button className="ml-2 inline-flex items-center gap-1 text-[12px] underline" onClick={() => { navigator.clipboard?.writeText(created.key); toast.success("Скопировано"); }}><Copy className="h-3.5 w-3.5" />копировать</button></Alert>}
            <div className="flex gap-2"><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Название ключа" /><Button loading={createKey.isPending} onClick={() => createKey.mutate()}>Создать</Button></div>
            {data.api_keys.map((k: any) => (
              <div key={k.id} className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5 text-[13.5px]">
                <div><div className="font-medium">{k.name}</div><div className="font-mono text-[12px] text-ink-3">{k.prefix}… · {k.last_used_at ? `использован ${dateTime(k.last_used_at)}` : "не использовался"}</div></div>
                <Button size="sm" variant="ghost" onClick={() => revoke.mutate(k.id)}><Trash2 className="h-4 w-4" /></Button>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader icon={<Webhook className="h-5 w-5" />} title="Вебхуки" subtitle="POST JSON с заголовками X-Draft-Event и X-Draft-Signature (sha256 HMAC), 3 попытки доставки" />
          <div className="space-y-3 px-5 pb-5">
            <Field label="URL"><Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://ats.company.ru/hooks/draft" /></Field>
            <div className="space-y-1.5">{Object.entries(data.events).map(([e, d]: any) => <Checkbox key={e} checked={events.includes(e)} onChange={(v) => setEvents(v ? [...events, e] : events.filter((x) => x !== e))} label={<><code className="font-mono text-[12.5px]">{e}</code> — {d}</>} />)}</div>
            <Button disabled={!/^https?:\/\//.test(url) || !events.length} loading={createHook.isPending} onClick={() => createHook.mutate()}>Добавить вебхук</Button>
            {data.webhooks.map((h: any) => (
              <div key={h.id} className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5 text-[13px]"><div className="min-w-0"><div className="truncate font-mono">{h.url}</div><div className="text-ink-3">{h.events.join(", ")}</div></div><Button size="sm" variant="ghost" onClick={() => delHook.mutate(h.id)}><Trash2 className="h-4 w-4" /></Button></div>
            ))}
          </div>
        </Card>
      </div>
      {data.deliveries.length > 0 && (
        <Card>
          <CardHeader title="Журнал доставки" />
          <div className="divide-y divide-line px-5 pb-3 text-[13px]">
            {data.deliveries.map((d: any) => <div key={d.id} className="flex items-center justify-between py-2"><span className="font-mono">{d.event}</span><span className="text-ink-3">{dateTime(d.created_at)} · попыток {d.attempts}</span><Badge tone={d.ok ? "ok" : "danger"}>{d.ok ? `HTTP ${d.status_code}` : d.error ? "ошибка" : `HTTP ${d.status_code}`}</Badge></div>)}
          </div>
        </Card>
      )}
    </div>
  );
}
