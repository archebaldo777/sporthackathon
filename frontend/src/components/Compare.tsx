import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, Scale } from "lucide-react";
import { Badge, Meter, Modal, PageLoader, ScoreRing } from "@/components/ui";
import { api } from "@/lib/api";
import { salaryRange } from "@/lib/format";

const EVIDENCE: Record<string, [string, string]> = {
  test: ["тест", "bg-brand-500 text-white"], fsp: ["ФСП", "bg-gradient-to-r from-brand-500 to-accent-500 text-white"], task: ["задача", "bg-ok-500 text-white"],
  declared: ["резюме", "bg-surface text-ink-2"], related: ["смежный", "bg-surface text-ink-3"], none: ["нет", "bg-accent-50 text-accent-600"],
};

/** Сравнение 2–3 кандидатов по одной потребности: те же компоненты формулы подбора и «почему A выше B». */
export function CompareModal({ needId, ids, onClose }: { needId: number; ids: number[] | null; onClose: () => void }) {
  const open = !!ids && ids.length >= 2;
  const { data, isLoading } = useQuery({
    queryKey: ["compare", needId, ids], enabled: open,
    queryFn: () => api(`/employer/needs/${needId}/compare`, { query: { ids: ids ?? [] } }),
  });
  return (
    <Modal open={open} onClose={onClose} wide title={<span className="inline-flex items-center gap-2"><Scale className="h-5 w-5 text-brand-500" />Сравнение кандидатов</span>}>
      {isLoading || !data ? <PageLoader /> : (
        <div className="space-y-6">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-[13px]">
              <thead>
                <tr>
                  <th className="w-40" />
                  {data.items.map((c: any, i: number) => (
                    <th key={c.id} className="px-2 pb-3 text-left align-bottom font-normal">
                      <div className="flex items-center gap-3">
                        <ScoreRing value={c.match.score} size={48} />
                        <div className="min-w-0">
                          <div className="kicker">{i + 1}-е место</div>
                          <div className="truncate text-[14px] font-semibold">{c.name}</div>
                          <div className="truncate text-[12px] text-ink-3">{c.category}</div>
                        </div>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items[0].match.components.map((comp: any) => (
                  <tr key={comp.key} className="border-t border-line">
                    <td className="py-2 pr-2 text-ink-2">{comp.name}<div className="text-[11px] text-ink-4">вес {Math.round(comp.weight * 100)}%</div></td>
                    {data.items.map((c: any) => {
                      const x = c.match.components.find((y: any) => y.key === comp.key);
                      const best = Math.max(...data.items.map((cc: any) => cc.match.components.find((y: any) => y.key === comp.key).contribution));
                      return (
                        <td key={c.id} className="px-2 py-2">
                          <div className="flex items-center gap-2"><Meter value={x.value} /><span className={clsx("num w-10 text-right", x.contribution === best ? "font-semibold text-brand-700" : "text-ink-3")}>+{x.contribution}</span></div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
                <tr className="border-t border-line">
                  <td className="py-2 pr-2 text-ink-2">Навыки из запроса</td>
                  {data.items.map((c: any) => (
                    <td key={c.id} className="px-2 py-2">
                      <div className="flex flex-wrap gap-1">
                        {data.skills.map((s: string) => {
                          const ev = c.match.skills?.[s]?.evidence ?? "none";
                          return <span key={s} className={clsx("rounded-md px-1.5 py-0.5 text-[11px] font-medium", EVIDENCE[ev]?.[1])} title={EVIDENCE[ev]?.[0]}>{s}{data.need.must_skills.includes(s) ? "*" : ""}</span>;
                        })}
                      </div>
                    </td>
                  ))}
                </tr>
                <tr className="border-t border-line">
                  <td className="py-2 pr-2 text-ink-2">Ожидания</td>
                  {data.items.map((c: any) => (
                    <td key={c.id} className={clsx("px-2 py-2", c.salary_from && c.salary_from > data.need.salary_to && "text-accent-600")}>{salaryRange(c.salary_from, c.salary_to)}</td>
                  ))}
                </tr>
                <tr className="border-t border-line">
                  <td className="py-2 pr-2 text-ink-2">ФСП</td>
                  {data.items.map((c: any) => <td key={c.id} className="px-2 py-2">{c.fsp?.count ? `${c.fsp.count} результат(ов)` : "нет истории — без штрафа"}</td>)}
                </tr>
                <tr className="border-t border-line">
                  <td className="py-2 pr-2 text-ink-2">Вероятность принятия</td>
                  {data.items.map((c: any) => <td key={c.id} className="px-2 py-2">{Math.round((c.match.acceptance?.p ?? 0) * 100)}% · {c.match.acceptance?.label}</td>)}
                </tr>
              </tbody>
            </table>
            <p className="mt-2 text-[11.5px] text-ink-3">Вклад — баллы компоненты в итоговой оценке (вес × значение). Навыки: синие — подтверждены тестом, градиент — ФСП, зелёные — задачей; * — обязательные. Суммы ожиданий — gross.</p>
          </div>
          {data.pairs.map((p: any) => (
            <div key={`${p.a}-${p.b}`} className="rounded-2xl border border-line p-4">
              <div className="text-[14px] font-semibold">Почему «{p.a_name}» выше «{p.b_name}»: <span className="num text-brand-700">+{p.score_gap}</span> балла</div>
              <div className="mt-3 grid gap-4 md:grid-cols-2">
                <div>
                  <div className="kicker mb-1.5 flex items-center gap-1 text-ok-700"><ArrowUpRight className="h-3.5 w-3.5" />Сильнее у {p.a_name}</div>
                  {p.a_better.length ? p.a_better.map((x: any) => <div key={x.key} className="flex justify-between text-[13px]"><span>{x.name}</span><span className="num">+{x.points}</span></div>) : <div className="text-[13px] text-ink-3">—</div>}
                  {p.b_modifiers.length > 0 && <div className="mt-2 text-[12.5px] text-ink-3">У второго: {p.b_modifiers.join("; ")}</div>}
                </div>
                <div>
                  <div className="kicker mb-1.5 flex items-center gap-1 text-accent-600"><ArrowDownRight className="h-3.5 w-3.5" />Сильнее у {p.b_name}</div>
                  {p.b_better.length ? p.b_better.map((x: any) => <div key={x.key} className="flex justify-between text-[13px]"><span>{x.name}</span><span className="num">+{x.points}</span></div>) : <div className="text-[13px] text-ink-3">—</div>}
                  {p.a_modifiers.length > 0 && <div className="mt-2 text-[12.5px] text-ink-3">У первого: {p.a_modifiers.join("; ")}</div>}
                </div>
              </div>
            </div>
          ))}
          <div className="flex flex-wrap gap-2 text-[12px] text-ink-3"><Badge>одна формула для всех</Badge>подборка ранжируется по тем же компонентам; сравнение пересчитано на текущих данных профилей</div>
        </div>
      )}
    </Modal>
  );
}
