import { useMutation } from "@tanstack/react-query";
import { ChevronDown, Download, FileJson, Play, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Alert, Button, Card, CardHeader, Tabs } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

type Proto = "pool" | "pairs";
const METHOD: Record<string, string> = { ours: "Драфт", keyword_baseline: "Поиск по резюме (классика)", ideal: "Потолок при этой разметке" };
const GN: Record<string, string> = { intern: "Стажёр", junior: "Junior", middle: "Middle", senior: "Senior" };
const f2 = (v?: number) => (v == null ? "—" : v.toFixed(2));

function save(data: unknown, name: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 1)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/** Проверка механики подбора на своём размеченном наборе пар «вакансия — кандидат» (например, наборе жюри). */
export default function ExternalEval() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [proto, setProto] = useState<Proto>("pool");
  const [source, setSource] = useState<string>("");
  const [parseError, setParseError] = useState<string>("");
  const [open, setOpen] = useState(false);
  const run = useMutation({ mutationFn: (data: unknown) => api("/validation/external-eval", { body: data, auth: false }) });
  const example = useMutation({ mutationFn: () => api("/validation/external-eval/example", { auth: false }) });

  const runExample = async () => {
    setParseError("");
    const d = example.data ?? (await example.mutateAsync());
    setSource("пример: синтетическая популяция, разметка по скрытой истине");
    run.mutate(d);
  };
  const onFile = async (f?: File) => {
    if (!f) return;
    setParseError("");
    try {
      const d = JSON.parse(await f.text());
      setSource(f.name);
      run.mutate(d);
    } catch {
      setParseError("Файл не является корректным JSON");
    }
    if (fileRef.current) fileRef.current.value = "";
  };

  const r: any = run.data;
  const rows = r ? Object.entries(r.summary[proto]).map(([k, v]: any) => ({ key: k, name: METHOD[k] ?? k, ...v })) : [];
  return (
    <Card>
      <CardHeader icon={<FileJson className="h-5 w-5" />} title="Проверьте подбор на своём наборе пар «вакансия — кандидат»"
        subtitle="Загрузите размеченный набор — вакансии текстом, кандидатов текстом резюме или полями, оценки релевантности пар 0–3 или 0/1. Система разберёт тексты, построит подборку и посчитает долю релевантных в топе в сравнении с классическим поиском по резюме. Данные никуда не сохраняются." />
      <div className="space-y-4 px-5 pb-5">
        <div className="flex flex-wrap gap-2">
          <input ref={fileRef} type="file" accept="application/json,.json" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} />
          <Button icon={<Upload className="h-4 w-4" />} onClick={() => fileRef.current?.click()} loading={run.isPending && !source.startsWith("пример")}>Загрузить JSON</Button>
          <Button variant="secondary" icon={<Play className="h-4 w-4" />} onClick={runExample} loading={example.isPending || (run.isPending && source.startsWith("пример"))}>Прогнать пример</Button>
          <Button variant="outline" icon={<Download className="h-4 w-4" />}
            onClick={async () => save(example.data ?? (await example.mutateAsync()), "eval_pairs_example.json")}>Скачать пример</Button>
        </div>
        <details className="rounded-xl bg-surface px-4 py-3 text-[12.5px] text-ink-2">
          <summary className="cursor-pointer font-medium text-ink">Формат файла</summary>
          <pre className="code-block mt-3 overflow-x-auto text-[11.5px]">{`{
  "vacancies":  [{"id": "v1", "text": "Python-разработчик Middle. Обязательно: Python, PostgreSQL… 200–280 тыс. ₽, удалённо"}],
  "candidates": [{"id": "c1", "resume_text": "…",              // или поля: specialization, grade, skills,
                  "salary_from": 230000, "work_formats": ["remote"],     // salary_from/to, city, search_status
                  "test": {"grade": "middle", "theta": 0.6, "verified_skills": ["Python"]},   // если проходил тест
                  "fsp": [{"discipline": "product", "level": "national", "place": 2, "date": "2025-11-20"}]}],
  "labels":     [{"vacancy": "v1", "candidate": "c1", "relevance": 2}]
}`}</pre>
          <p className="mt-2">Специализация и грейд — коды или обычные названия («Бэкенд», «мидл»). Кандидат без теста ранжируется по заявленной категории, без истории ФСП — без бонуса, но не исключается. Протокол «по всей базе» — система ищет среди всех кандидатов файла (неразмеченные пары считаются нерелевантными); «только пары» — ранжируются только кандидаты, размеченные для вакансии. То же из консоли: <code>python -m app.validation.external_eval data.json</code>.</p>
        </details>
        {parseError && <Alert tone="danger">{parseError}</Alert>}
        {run.error && <Alert tone="danger">{(run.error as ApiError).message}</Alert>}
        {r && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-[13px] text-ink-3">
              <span className="max-w-full truncate rounded-full bg-night px-2.5 py-0.5 text-[12px] font-medium text-white" title={source}>{source}</span>
              <span>{r.vacancies_evaluated} из {r.vacancies} вакансий · {r.candidates} кандидатов · {r.labels} пар · шкала {r.scale === "binary" ? "0/1" : "0–3"}, релевантна оценка ≥ {r.threshold} · с тестом {r.candidates_with_test}, с ФСП {r.candidates_with_fsp}{r.candidates_uncategorized ? ` · без категории ${r.candidates_uncategorized}` : ""}</span>
            </div>
            <Tabs value={proto} onChange={setProto} tabs={[{ id: "pool", label: "По всей базе" }, { id: "pairs", label: "Только размеченные пары" }]} />
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead><tr className="text-left text-ink-3"><th className="py-2 font-medium">Ранжирование</th><th className="font-medium">P@10</th><th className="font-medium">nDCG@10</th><th className="font-medium">MRR</th><th className="font-medium">R@30</th></tr></thead>
                <tbody>{rows.map((x: any) => (
                  <tr key={x.key} className={"border-t border-line " + (x.key === "ours" ? "font-semibold text-brand-700" : x.key === "ideal" ? "text-ink-3" : "")}>
                    <td className="py-2 pr-2">{x.name}</td><td className="num">{f2(x["p@10"])}</td><td className="num">{f2(x["ndcg@10"])}</td><td className="num">{f2(x.mrr)}</td><td className="num">{f2(x["recall@30"])}</td>
                  </tr>))}
                </tbody>
              </table>
            </div>
            <p className="text-[13px] text-ink-2">nDCG@10 лучше классического поиска в <b>{r.ours_beats_keyword.wins}</b> из {r.vacancies_evaluated} вакансий{r.ours_beats_keyword.ties ? `, наравне — ${r.ours_beats_keyword.ties}` : ""}. P@10 — доля релевантных в топ-10; «потолок» показывает максимум, достижимый при числе релевантных кандидатов в разметке.</p>
            <button className="flex items-center gap-1.5 text-[13px] font-medium text-brand-700" onClick={() => setOpen(!open)}>
              <ChevronDown className={"h-4 w-4 transition " + (open ? "rotate-180" : "")} />Разбор по вакансиям
            </button>
            {open && (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-[12.5px]">
                  <thead><tr className="text-left text-ink-3"><th className="py-2 font-medium">Вакансия</th><th className="font-medium">Распознано</th><th className="font-medium">Релевантных</th><th className="font-medium">nDCG Драфт</th><th className="font-medium">nDCG классика</th><th className="font-medium">Топ-3 (оценка в разметке)</th></tr></thead>
                  <tbody>{r.per_vacancy.map((v: any) => (
                    <tr key={v.vacancy} className="border-t border-line align-top">
                      <td className="py-2 pr-2 font-mono">{v.vacancy}</td>
                      <td className="pr-2">{v.parsed.specialization} · {v.parsed.grades.map((g: string) => GN[g] ?? g).join("/")}<div className="text-ink-3">{v.parsed.must_skills.join(", ")}</div></td>
                      <td className="num">{v.relevant}</td>
                      <td className={"num " + (v[proto].ours["ndcg@10"] >= v[proto].keyword_baseline["ndcg@10"] ? "font-semibold text-brand-700" : "")}>{f2(v[proto].ours["ndcg@10"])}</td>
                      <td className="num">{f2(v[proto].keyword_baseline["ndcg@10"])}</td>
                      <td className="font-mono">{v.top.slice(0, 3).map((t: any) => `${t.candidate}(${t.label ?? "–"})`).join(" ")}</td>
                    </tr>))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
