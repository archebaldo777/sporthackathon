import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { StatusBadge } from "@/components/domain";
import { PageHeader } from "@/components/layout/Layouts";
import { Button, Card, EmptyState, PageLoader } from "@/components/ui";
import { api } from "@/lib/api";
import { dateShort, salaryRange } from "@/lib/format";

export default function Applications() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["cand-applications"], queryFn: () => api("/candidate/applications") });
  const withdraw = useMutation({ mutationFn: (id: number) => api(`/candidate/applications/${id}`, { method: "DELETE" }), onSuccess: () => { toast.success("Отклик отозван"); qc.invalidateQueries(); } });
  if (isLoading) return <PageLoader />;
  const items = data?.items ?? [];
  return (
    <div>
      <PageHeader title="Мои отклики" subtitle="Статусы ваших самостоятельных откликов на вакансии" action={<Link to="/c/jobs"><Button>Найти вакансии</Button></Link>} />
      {items.length === 0 ? <Card><EmptyState icon={<Send />} title="Вы ещё не откликались" text="Основной сценарий — приглашения от компаний, но откликнуться самостоятельно тоже можно." action={<Link to="/c/jobs"><Button>К вакансиям</Button></Link>} /></Card> : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-[14px]">
            <thead><tr className="border-b border-line text-left text-[12.5px] text-ink-3"><th className="px-5 py-3 font-medium">Вакансия</th><th className="font-medium">Зарплата</th><th className="font-medium">Соответствие</th><th className="font-medium">Статус</th><th className="font-medium">Дата</th><th /></tr></thead>
            <tbody>
              {items.map((a: any) => (
                <tr key={a.id} className="border-b border-line last:border-0">
                  <td className="px-5 py-3.5"><Link to={`/c/jobs/${a.vacancy.id}`} className="font-medium hover:text-brand-600">{a.vacancy.title}</Link><div className="text-[12.5px] text-ink-3">{a.vacancy.company}</div>{a.employer_comment && <div className="mt-1 text-[12.5px] text-ink-2">«{a.employer_comment}»</div>}</td>
                  <td className="num">{salaryRange(a.vacancy.salary_from, a.vacancy.salary_to)}</td>
                  <td className="num">{a.match_score != null ? Math.round(a.match_score) : "—"}</td>
                  <td><StatusBadge status={a.status} name={a.status_name} /></td>
                  <td className="text-ink-3">{dateShort(a.created_at)}</td>
                  <td className="pr-5 text-right">{["sent", "viewed"].includes(a.status) && <Button size="sm" variant="ghost" onClick={() => withdraw.mutate(a.id)}>Отозвать</Button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
