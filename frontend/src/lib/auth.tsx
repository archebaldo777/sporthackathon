import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, tokens } from "./api";

export type User = { id: number; email: string; role: "candidate" | "employer" | "admin"; email_verified: boolean; fsp_linked: boolean; display_name?: string | null };
export type TokenOut = { access_token: string; refresh_token: string; expires_in: number; user: User };

type Ctx = {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<User>;
  acceptTokens: (t: TokenOut) => User;
  logout: () => void;
  reload: () => Promise<void>;
};

const AuthCtx = createContext<Ctx>(null as unknown as Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const qc = useQueryClient();

  const reload = useCallback(async () => {
    if (!tokens.access) {
      setUser(null);
      setReady(true);
      return;
    }
    try {
      setUser(await api<User>("/auth/me"));
    } catch {
      tokens.clear();
      setUser(null);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    reload();
    const onLogout = () => { setUser(null); qc.clear(); };
    window.addEventListener("draft:logout", onLogout);
    return () => window.removeEventListener("draft:logout", onLogout);
  }, [reload, qc]);

  const acceptTokens = useCallback((t: TokenOut) => {
    tokens.set(t.access_token, t.refresh_token);
    qc.clear();
    setUser(t.user);
    return t.user;
  }, [qc]);

  const login = useCallback(async (email: string, password: string) => {
    const t = await api<TokenOut>("/auth/login", { body: { email, password }, auth: false });
    return acceptTokens(t);
  }, [acceptTokens]);

  const logout = useCallback(() => {
    const rt = tokens.refresh;
    if (rt) api("/auth/logout", { body: { refresh_token: rt }, auth: false }).catch(() => undefined);
    tokens.clear();
    qc.clear();
    setUser(null);
  }, [qc]);

  const value = useMemo(() => ({ user, ready, login, logout, reload, acceptTokens }), [user, ready, login, logout, reload, acceptTokens]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);

export function homeFor(u: User | null) {
  if (!u) return "/";
  if (!u.email_verified) return "/verify-email";
  return u.role === "candidate" ? "/c" : u.role === "employer" ? "/e" : "/admin";
}
