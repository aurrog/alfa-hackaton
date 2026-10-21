import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { Application, CompanyDetails, Product } from '../../api/types';

const LIVE = new Set(['submitted', 'data_check', 'enrichment', 'scoring', 'disbursement']);
const BANK = new Set(['manual_review', 'committee_review']);

/** Заявка с «живым» обновлением: пока работает конвейер — опрос раз в секунду, пока у банка — раз в 4 секунды. */
export function useApplication(id: string | undefined) {
  return useQuery({
    queryKey: ['application', id],
    queryFn: () => api.get<Application>(`/api/v1/applications/${id}`),
    enabled: !!id,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      if (!s) return false;
      if (LIVE.has(s)) return 1000;
      if (BANK.has(s)) return 4000;
      return 15000;
    },
  });
}

export function useSetApplication() {
  const qc = useQueryClient();
  return (app: Application) => {
    qc.setQueryData(['application', app.id], app);
    void qc.invalidateQueries({ queryKey: ['applications'] });
    void qc.invalidateQueries({ queryKey: ['notifications'] });
  };
}

export function useCompany(id: string | undefined) {
  return useQuery({
    queryKey: ['company', id],
    queryFn: () => api.get<CompanyDetails>(`/api/v1/companies/${id}`),
    enabled: !!id,
  });
}

export function useProducts(companyId: string | undefined) {
  return useQuery({
    queryKey: ['products', companyId],
    queryFn: () => api.get<{ items: Product[]; key_rate: number; purposes: { code: string; title: string; hint: string }[] }>('/api/v1/products', { company_id: companyId }),
    enabled: !!companyId,
  });
}
