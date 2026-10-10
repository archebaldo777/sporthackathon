import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, ShieldX, Trophy } from "lucide-react";
import { useParams } from "react-router-dom";
import { CategoryBadge } from "@/components/domain";
import { Alert, Badge, Card, Logo, PageLoader } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { date } from "@/lib/format";

export default function Verify() {
  const { token } = useParams();
  const { data, isLoading, error } = useQuery({ queryKey: ["verify", token], queryFn: () => api(`/public/verify/${token}`, { auth: false }), retry: false });
  return (
    <div className="grid min-h-[70vh] place-items-center px-4 py-12">
      <Card className="w-full max-w-lg p-7">
        <Logo />
        {isLoading ? <PageLoader /> : error ? (
          <div className="mt-6"><Alert tone="danger" icon={<ShieldX className="h-5 w-5" />} title="Профиль не подтверждён">{(error as ApiError).message}</Alert></div>
        ) : (
          <div className="mt-6 space-y-4">
            <div className="flex items-center gap-2 text-[18px] font-bold text-ok-700"><BadgeCheck className="h-6 w-6" />PDF-профиль подлинный</div>
            <p className="text-[14px] text-ink-3">Документ выпущен платформой {date(data.issued_at)}. Ниже — актуальные данные профиля на сегодня.</p>
            <div className="rounded-xl bg-surface p-4">
              <div className="text-[16px] font-semibold">{data.name} <span className="font-mono text-[13px] text-ink-3">{data.code}</span></div>
              <div className="mt-2"><CategoryBadge label={data.category} large /></div>
              <div className="mt-2 text-[13px] text-ink-3">Грейд подтверждён тестом {date(data.grade_confirmed_at)}</div>
            </div>
            <div className="flex flex-wrap gap-1.5">{data.verified_skills.map((s: string) => <Badge key={s} tone="brand">✓ {s}</Badge>)}</div>
            <div className="text-[13.5px]">{data.fsp_linked ? <span className="inline-flex items-center gap-1.5"><Trophy className="h-4 w-4 text-accent-500" />Связан с ФСП ID · подтверждённых результатов: {data.fsp_achievements}</span> : "ФСП ID не связан"}</div>
          </div>
        )}
      </Card>
    </div>
  );
}
