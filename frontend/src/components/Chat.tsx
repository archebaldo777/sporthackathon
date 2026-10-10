import clsx from "clsx";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessagesSquare, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { dateTime } from "@/lib/format";

/** Переписка внутри принятого приглашения: стороны общаются на платформе, не раскрывая контакты. */
export function Chat({ base, counterpart }: { base: string; counterpart: string }) {
  const qc = useQueryClient();
  const key = ["messages", base];
  const { data } = useQuery({ queryKey: key, queryFn: () => api(`${base}/messages`), refetchInterval: 15000 });
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const send = useMutation({
    mutationFn: () => api(`${base}/messages`, { body: { text } }),
    onSuccess: () => { setText(""); qc.invalidateQueries({ queryKey: key }); },
    onError: (e: ApiError) => toast.error(e.message),
  });
  const items = data?.items ?? [];
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [items.length]);
  return (
    <div className="rounded-xl border border-line">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3 text-[14px] font-semibold">
        <MessagesSquare className="h-4 w-4 text-brand-500" />Переписка с {counterpart}
        <span className="ml-auto text-[12px] font-normal text-ink-3">контакты для переписки не нужны</span>
      </div>
      <div className="max-h-80 space-y-2 overflow-y-auto px-4 py-3">
        {items.length === 0 && <p className="py-4 text-center text-[13px] text-ink-3">Сообщений пока нет — договоритесь о созвоне прямо здесь.</p>}
        {items.map((m: any) => (
          <div key={m.id} className={clsx("flex", m.mine ? "justify-end" : "justify-start")}>
            <div className={clsx("max-w-[80%] rounded-2xl px-3.5 py-2 text-[14px]", m.mine ? "bg-brand-500 text-white" : "bg-surface text-ink")}>
              <div className="whitespace-pre-line break-words">{m.text}</div>
              <div className={clsx("mt-1 text-[11px]", m.mine ? "text-white/70" : "text-ink-4")}>{dateTime(m.created_at)}{m.mine && m.read ? " · прочитано" : ""}</div>
            </div>
          </div>
        ))}
        <div ref={end} />
      </div>
      <form className="flex items-end gap-2 border-t border-line p-3" onSubmit={(e) => { e.preventDefault(); if (text.trim()) send.mutate(); }}>
        <Textarea rows={2} value={text} maxLength={2000} onChange={(e) => setText(e.target.value)} placeholder="Сообщение…" className="min-w-0 flex-1"
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && text.trim()) send.mutate(); }} />
        <Button type="submit" loading={send.isPending} disabled={!text.trim()} icon={<Send className="h-4 w-4" />} aria-label="Отправить">Отправить</Button>
      </form>
    </div>
  );
}
