import { useQuery } from "@tanstack/react-query";
import { Plus, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/layout/Layouts";
import { Badge, Button, Card, EmptyState, PageLoader } from "@/components/ui";
import { api } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { ago, salaryRange } from "@/lib/format";

export default function Needs() {
  const { data, isLoading } = useQuery({ queryKey: ["emp-needs"], queryFn: () => api("/employer/needs") });
  const { data: cat } = useCatalog();
  if (isLoading) return <PageLoader />;
  const items = data?.items ?? [];
  return (
    <div>
      <PageHeader title="Потребности и подборки" subtitle="Потребность — описание того, кого вы ищете. По ней система формирует подборку из подходящих категорий и ранжирует кандидатов с объяснением. Привязка к вакансии не нужна."
        action={<Link to="/e/needs/new"><Button icon={<Plus className="h-4 w-4" />}>Новая потребность</Button></Link>} />
      {items.length === 0 ? <Card><EmptyState icon={<Sparkles />} title="Потребностей пока нет" text="Опишите задачу команды простым текстом — NLP заполнит стек, грейд и вилку." action={<Link to="/e/needs/new"><Button>Описать потребность</Button></Link>} /></Card> : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((n: any) => (
            <Link key={n.id} to={`/e/needs/${n.id}`} className="card block p-5 transition hover:border-brand-300 hover:shadow-lift">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0"><h3 className="font-sans text-[16px] font-semibold leading-snug">{n.title}</h3><div className="mt-1 text-[13px] text-ink-3">{cat?.specializations.find((s) => s.code === n.specialization)?.name}</div></div>
                <div className="text-right"><div className="font-mono text-[24px] font-bold leading-none">{n.shortlist.total}</div><div className="text-[11.5px] text-ink-3">в подборке</div></div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">{n.categories.map((c: string) => <Badge key={c} tone="dark">{c}</Badge>)}{n.must_skills.map((s: string) => <Badge key={s} tone="brand">{s}</Badge>)}</div>
              <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-3 text-[12.5px] text-ink-3">
                <span className="font-medium text-ink-2">{salaryRange(n.salary_from, n.salary_to)}</span>
                <span>★ {n.shortlist.starred}</span><span>приглашено: {n.invited}</span><span>обновлено {ago(n.last_run_at)}</span>
                {n.market?.status === "low" && <Badge tone="warn">вилка ниже рынка</Badge>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
