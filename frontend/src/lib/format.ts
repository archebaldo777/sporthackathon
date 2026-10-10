export const rub = (n?: number | null) => (n == null ? "—" : `${Math.round(n / 1000).toLocaleString("ru-RU")} тыс. ₽`);

// Все суммы на платформе — в месяц, до вычета НДФЛ (gross). Подпись обязательна: так решили постановщики на Q&A-сессии.
export const GROSS = "gross";
export const GROSS_HINT = "в месяц, до вычета НДФЛ (gross)";
export const salaryRange = (from?: number | null, to?: number | null) => {
  if (from == null && to == null) return "не указана";
  if (from != null && to != null) return `${Math.round(from / 1000)}–${Math.round(to / 1000)} тыс. ₽ ${GROSS}`;
  return from != null ? `от ${rub(from)} ${GROSS}` : `до ${rub(to)} ${GROSS}`;
};

export const date = (s?: string | null) => (s ? new Date(s).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" }) : "—");
export const dateShort = (s?: string | null) => (s ? new Date(s).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit" }) : "—");
export const dateTime = (s?: string | null) =>
  s ? new Date(s).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

export function ago(s?: string | null) {
  if (!s) return "—";
  const diff = (Date.now() - new Date(s).getTime()) / 1000;
  if (diff < 60) return "только что";
  if (diff < 3600) return `${Math.floor(diff / 60)} мин назад`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} ч назад`;
  const d = Math.floor(diff / 86400);
  if (d < 30) return `${d} ${plural(d, "день", "дня", "дней")} назад`;
  return dateShort(s);
}

export function plural(n: number, one: string, few: string, many: string) {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
}

export const pct = (v?: number | null, digits = 0) => (v == null ? "—" : `${(v * 100).toFixed(digits)}%`);

export const GRADE_NAMES: Record<string, string> = { intern: "Стажёр", junior: "Junior", middle: "Middle", senior: "Senior" };
export const GRADE_ORDER = ["intern", "junior", "middle", "senior"];
export const FORMAT_NAMES: Record<string, string> = { office: "Офис", hybrid: "Гибрид", remote: "Удалённо" };
export const STATUS_TONE: Record<string, "brand" | "ok" | "warn" | "danger" | "neutral"> = {
  sent: "brand", viewed: "warn", accepted: "ok", declined: "danger", expired: "neutral", withdrawn: "neutral",
  interview: "brand", offer: "ok", rejected: "danger", submitted: "warn", reviewed: "ok", assigned: "brand", skipped: "neutral",
};

/** Цветовой код дисциплин ФСП (брендбук): фиолетовый — продуктовое, синий — алгоритмическое, бирюзовый — БАС,
 *  жёлтый — робототехника, зелёный — информационная безопасность. */
export const DISCIPLINE_COLORS: Record<string, string> = {
  product: "#8F1BF4", algorithmic: "#402FFD", uav: "#1ED3CA", robotics: "#ECB617", security: "#09A953",
};
/** На светлых дисциплинарных цветах (бирюзовый, жёлтый) значок — тёмный, на остальных — белый. */
export const DISCIPLINE_ON_DARK_ICON: Record<string, boolean> = { uav: true, robotics: true };
