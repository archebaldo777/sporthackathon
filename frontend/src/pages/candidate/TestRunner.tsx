import clsx from "clsx";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Clock, FlaskConical, Flag, Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Alert, Badge, Button, Card, DataTable, Input, Modal, PageLoader, RichText } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

const LANG_LABEL: Record<string, string> = { python: "Python", javascript: "JavaScript", java: "Java", go: "Go", csharp: "C#", kotlin: "Kotlin",
  php: "PHP", swift: "Swift", dart: "Dart", sql: "SQL", jsx: "React / JSX", css: "CSS", html: "HTML", yaml: "YAML", dockerfile: "Dockerfile", text: "" };

export default function TestRunner() {
  const { id } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["cand-me"], queryFn: () => api("/candidate/me") });
  const { data, isLoading, error } = useQuery({ queryKey: ["attempt", id], queryFn: () => api(`/candidate/assessment/attempts/${id}`), refetchOnWindowFocus: false, staleTime: Infinity });
  const [item, setItem] = useState<any>(null);
  const [answer, setAnswer] = useState<any>(null);
  const [left, setLeft] = useState(0);
  const [sending, setSending] = useState(false);
  const [confirmFinish, setConfirmFinish] = useState(false);
  const events = useRef({ blur: 0, paste: 0 });
  const started = useRef(Date.now());

  useEffect(() => {
    if (!data) return;
    if (data.finished) nav(`/c/assessment/result/${id}`, { replace: true });
    else setItem(data.item);
  }, [data, id, nav]);

  useEffect(() => {
    if (!item) return;
    setAnswer(item.kind === "multi" ? [] : null);
    setLeft(item.time_left_s);
    events.current = { blur: 0, paste: 0 };
    started.current = Date.now();
  }, [item?.item_id]); // eslint-disable-line

  const submit = useCallback(async (auto = false) => {
    if (!item || sending) return;
    setSending(true);
    try {
      const r: any = await api(`/candidate/assessment/attempts/${id}/answer`, {
        body: { item_id: item.item_id, response: answer, time_ms: Date.now() - started.current, events: events.current },
      });
      if (auto) toast.message("Время на задание истекло — ответ отправлен");
      if (r.finished) {
        qc.invalidateQueries();
        nav(`/c/assessment/result/${id}`, { replace: true });
      } else setItem(r.item);
    } catch (e) {
      const err = e as ApiError;
      toast.error(err.message);
      if (err.code === "stale_item" || err.code === "attempt_closed") qc.invalidateQueries({ queryKey: ["attempt", id] });
    } finally {
      setSending(false);
    }
  }, [item, answer, id, sending, nav, qc]);

  // таймер задания
  useEffect(() => {
    if (!item) return;
    const t = setInterval(() => setLeft((x) => x - 1), 1000);
    return () => clearInterval(t);
  }, [item?.item_id]); // eslint-disable-line
  useEffect(() => { if (item && left <= 0 && !sending) submit(true); }, [left]); // eslint-disable-line

  // контроль честности: уходы со вкладки и вставки
  useEffect(() => {
    const vis = () => { if (document.hidden) events.current.blur += 1; };
    const paste = () => { events.current.paste += 1; };
    const unload = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    document.addEventListener("visibilitychange", vis);
    document.addEventListener("paste", paste);
    window.addEventListener("beforeunload", unload);
    return () => { document.removeEventListener("visibilitychange", vis); document.removeEventListener("paste", paste); window.removeEventListener("beforeunload", unload); };
  }, []);

  // режим эксперта (демо-аккаунты жюри): ответ без решения задачи или автопрохождение профилем уровня θ
  const [theta, setTheta] = useState("0.5");
  const expert = async (path: string, body: any) => {
    if (sending) return;
    setSending(true);
    try {
      const r: any = await api(`/candidate/assessment/attempts/${id}/expert/${path}`, { body });
      if (r.finished) { qc.invalidateQueries(); nav(`/c/assessment/result/${id}`, { replace: true }); } else setItem(r.item);
    } catch (e) { toast.error((e as ApiError).message); } finally { setSending(false); }
  };

  const finish = async () => {
    await api(`/candidate/assessment/attempts/${id}/finish`, { method: "POST" });
    qc.invalidateQueries();
    nav(`/c/assessment/result/${id}`, { replace: true });
  };

  if (error) return <Alert tone="danger">{(error as ApiError).message}</Alert>;
  if (isLoading || !item) return <PageLoader />;
  const hasAnswer = item.kind === "multi" ? answer?.length > 0 : answer !== null && answer !== "";
  // длина адаптивная: обычно ~15 заданий, пограничным кандидатам — до max_items; полоса не «упирается» раньше времени
  const progress = Math.min(0.95, item.position / Math.max(item.position + 2, 15));
  const urgent = left <= 20;
  return (
    <div className="mx-auto max-w-3xl">
      <div className="sticky top-16 z-20 -mx-4 mb-5 border-b border-line bg-surface/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="kicker">Задание {item.position} · адаптивный тест: завершится, когда грейд определён надёжно (до {item.max_items})</div>
            <div className="mt-0.5 truncate text-[14px] font-semibold">{item.competency}</div>
          </div>
          <div className={clsx("flex items-center gap-2 rounded-xl px-3 py-1.5 font-mono text-[15px] font-bold num", urgent ? "bg-accent-50 text-accent-600" : "bg-white text-ink")}>
            <Clock className="h-4 w-4" />{Math.max(0, Math.floor(left / 60))}:{String(Math.max(0, left % 60)).padStart(2, "0")}
          </div>
        </div>
        <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-line"><div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${progress * 100}%` }} /></div>
      </div>

      {me?.expert_mode && (
        <Card className="mb-4 border-warn-500/40 bg-warn-50/40 p-4">
          <div className="flex items-center gap-2 text-[13.5px] font-semibold"><FlaskConical className="h-4 w-4 text-warn-600" />Режим эксперта (демо-аккаунт жюри)</div>
          <p className="mt-1 text-[12.5px] text-ink-3">Для проверки воспроизводимости и разделяющей силы: ответьте на задание без решения или пройдите оставшиеся задания как синтетический кандидат уровня θ (ответы по модели IRT, ключи остаются на сервере). Такие ответы не участвуют в калибровке банка.</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button size="sm" variant="outline" disabled={sending} onClick={() => expert("answer", { item_id: item.item_id, correct: true })}>Ответить верно</Button>
            <Button size="sm" variant="outline" disabled={sending} onClick={() => expert("answer", { item_id: item.item_id, correct: false })}>Ответить неверно</Button>
            <span className="mx-1 h-5 w-px bg-line" />
            <select aria-label="Уровень профиля" value={theta} onChange={(e) => setTheta(e.target.value)} className="rounded-lg border border-line bg-white px-2 py-1.5 text-[13px]">
              {[["-1.5", "Стажёр (θ −1.5)"], ["-0.5", "Junior (θ −0.5)"], ["0.5", "Middle (θ 0.5)"], ["1.5", "Senior (θ 1.5)"], ["-1", "на пороге Junior (θ −1.0)"], ["0", "на пороге Middle (θ 0.0)"], ["1", "на пороге Senior (θ 1.0)"]].map(([v, n]) => <option key={v} value={v}>{n}</option>)}
            </select>
            <Button size="sm" loading={sending} onClick={() => expert("simulate", { theta: Number(theta) })}>Пройти как этот профиль</Button>
          </div>
        </Card>
      )}
      <Card className="animate-fade-in p-5 sm:p-7" key={item.item_id}>
        <RichText text={item.text} />
        {item.code && (
          <div className="mt-4">
            {LANG_LABEL[item.code_lang] && <div className="mb-1 font-mono text-[11px] uppercase tracking-wider text-ink-3">{LANG_LABEL[item.code_lang]}</div>}
            <pre className="code-block" onCopy={(e) => e.preventDefault()}>{item.code}</pre>
          </div>
        )}
        {item.tables?.length > 0 && (
          <div className="mt-4 grid gap-3 md:grid-cols-2">{item.tables.map((t: any) => <DataTable key={t.name} name={t.name} columns={t.columns} rows={t.rows} />)}</div>
        )}
        <div className="mt-6">
          {item.kind === "single" && (
            <div className="space-y-2">
              {item.options.map((o: string, i: number) => (
                <button key={i} onClick={() => setAnswer(i)}
                  className={clsx("flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left text-[14.5px] transition",
                    answer === i ? "border-brand-500 bg-brand-50" : "border-line hover:border-brand-200")}>
                  <span className={clsx("mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border-2", answer === i ? "border-brand-500" : "border-ink-4")}>
                    {answer === i && <span className="h-2.5 w-2.5 rounded-full bg-brand-500" />}
                  </span>
                  <span className="whitespace-pre-wrap font-[450]">{o}</span>
                </button>
              ))}
            </div>
          )}
          {item.kind === "multi" && (
            <div className="space-y-2">
              {item.hint && <div className="mb-1 text-[13px] text-ink-3">{item.hint}</div>}
              {item.options.map((o: string, i: number) => {
                const on = answer?.includes(i);
                return (
                  <button key={i} onClick={() => setAnswer(on ? answer.filter((x: number) => x !== i) : [...(answer || []), i])}
                    className={clsx("flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left text-[14.5px] transition", on ? "border-brand-500 bg-brand-50" : "border-line hover:border-brand-200")}>
                    <span className={clsx("mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md border-2 text-[12px] text-white", on ? "border-brand-500 bg-brand-500" : "border-ink-4")}>{on && "✓"}</span>
                    <span>{o}</span>
                  </button>
                );
              })}
            </div>
          )}
          {item.kind === "input" && (
            <div className="max-w-md">
              <Input autoFocus value={answer ?? ""} onChange={(e) => setAnswer(e.target.value)} inputMode={item.input?.type === "number" ? "decimal" : "text"}
                placeholder={item.input?.type === "number" ? "Введите число" : "Введите ответ"} className="font-mono text-[17px]"
                onKeyDown={(e) => { if (e.key === "Enter" && hasAnswer) submit(); }} />
              <p className="hint">{item.input?.type === "number" ? "Дробную часть отделяйте точкой или запятой" : "Регистр и лишние пробелы не важны"}</p>
            </div>
          )}
        </div>
        <div className="mt-7 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
          <button onClick={() => setConfirmFinish(true)} className="inline-flex items-center gap-1.5 text-[13px] text-ink-3 hover:text-accent-600"><Flag className="h-4 w-4" />Завершить досрочно</button>
          <div className="flex items-center gap-3">
            {!hasAnswer && <span className="text-[12.5px] text-ink-4">Без ответа задание засчитается как неверное</span>}
            <Button size="lg" onClick={() => submit()} loading={sending}>{hasAnswer ? "Ответить" : "Пропустить"}</Button>
          </div>
        </div>
      </Card>
      <p className="mt-4 flex items-center gap-2 text-[12.5px] text-ink-3"><AlertTriangle className="h-4 w-4" />Задания уникальны для вашей попытки. Вернуться к предыдущему заданию нельзя — так работает адаптивный тест.</p>
      <Modal open={confirmFinish} onClose={() => setConfirmFinish(false)} title="Завершить тест досрочно?"
        footer={<><Button variant="ghost" onClick={() => setConfirmFinish(false)}>Продолжить тест</Button><Button variant="danger" onClick={finish}>Завершить</Button></>}>
        <p className="text-[14px] text-ink-2">Результат будет рассчитан по уже данным ответам. Оставшиеся задания не засчитываются, точность оценки снизится.</p>
      </Modal>
      {sending && <div className="fixed bottom-6 right-6 flex items-center gap-2 rounded-xl bg-night px-4 py-2 text-[13px] text-white shadow-xl"><Loader2 className="h-4 w-4 animate-spin" />Подбираем следующее задание…</div>}
    </div>
  );
}
