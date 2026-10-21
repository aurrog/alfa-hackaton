import { useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, getToken, setToken, setUnauthorizedHandler } from '../api/client';
import type { Company, User } from '../api/types';

interface AuthState {
  user: User | null;
  companies: Company[];
  company: Company | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  refresh: () => Promise<void>;
  selectCompany: (id: string) => void;
}

const Ctx = createContext<AuthState | null>(null);
const COMPANY_KEY = 'scc.company';

function readCompany(): string | null {
  try {
    return localStorage.getItem(COMPANY_KEY);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState<string | null>(readCompany());
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setReady(true);
      return;
    }
    try {
      const me = await api.get<{ user: User; companies: Company[] }>('/api/v1/auth/me');
      setUser(me.user);
      setCompanies(me.companies);
    } catch {
      setUser(null);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      qc.clear();
    });
    void refresh();
  }, [refresh, qc]);

  const login = useCallback(
    async (email: string, password: string) => {
      const r = await api.post<{ access_token: string; user: User }>('/api/v1/auth/login', { email, password });
      setToken(r.access_token);
      qc.clear();
      await refresh();
      return r.user;
    },
    [qc, refresh],
  );

  const logout = useCallback(() => {
    void api.post('/api/v1/auth/logout').catch(() => undefined);
    setToken(null);
    setUser(null);
    setCompanies([]);
    qc.clear();
  }, [qc]);

  const selectCompany = useCallback((id: string) => {
    setCompanyId(id);
    try {
      localStorage.setItem(COMPANY_KEY, id);
    } catch {
      /* без сохранения */
    }
  }, []);

  const company = useMemo(() => companies.find((c) => c.id === companyId) ?? companies[0] ?? null, [companies, companyId]);

  return (
    <Ctx.Provider value={{ user, companies, company, ready, login, logout, refresh, selectCompany }}>{children}</Ctx.Provider>
  );
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error('AuthProvider missing');
  return v;
}
