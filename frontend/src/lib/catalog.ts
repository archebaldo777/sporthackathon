import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export type Catalog = {
  version: string;
  directions: { code: string; name: string }[];
  specializations: { code: string; name: string; short: string; direction: string; langs: string[]; frameworks: string[]; blueprint: Record<string, number>; core_skills: string[] }[];
  grades: { code: string; name: string; order: number; years: string }[];
  langs: { code: string; name: string }[];
  competencies: { code: string; name: string }[];
  skills: { name: string; group: string }[];
  fsp_disciplines: { code: string; name: string }[];
  fsp_levels: { code: string; name: string }[];
  work_formats: { code: string; name: string }[];
  domains: { code: string; name: string }[];
  team_roles: { code: string; name: string }[];
  soft_skills: string[];
  search_statuses: { code: string; name: string }[];
  decline_reasons: { code: string; name: string }[];
  market_salary: Record<string, Record<string, number>>;
  cities: string[];
};

export function useCatalog() {
  return useQuery({ queryKey: ["catalog"], queryFn: () => api<Catalog>("/catalog", { auth: false }), staleTime: Infinity });
}

export function specName(c: Catalog | undefined, code?: string | null) {
  return c?.specializations.find((s) => s.code === code)?.name ?? code ?? "—";
}
export function specShort(c: Catalog | undefined, code?: string | null) {
  return c?.specializations.find((s) => s.code === code)?.short ?? code ?? "—";
}
export function domainName(c: Catalog | undefined, code: string) {
  return c?.domains.find((d) => d.code === code)?.name ?? code;
}
export function langName(c: Catalog | undefined, code?: string | null) {
  return c?.langs.find((l) => l.code === code)?.name ?? code ?? "—";
}
