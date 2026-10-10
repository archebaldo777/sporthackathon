import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Link2, RefreshCw, ShieldCheck, Trash2, Trophy, Unlink } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { FspPanel } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CardHeader, Input, Modal, PageLoader, Toggle } from "@/components/ui";
import { api, ApiError, download } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateTime } from "@/lib/format";

export default function Settings() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const { logout } = useAuth();
  const { data: me, isLoading } = useQuery({ queryKey: ["cand-me"], queryFn: () => api("/candidate/me") });
  const { data: cons } = useQuery({ queryKey: ["consents"], queryFn: () => api("/candidate/consents") });
  const [del, setDel] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const inv = () => qc.invalidateQueries();
  const priv = useMutation({ mutationFn: (body: any) => api("/candidate/settings/privacy", { method: "PUT", body }), onSuccess: () => { inv(); toast.success("Сохранено"); }, onError: (e: ApiError) => toast.error(e.message) });
  const consent = useMutation({ mutationFn: (body: any) => api("/candidate/consents", { body }), onSuccess: inv, onError: (e: ApiError) => toast.error(e.message) });
  const link = useMutation({ mutationFn: () => api("/auth/fsp/link"), onSuccess: (r: any) => (window.location.href = r.authorize_url), onError: (e: ApiError) => toast.error(e.message) });
  const sync = useMutation({ mutationFn: () => api("/candidate/fsp/sync", { method: "POST" }), onSuccess: (r: any) => { inv(); toast.success(`Достижения обновлены: ${r.achievements}`); }, onError: (e: ApiError) => toast.error(e.message) });
  const unlink = useMutation({ mutationFn: () => api("/candidate/fsp", { method: "DELETE" }), onSuccess: () => { inv(); toast.success("ФСП ID отвязан"); } });
  const remove = useMutation({ mutationFn: () => api("/candidate/account", { method: "DELETE" }), onSuccess: () => { logout(); nav("/"); toast.success("Аккаунт и данные удалены"); } });
  if (isLoading || !me) return <PageLoader />;
  const p = me.privacy || {};
  return (
    <div className="space-y-6">
      <PageHeader title="Настройки, приватность и ФСП ID" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader icon={<Trophy className="h-5 w-5" />} title="Связь с ФСП ID" subtitle="Вход через ФСП ID (OIDC, Keycloak). Результаты соревнований приходят из реестра ФСП и отмечаются как подтверждённые." />
          <div className="space-y-4 px-5 pb-5">
            {me.fsp?.linked ? (
              <>
                <div className="flex flex-wrap items-center gap-2"><Badge tone="fsp">ФСП ID: {me.fsp.fsp_id}</Badge><Badge tone="ok">{me.fsp.count} результатов</Badge></div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="secondary" icon={<RefreshCw className="h-4 w-4" />} loading={sync.isPending} onClick={() => sync.mutate()}>Обновить из реестра</Button>
                  <Button variant="ghost" icon={<Unlink className="h-4 w-4" />} onClick={() => unlink.mutate()}>Отвязать</Button>
                </div>
                <div className="max-h-72 overflow-y-auto"><FspPanel fsp={me.fsp} own /></div>
              </>
            ) : (
              <>
                <Alert tone="brand">История ФСП необязательна: категория определяется тестом. Если вы участвовали в соревнованиях ФСП, достижения поднимут вас в выдаче внутри категории.</Alert>
                <Button variant="dark" icon={<Link2 className="h-4 w-4" />} loading={link.isPending} onClick={() => link.mutate()}>Связать с ФСП ID</Button>
              </>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader icon={<ShieldCheck className="h-5 w-5" />} title="Что видно работодателю" subtitle="Контакты (e-mail, телефон, Telegram) раскрываются только после принятия приглашения или вашего отклика." />
          <div className="space-y-4 px-5 pb-5">
            <Toggle checked={!!me.visible} onChange={(v) => priv.mutate({ visible: v })} label="Профиль опубликован в базе" description="Если выключить — вы пропадёте из поиска и подборок; согласие на публикацию будет отозвано." />
            <Toggle checked={!p.hide_name} onChange={(v) => priv.mutate({ hide_name: !v })} label="Показывать имя до принятия приглашения" description="По умолчанию работодатель видит код кандидата — это снижает предвзятость." />
            <Toggle checked={!p.hide_current_company} onChange={(v) => priv.mutate({ hide_current_company: !v })} label="Показывать текущего работодателя" />
            <Toggle checked={!!p.show_salary} onChange={(v) => priv.mutate({ show_salary: v })} label="Показывать ожидания по зарплате" />
            <Toggle checked={!!p.show_fsp} onChange={(v) => priv.mutate({ show_fsp: v })} label="Показывать достижения ФСП" />
            <Toggle checked={!!p.show_tasks} onChange={(v) => priv.mutate({ show_tasks: v })} label="Показывать результаты регулярных задач" />
          </div>
        </Card>
      </div>
      <Card>
        <CardHeader title="Согласия (152-ФЗ)" subtitle="Журнал согласий хранится с версией документа, датой и IP" />
        <div className="grid gap-4 px-5 pb-5 lg:grid-cols-2">
          <div className="space-y-4">
            {cons && Object.entries(cons.kinds).map(([k, name]: any) => (
              <Toggle key={k} checked={!!cons.current[k]} onChange={(v) => consent.mutate({ kind: k, granted: v })} label={name}
                description={k === "pd_processing" ? "Обязательно для работы сервиса. Для отзыва — удалите аккаунт." : undefined} />
            ))}
          </div>
          <div className="max-h-56 overflow-y-auto rounded-xl bg-surface p-3">
            {(cons?.log ?? []).map((l: any, i: number) => (
              <div key={i} className="flex justify-between gap-3 py-1 text-[12.5px]"><span>{(cons.all_kinds ?? cons.kinds)[l.kind]} · v{l.version}</span><span className={l.granted ? "text-ok-700" : "text-accent-600"}>{l.granted ? "дано" : "отозвано"} · {dateTime(l.created_at)}</span></div>
            ))}
          </div>
        </div>
      </Card>
      <Card>
        <CardHeader title="Мои данные" />
        <div className="flex flex-wrap gap-3 px-5 pb-5">
          <Button variant="outline" icon={<Download className="h-4 w-4" />} onClick={() => download("/candidate/export", `draft-data-${me.code}.json`)}>Выгрузить все мои данные</Button>
          <Button variant="danger" icon={<Trash2 className="h-4 w-4" />} onClick={() => setDel(true)}>Удалить аккаунт</Button>
        </div>
      </Card>
      <Modal open={del} onClose={() => setDel(false)} title="Удалить аккаунт?"
        footer={<><Button variant="ghost" onClick={() => setDel(false)}>Отмена</Button><Button variant="danger" disabled={confirmText !== "УДАЛИТЬ"} loading={remove.isPending} onClick={() => remove.mutate()}>Удалить навсегда</Button></>}>
        <p className="text-[14px] text-ink-2">Будут удалены профиль, результаты тестов, приглашения и отклики. Действие необратимо. Введите <b>УДАЛИТЬ</b> для подтверждения.</p>
        <Input className="mt-3" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />
      </Modal>
    </div>
  );
}
