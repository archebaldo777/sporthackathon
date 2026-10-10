/** HTTP-клиент API: JWT в заголовке, автоматическое обновление access-токена по refresh-токену, единый формат ошибок. */
export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
  }
}

const store = {
  get(k: string) {
    try { return localStorage.getItem(k); } catch { return null; }
  },
  set(k: string, v: string | null) {
    try { v === null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* приватный режим */ }
  },
};

export const tokens = {
  get access() { return store.get("draft.access"); },
  get refresh() { return store.get("draft.refresh"); },
  set(access: string | null, refresh: string | null) {
    store.set("draft.access", access);
    store.set("draft.refresh", refresh);
  },
  clear() { this.set(null, null); },
};

type Opts = { method?: string; body?: unknown; query?: Record<string, unknown>; form?: FormData; raw?: boolean; auth?: boolean };

let refreshing: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  const rt = tokens.refresh;
  if (!rt) return false;
  try {
    const r = await fetch(`${API_BASE}/auth/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: rt }) });
    if (!r.ok) return false;
    const d = await r.json();
    tokens.set(d.access_token, d.refresh_token);
    return true;
  } catch {
    return false;
  }
}

function qs(query?: Record<string, unknown>) {
  if (!query) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, String(x)));
    else p.append(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export async function api<T = any>(path: string, opts: Opts = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.auth !== false && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let r: Response;
  try {
    r = await fetch(`${API_BASE}${path}${qs(opts.query)}`, { method: opts.method || (body ? "POST" : "GET"), headers, body });
  } catch {
    throw new ApiError(0, "network", "Нет соединения с сервером");
  }
  if (r.status === 401 && !retried && tokens.refresh && !path.startsWith("/auth/")) {
    refreshing = refreshing || doRefresh().finally(() => setTimeout(() => (refreshing = null), 0));
    if (await refreshing) return api<T>(path, opts, true);
    tokens.clear();
    window.dispatchEvent(new Event("draft:logout"));
  }
  if (!r.ok) {
    let code = "http_error", message = `Ошибка ${r.status}`, details;
    try {
      const d = await r.json();
      code = d.error?.code ?? code;
      message = d.error?.message ?? message;
      details = d.error?.details;
    } catch { /* не JSON */ }
    throw new ApiError(r.status, code, message, details);
  }
  if (opts.raw) return r as unknown as T;
  if (r.status === 204) return undefined as T;
  return r.json();
}

export async function download(path: string, filename: string) {
  const r = await api<Response>(path, { raw: true });
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
