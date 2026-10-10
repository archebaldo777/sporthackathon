import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, CheckCircle2, Info, XCircle } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { TopicBars, TopicRadar } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Alert, Badge, Button, Card, CardHeader, Meter, PageLoader } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { GRADE_NAMES, GRADE_ORDER } from "@/lib/format";

const CUTS: Record<string, number> = { intern: -2, junior: -1, middle: 0, senior: 1 };

export default function AttemptResult() {
  const { id } = useParams();
  const qc = useQueryClient();
  const nav = useNavigate();
  const { data, isLoading } = useQuery({ queryKey: ["attempt", id], queryFn: () => api(`/candidate/assessment/attempts/${id}`) });
  const up = useMutation({
    mutationFn: () => api(`/candidate/assessment/attempts/${id}/upgrade`, { method: "POST" }),
    onSuccess: (r: any) => { qc.invalidateQueries(); nav(`/c/assessment/test/${r.attempt_id}`); },
    onError: (e: ApiError) => toast.error(e.message),
  });
  const confirm = useMutation({
    mutationFn: (grade: string) => api("/candidate/assessment/attempts", { body: { target_grade: grade } }),
    onSuccess: (r: any) => { qc.invalidateQueries(); nav(`/c/assessment/test/${r.attempt_id}`); },
    onError: (e: ApiError) => toast.error(e.message),
  });
  if (isLoading || !data) return <PageLoader />;
  const r = data.result;
  if (!r) return <Alert>Попытка ещё не завершена. <Link className="link" to={`/c/assessment/test/${id}`}>Продолжить</Link></Alert>;
  const traj = (r.trajectory ?? []).map((t: any) => ({ ...t, lo: t.theta - t.se, hi: t.theta + t.se, band: [t.theta - t.se, t.theta + t.se], ok: t.correct ? t.theta : null, bad: !t.correct ? t.theta : null }));
  return (
    <div className="space-y-6">
      <PageHeader back={{ to: "/c/assessment", label: "К тестированию" }} title={`Результат теста на ${GRADE_NAMES[r.target_grade]}`}
        subtitle={`${r.items_count} заданий · итоговая оценка способности θ = ${r.theta?.toFixed(2)} ± ${r.se?.toFixed(2)}`} />
      <Card className={r.passed ? "border-ok-500/30" : "border-accent-100"}>
        <div className="flex flex-col gap-5 p-6 md:flex-row md:items-center">
          <div className={"grid h-16 w-16 shrink-0 place-items-center rounded-2xl " + (r.passed ? "bg-ok-50 text-ok-500" : "bg-accent-50 text-accent-500")}>
            {r.passed ? <CheckCircle2 className="h-9 w-9" /> : <XCircle className="h-9 w-9" />}
          </div>
          <div className="flex-1">
            <h2 className="font-sans text-[22px] font-bold">{r.passed ? `Грейд ${GRADE_NAMES[r.target_grade]} подтверждён` : r.decision === "needs_confirmation" ? `Подтвердите грейд ${GRADE_NAMES[r.target_grade]} контрольной формой` : `Грейд ${GRADE_NAMES[r.target_grade]} пока не подтверждён`}</h2>
            <p className="mt-1 text-[14.5px] text-ink-3">
              {r.passed ? "Вы в категории — работодатели видят ваш профиль и могут пригласить." :
                r.decision === "needs_confirmation" ? "Результат выше порога, но система зафиксировала сигналы, при которых грейд подтверждается короткой формой: 6–10 новых заданий, таймер строже. Доступна сразу и не расходует попытку." :
                "Грейд не понижается принудительно. Тест на уровень ниже доступен сразу, повтор этого уровня — через 14 дней."}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {r.upgrade_grade && <Button loading={up.isPending} onClick={() => up.mutate()} icon={<ArrowUpRight className="h-4 w-4" />}>Тест на {GRADE_NAMES[r.upgrade_grade]} без ожидания</Button>}
            {r.decision === "needs_confirmation" && <Button loading={confirm.isPending} onClick={() => confirm.mutate(r.target_grade)}>Пройти контрольную форму</Button>}
            {!r.passed && r.decision !== "needs_confirmation" && r.suggested_grade && <Link to="/c/assessment"><Button>Пройти тест на {GRADE_NAMES[r.suggested_grade]}</Button></Link>}
            <Link to="/c"><Button variant="outline">В кабинет</Button></Link>
          </div>
        </div>
        {r.upgrade_grade && (
          <div className="border-t border-line px-6 py-4"><Alert tone="ok" icon={<Info className="h-4 w-4" />}>Вы уверенно справились: вероятность уровня {GRADE_NAMES[r.upgrade_grade]} — {Math.round((r.probs?.[r.upgrade_grade] ?? 0) * 100)}%. Грейд не повышается автоматически: можно сразу пройти отдельный тест на {GRADE_NAMES[r.upgrade_grade]} — без ожидания 90 дней и вне лимита попыток. Предложение действует 14 дней.</Alert></div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <Card>
          <CardHeader title="Вероятность каждого грейда" subtitle="Апостериорная вероятность P(θ ≥ порог грейда). Решение: ≥ 50% для заявленного, ≥ 80% — для повышения." />
          <div className="space-y-3 px-5 pb-5">
            {GRADE_ORDER.map((g) => (
              <div key={g} className="grid grid-cols-[80px_1fr_52px] items-center gap-3 text-[13.5px]">
                <span className="font-mono font-semibold">{GRADE_NAMES[g]}</span>
                <Meter value={r.probs?.[g] ?? 0} tone={(r.probs?.[g] ?? 0) >= 0.5 ? "brand" : "warn"} />
                <span className="num text-right">{Math.round((r.probs?.[g] ?? 0) * 100)}%</span>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="Результаты по компетенциям" subtitle="Оценки с байесовским сжатием к общему уровню" />
          <div className="px-3 pb-3">{Object.keys(r.topic_scores || {}).length >= 3 ? <TopicRadar topics={r.topic_scores} height={240} /> : <div className="px-2 pb-3"><TopicBars topics={r.topic_scores} /></div>}</div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Как адаптивный тест уточнял оценку" subtitle="После каждого ответа пересчитывается θ̂ и доверительный интервал; следующее задание выбирается по максимуму информации около текущей оценки." />
        <div className="h-72 px-2 pb-4">
          <ResponsiveContainer>
            <ComposedChart data={traj} margin={{ top: 10, right: 64, left: -10, bottom: 0 }}>
              <CartesianGrid stroke="#EDEDF3" />
              <XAxis dataKey="n" tick={{ fontSize: 12 }} />
              <YAxis domain={[-3, 3]} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v: any) => (Array.isArray(v) ? v.map((x: number) => x.toFixed(2)).join(" … ") : Number(v).toFixed(2))} labelFormatter={(l) => `Задание ${l}`} />
              {Object.entries(CUTS).slice(1).map(([g, c]) => <ReferenceLine key={g} y={c} stroke="#C9C2FF" strokeDasharray="4 4" label={{ value: GRADE_NAMES[g], position: "right", fontSize: 11, fill: "#62636B" }} />)}
              <Area dataKey="band" stroke="none" fill="#402FFF" fillOpacity={0.12} name="θ ± SE" />
              <Line dataKey="theta" stroke="#402FFF" strokeWidth={2.5} dot={false} name="θ̂" />
              <Scatter dataKey="ok" fill="#12A150" name="верно" />
              <Scatter dataKey="bad" fill="#EC1D35" name="неверно" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card>
        <CardHeader title="Задания попытки" subtitle="Ключи ответов не раскрываются — задания генерируются заново для каждого кандидата" />
        <div className="overflow-x-auto px-5 pb-5">
          <table className="w-full text-[13.5px]">
            <thead><tr className="text-left text-ink-3"><th className="py-2 font-medium">№</th><th className="font-medium">Компетенция</th><th className="font-medium">Сложность</th><th className="font-medium">Результат</th><th className="text-right font-medium">Время</th></tr></thead>
            <tbody>
              {r.items.map((it: any) => (
                <tr key={it.position} className="border-t border-line">
                  <td className="py-2 font-mono">{it.position}</td><td>{it.competency}</td>
                  <td><Badge tone="neutral">{["", "стажёр", "junior", "middle", "senior"][it.level] || "—"}</Badge></td>
                  <td>{it.correct ? <Badge tone="ok">верно</Badge> : <Badge tone="danger">неверно</Badge>}</td>
                  <td className="text-right font-mono text-ink-3">{it.time_spent_s} с</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
