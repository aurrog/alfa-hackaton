import { Alert, Box, Button, Grid, Group, SimpleGrid, Slider, Stack, Text, Title } from '@mantine/core';
import { IconArrowRight } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { api, errorText } from '../../api/client';
import type { Application, ApplicationSummary, Loan, Preapproved, Stage } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { Feed } from '../../components/Feed';
import { RouteMap } from '../../components/RouteMap';
import { Money, Plate, Section, StatusBadge, Tag } from '../../components/ui';
import { annuity, date, money, months, pct, shortDate } from '../../lib/format';
import { CheckDraw } from '../../lib/motion';
import { MSP } from '../../lib/labels';
import { useCompany, useProducts } from './hooks';

const STAGE_BY_STATUS: Record<string, number> = {
  draft: 0, pending_signature: 0, submitted: 1, data_check: 1, info_requested: 1, enrichment: 2, scoring: 2,
  manual_review: 3, committee_review: 3, offer_issued: 4, offer_accepted: 4, disbursement: 5,
};
const TITLES = ['Заявка', 'Проверка', 'Оценка', 'Решение', 'Подписание', 'Выдача'];

export function miniStages(status: string): Stage[] {
  const idx = STAGE_BY_STATUS[status] ?? 0;
  return TITLES.map((title, i) => ({ key: String(i), title, state: i < idx ? 'done' : i === idx ? 'current' : 'upcoming' }));
}

export const appLink = (a: { id: string; status: string }) => (a.status === 'draft' || a.status === 'pending_signature' ? `/applications/${a.id}/edit` : `/applications/${a.id}`);

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? 'Доброй ночи' : h < 12 ? 'Доброе утро' : h < 18 ? 'Добрый день' : 'Добрый вечер';
}

/** Кредитный потенциал: одобренная заранее сумма и выбор суммы прямо на главной. */
function Potential({ pre, companyId }: { pre: Preapproved; companyId: string }) {
  const nav = useNavigate();
  const products = useProducts(companyId);
  const product = products.data?.items.find((p) => p.code === pre.product_code);
  const min = Math.min(product?.min_amount ?? 100_000, pre.max_amount);
  const [amount, setAmount] = useState(Math.min(pre.max_amount, 500_000));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setAmount((a) => Math.min(Math.max(a, min), pre.max_amount)), [min, pre.max_amount]);
  const payment = annuity(amount, pre.rate_from, pre.term_months);
  const purposes = product?.purposes.map((p) => p.code) ?? [];
  const purpose = purposes.includes('any') ? 'any' : purposes.includes('working_capital') ? 'working_capital' : purposes[0] ?? 'any';

  const take = async () => {
    setBusy(true);
    setError(null);
    try {
      const app = await api.post<Application>('/api/v1/applications', {
        company_id: companyId, product_code: pre.product_code, amount, term_months: pre.term_months, purpose, preapproved: true,
      });
      nav(`/applications/${app.id}/edit`);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  return (
    <Plate size="lg">
      <Grid gutter={{ base: 24, md: 40 }} align="stretch">
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Group gap={8}>
            <Tag tone="ok">Одобрено заранее</Tag>
            <Text size="sm" c="dimmed">
              до {date(pre.valid_until)}
            </Text>
          </Group>
          <Box mt={14}>
            <Money value={pre.max_amount} prefix="до" size="clamp(40px, 7vw, 64px)" countUp />
          </Box>
          <Text fz={16} mt={10} c="var(--ink-2)">
            {pre.product_name} на {months(pre.term_months)}, ставка от {pct(pre.rate_from)}
          </Text>
          <Stack gap={8} mt={20}>
            {['Документы не нужны — банк видит обороты по счёту', 'Решение за несколько минут', 'Деньги — на расчётный счёт сразу после подписи'].map((t, i) => (
              <Group key={t} gap={10} wrap="nowrap">
                <CheckDraw size={18} delay={500 + i * 160} />
                <Text size="sm">{t}</Text>
              </Group>
            ))}
          </Stack>
          <Text size="xs" c="dimmed" mt={16}>
            На чём основан расчёт: {pre.basis.slice(0, 2).join(' · ')}
          </Text>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Box bg="#fff" p={{ base: 18, sm: 24 }} h="100%" style={{ borderRadius: 18, display: 'flex', flexDirection: 'column' }}>
            <Text size="sm" c="dimmed">
              Сколько взять
            </Text>
            <Money value={amount} size={34} />
            <Slider className="hint-thumb" mt={14} value={amount} onChange={setAmount} min={min} max={pre.max_amount} step={50_000} label={null} aria-label="Сумма" />
            <Group justify="space-between" mt={6}>
              <Text size="xs" c="dimmed" className="num">
                {money(min)}
              </Text>
              <Text size="xs" c="dimmed" className="num">
                {money(pre.max_amount)}
              </Text>
            </Group>
            <Group justify="space-between" mt={18} align="flex-end">
              <Text size="sm" c="dimmed">
                Платёж в месяц
              </Text>
              <Money value={payment} size={20} animate />
            </Group>
            {error && (
              <Alert color="bad" mt="sm">
                {error}
              </Alert>
            )}
            <Box mt="auto" pt={20}>
              <Button color="brand" size="lg" fullWidth onClick={take} loading={busy} rightSection={<IconArrowRight size={18} />}>
                Получить {money(amount)}
              </Button>
              <Button variant="subtle" size="sm" fullWidth mt={6} component={Link} to="/products">
                Другая цель или срок
              </Button>
            </Box>
          </Box>
        </Grid.Col>
      </Grid>
    </Plate>
  );
}

function NoPotential() {
  return (
    <Plate size="lg">
      <Grid gutter={{ base: 20, md: 40 }} align="center">
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Title order={2} fz={{ base: 24, sm: 30 }}>
            Узнайте, сколько можно получить
          </Title>
          <Text c="var(--ink-2)" mt={10} fz={16} maw={520}>
            Выберите цель, сумму и срок — сразу покажем подходящий продукт, ставку и платёж. Данные компании и обороты подставим сами.
          </Text>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Stack gap={8}>
            <Button color="brand" size="lg" component={Link} to="/products" rightSection={<IconArrowRight size={18} />}>
              Рассчитать
            </Button>
            <Group gap={8} justify="center">
              {[
                ['working_capital', 'Оборот'],
                ['equipment', 'Оборудование'],
                ['cash_gap', 'Кассовый разрыв'],
              ].map(([p, t]) => (
                <Link key={p} to={`/products?purpose=${p}`} className="tag" style={{ textDecoration: 'none' }}>
                  {t}
                </Link>
              ))}
            </Group>
          </Stack>
        </Grid.Col>
      </Grid>
    </Plate>
  );
}

function AppCard({ a }: { a: ApplicationSummary }) {
  const action = a.waiting === 'client';
  return (
    <Link to={appLink(a)} className={`plate sm link${action ? ' warn' : ''}`}>
      <Group justify="space-between" wrap="nowrap" align="flex-start" gap="sm">
        <Box style={{ minWidth: 0 }}>
          <Text fw={600} truncate>
            {a.product_name}
          </Text>
          <Text size="sm" c="dimmed" className="num">
            {a.number} · {months(a.term_months)}
          </Text>
        </Box>
        <Money value={a.offer?.amount ?? a.amount} size={19} />
      </Group>
      <Box mt={14}>
        <RouteMap stages={miniStages(a.status)} waiting={a.waiting} compact />
      </Box>
      <Group justify="space-between" mt={12} gap="xs" wrap="wrap">
        <StatusBadge label={a.status_label} tone={a.status_tone} size="sm" pulse={a.waiting === 'system'} />
        {a.next_action && (
          <Text size="sm" fw={action ? 600 : 500} c={action ? 'var(--warn-ink)' : 'dimmed'}>
            {a.next_action}
            {a.open_tasks ? ` · задач: ${a.open_tasks}` : ''}
          </Text>
        )}
      </Group>
    </Link>
  );
}

export function HomePage() {
  const { user, company } = useAuth();
  const details = useCompany(company?.id);
  const apps = useQuery({
    queryKey: ['applications', company?.id],
    queryFn: () => api.get<{ items: ApplicationSummary[] }>('/api/v1/applications', { company_id: company?.id }),
    enabled: !!company,
    refetchInterval: 6000,
  });
  const loans = useQuery({ queryKey: ['loans', company?.id], queryFn: () => api.get<{ items: Loan[] }>('/api/v1/loans', { company_id: company?.id }), enabled: !!company });
  if (!company) return <Navigate to="/companies/connect" replace />;
  const items = apps.data?.items ?? [];
  const active = items.filter((a) => !a.terminal);
  const recent = items.filter((a) => a.terminal).slice(0, 3);
  const pre = details.data?.preapproved?.[0];
  const firstName = user?.full_name.split(' ')[1] ?? user?.full_name;
  const loanList = loans.data?.items ?? [];

  return (
    <Stack gap={40} className="enter">
      <Box>
        <Title order={1} fz={{ base: 28, sm: 36 }}>
          {greeting()}, {firstName}
        </Title>
        <Text c="dimmed" mt={6}>
          {company.short_name} · {company.sector}
          {company.msp_category ? ` · ${MSP[company.msp_category].toLowerCase()}` : ''}
          {company.is_bank_client ? ' · клиент банка' : ''}
        </Text>
      </Box>

      {details.isLoading ? <Plate size="lg" style={{ minHeight: 260 }}>{null}</Plate> : pre ? <Potential pre={pre} companyId={company.id} /> : <NoPotential />}

      <Grid gutter={{ base: 32, md: 40 }}>
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Section title="Заявки" right={items.length > 0 ? <Link to="/applications" className="link-btn" style={{ fontSize: 14 }}>Все заявки</Link> : undefined}>
            <Stack gap={10} className="enter">
              {active.map((a) => (
                <AppCard key={a.id} a={a} />
              ))}
              {!active.length && (
                <Plate size="sm">
                  <Text size="sm" c="var(--ink-2)">
                    Активных заявок нет. {pre ? 'Одобренную сумму можно получить без документов — выберите сумму выше.' : 'Рассчитайте сумму и платёж — заявка заполнится данными, которые уже известны банку.'}
                  </Text>
                </Plate>
              )}
            </Stack>
            {recent.length > 0 && (
              <div className="rows" style={{ marginTop: 10 }}>
                {recent.map((a) => (
                  <Link key={a.id} to={appLink(a)} className="row">
                    <Box style={{ flex: 1, minWidth: 0 }}>
                      <Text size="sm" fw={500} className="row-title" truncate>
                        {a.product_name}
                      </Text>
                      <Text size="xs" c="dimmed" className="num">
                        {a.number} · {shortDate(a.created_at)}
                      </Text>
                    </Box>
                    <Text size="sm" className="num" fw={500}>
                      {money(a.offer?.amount ?? a.amount)}
                    </Text>
                    <Box w={150} ta="right" visibleFrom="xs">
                      <StatusBadge label={a.status_label} tone={a.status_tone} size="sm" />
                    </Box>
                  </Link>
                ))}
              </div>
            )}
          </Section>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Section title="Кредиты" right={loanList.length > 0 ? <Link to="/loans" className="link-btn" style={{ fontSize: 14 }}>График</Link> : undefined}>
            {loanList.length === 0 ? (
              <Plate size="sm">
                <Text size="sm" c="var(--ink-2)">
                  Действующих кредитов нет. После выдачи здесь появятся ближайший платёж и график.
                </Text>
              </Plate>
            ) : (
              <Stack gap={10}>
                {loanList.slice(0, 2).map((l) => (
                  <Link key={l.id} to="/loans" className="plate sm link">
                    <Text size="sm" c="dimmed">
                      {l.next_payment ? `Ближайший платёж ${date(l.next_payment.date)}` : 'Платежей по графику нет'}
                    </Text>
                    {l.next_payment && <Money value={l.next_payment.payment} size={26} />}
                    <SimpleGrid cols={2} mt={12} spacing="xs">
                      <Box>
                        <Text size="xs" c="dimmed">
                          {l.product_name}
                        </Text>
                        <Text size="sm" fw={500} className="num">
                          {money(l.amount)}
                        </Text>
                      </Box>
                      <Box>
                        <Text size="xs" c="dimmed">
                          Ставка
                        </Text>
                        <Text size="sm" fw={500}>
                          {pct(l.rate, 2)}
                        </Text>
                      </Box>
                    </SimpleGrid>
                  </Link>
                ))}
              </Stack>
            )}
          </Section>
        </Grid.Col>
      </Grid>

      <Feed companyId={company.id} limit={6} />
    </Stack>
  );
}
