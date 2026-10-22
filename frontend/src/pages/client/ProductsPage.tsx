import { Alert, Box, Button, Checkbox, Grid, Group, Modal, NumberInput, SimpleGrid, Slider, Stack, Text, Title, UnstyledButton } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconAlertTriangle, IconArrowRight, IconCheck, IconX } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { api, errorText } from '../../api/client';
import type { Application, Preapproved, Recommendation } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { Money, PageTitle, Plate, Steps, Tag } from '../../components/ui';
import { money, months, pct } from '../../lib/format';
import { PRODUCT_KIND, PURPOSES } from '../../lib/labels';
import { useProducts } from './hooks';

export const FLOW = ['Расчёт', 'Данные', 'Подпись'];
const TERMS = [6, 12, 18, 24, 36, 48, 60, 84];
const MIN = 100_000;
const MAX = 50_000_000;

/** Логарифмическая шкала ползунка: точный выбор и для 300 тысяч, и для 30 миллионов. */
const toPos = (a: number) => (100 * Math.log(Math.min(Math.max(a, MIN), MAX) / MIN)) / Math.log(MAX / MIN);
function fromPos(p: number) {
  const raw = MIN * (MAX / MIN) ** (p / 100);
  const step = raw < 1_000_000 ? 50_000 : raw < 5_000_000 ? 100_000 : raw < 20_000_000 ? 500_000 : 1_000_000;
  return Math.round(raw / step) * step;
}

function Panel({ r, pre, requested }: { r: Recommendation; pre?: Preapproved; requested: { amount: number; term: number } }) {
  const inLimit = !!pre && pre.product_code === r.code && r.amount <= pre.max_amount;
  const adjusted = r.amount !== requested.amount || r.term_months !== requested.term;
  return (
    <Box className="rise" key={r.code}>
      <Text size="sm" c="dimmed">
        {r.best ? 'Подходит лучше всего' : 'Выбранный вариант'}
      </Text>
      <Group gap={8} mt={4} wrap="wrap">
        <Title order={2} fz={26}>
          {r.name}
        </Title>
        {r.gov_program && <Tag tone="info">Господдержка</Tag>}
      </Group>
      <Text size="sm" c="var(--ink-2)" mt={4}>
        {r.tagline}
      </Text>
      <Box mt={22}>
        <Text size="sm" c="dimmed">
          {r.payment_kind === 'annuity' ? 'Платёж в месяц' : 'Проценты в месяц при полном использовании'}
        </Text>
        <Money value={r.monthly_payment_from} prefix="от" size={40} animate />
      </Box>
      <SimpleGrid cols={3} mt={18} spacing="sm">
        <Box>
          <Text size="xs" c="dimmed">
            Сумма
          </Text>
          <Text fw={600} size="sm" className="num">
            {money(r.amount)}
          </Text>
        </Box>
        <Box>
          <Text size="xs" c="dimmed">
            Срок
          </Text>
          <Text fw={600} size="sm">
            {months(r.term_months)}
          </Text>
        </Box>
        <Box>
          <Text size="xs" c="dimmed">
            Ставка
          </Text>
          <Text fw={600} size="sm">
            от {pct(r.rate_from)}
          </Text>
        </Box>
      </SimpleGrid>
      {adjusted && (
        <Text size="xs" c="dimmed" mt={8}>
          Сумма и срок приведены к условиям продукта: {money(r.min_amount)} – {money(r.max_amount)}, {r.min_term}–{r.max_term} мес.
        </Text>
      )}
      <Stack gap={8} mt={18}>
        {inLimit && (
          <Group gap={10} wrap="nowrap" align="flex-start">
            <IconCheck size={17} color="var(--ok)" stroke={2.4} style={{ flex: 'none', marginTop: 2 }} />
            <Text size="sm" fw={600}>
              В пределах одобренного лимита — документы не нужны
            </Text>
          </Group>
        )}
        {r.pros.slice(0, 3).map((p) => (
          <Group key={p} gap={10} wrap="nowrap" align="flex-start">
            <IconCheck size={17} color="var(--ok)" stroke={2.4} style={{ flex: 'none', marginTop: 2 }} />
            <Text size="sm">{p}</Text>
          </Group>
        ))}
        {r.warnings.map((p) => (
          <Group key={p} gap={10} wrap="nowrap" align="flex-start">
            <IconAlertTriangle size={17} color="var(--warn)" style={{ flex: 'none', marginTop: 2 }} />
            <Text size="sm">{p}</Text>
          </Group>
        ))}
        {r.blockers.map((p) => (
          <Group key={p} gap={10} wrap="nowrap" align="flex-start">
            <IconX size={17} color="var(--bad)" stroke={2.4} style={{ flex: 'none', marginTop: 2 }} />
            <Text size="sm">{p}</Text>
          </Group>
        ))}
      </Stack>
      <Text size="xs" c="dimmed" mt={16}>
        {PRODUCT_KIND[r.kind]} · {r.decision_time.toLowerCase()} · точные условия — в предложении банка после оценки
      </Text>
    </Box>
  );
}

export function ProductsPage() {
  const { company } = useAuth();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const initialPurpose = sp.get('purpose');
  const [purpose, setPurpose] = useState(initialPurpose && PURPOSES[initialPurpose] ? initialPurpose : 'working_capital');
  const [amount, setAmount] = useState<number>(Number(sp.get('amount')) || 1_500_000);
  const [term, setTerm] = useState<number>(Number(sp.get('term')) || 24);
  const [regular, setRegular] = useState(purpose === 'cash_gap');
  const [collateral, setCollateral] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [catalog, setCatalog] = useState(false);
  const [need] = useDebouncedValue({ purpose, amount, term, regular, collateral }, 300);
  const products = useProducts(company?.id);

  const rec = useQuery({
    queryKey: ['recommend', company?.id, need],
    queryFn: () =>
      api.post<{ items: Recommendation[]; preapproved: Preapproved[]; key_rate: number }>('/api/v1/products/recommend', {
        company_id: company!.id, purpose: need.purpose, amount: need.amount || MIN, term_months: need.term,
        urgent: true, regular: need.regular, has_collateral: need.collateral,
      }),
    enabled: !!company && need.amount > 0,
    placeholderData: (prev) => prev,
  });
  const pre = rec.data?.preapproved?.[0];
  const items = useMemo(() => rec.data?.items ?? [], [rec.data]);
  const best = items.find((r) => r.best) ?? items.find((r) => r.eligible);
  const current = items.find((r) => r.code === selected && r.eligible) ?? best;
  const others = items.filter((r) => r.code !== current?.code);

  useEffect(() => {
    // при смене задачи сбрасываем ручной выбор: лучший вариант мог поменяться
    setSelected(null);
  }, [need.purpose, need.regular, need.collateral]);

  if (!company) return <Navigate to="/companies/connect" replace />;

  // цель заявки должна входить в цели продукта: иначе берём первую подходящую
  const purposeFor = (code: string) => {
    const ps = products.data?.items.find((p) => p.code === code)?.purposes.map((x) => x.code) ?? [];
    if (!ps.length || ps.includes(purpose) || ps.includes('any')) return purpose;
    return ps[0];
  };

  const create = async () => {
    if (!current) return;
    setCreating(true);
    setError(null);
    try {
      const app = await api.post<Application>('/api/v1/applications', {
        company_id: company.id, product_code: current.code, amount: current.amount, term_months: current.term_months,
        purpose: purposeFor(current.code),
        preapproved: !!pre && pre.product_code === current.code && current.amount <= pre.max_amount,
      });
      nav(`/applications/${app.id}/edit`);
    } catch (e) {
      setError(errorText(e));
      setCreating(false);
    }
  };

  const cta = (
    <Button color="brand" size="lg" fullWidth onClick={create} loading={creating} disabled={!current?.eligible} rightSection={<IconArrowRight size={18} />}>
      Продолжить
    </Button>
  );

  return (
    <Box>
      <PageTitle top={<Steps current={0} titles={FLOW} />} title="Новая заявка" sub="Подберём продукт под задачу и покажем платёж ещё до заявки. Данные компании подставим сами." />
      <Grid gutter={{ base: 28, md: 48 }}>
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Stack gap={36} className="enter">
            <Box>
              <Title order={3} mb={12}>
                На что нужны деньги
              </Title>
              <SimpleGrid cols={{ base: 2, sm: 3 }} spacing={8}>
                {Object.entries(PURPOSES).map(([code, p]) => (
                  <button
                    key={code}
                    type="button"
                    className="choice"
                    data-active={purpose === code}
                    onClick={() => {
                      setPurpose(code);
                      if (code === 'cash_gap') setRegular(true);
                    }}
                  >
                    <div className="t">{p.title}</div>
                    <div className="h">{p.hint}</div>
                  </button>
                ))}
              </SimpleGrid>
            </Box>

            <Box>
              <Title order={3} mb={12}>
                Сколько
              </Title>
              <NumberInput
                value={amount}
                onChange={(v) => setAmount(Math.min(Number(v) || 0, 200_000_000))}
                min={MIN}
                max={200_000_000}
                step={50_000}
                suffix=" ₽"
                hideControls
                size="xl"
                aria-label="Сумма"
                styles={{ input: { fontFamily: 'var(--display)', fontWeight: 700, fontSize: 30, height: 64, letterSpacing: '-0.02em' } }}
              />
              <Slider mt={16} value={toPos(amount)} onChange={(p) => setAmount(fromPos(p))} min={0} max={100} step={0.5} label={null} aria-label="Сумма на шкале" />
              <Group justify="space-between" mt={6}>
                <Text size="xs" c="dimmed">
                  100 тыс.
                </Text>
                <Text size="xs" c="dimmed">
                  50 млн
                </Text>
              </Group>
            </Box>

            <Box>
              <Title order={3} mb={12}>
                На какой срок
              </Title>
              <div className="chips">
                {TERMS.map((t) => (
                  <button key={t} type="button" className="choice" data-active={term === t} onClick={() => setTerm(t)}>
                    {t} мес.
                  </button>
                ))}
              </div>
            </Box>

            <Stack gap={12}>
              <Checkbox checked={collateral} onChange={(e) => setCollateral(e.currentTarget.checked)} label="Есть залог — недвижимость, оборудование или транспорт" description="С залогом можно получить больше и дешевле" />
              <Checkbox checked={regular} onChange={(e) => setRegular(e.currentTarget.checked)} label="Деньги нужны регулярно" description="Подойдёт лимит: берёте и возвращаете, проценты — только за использованное" />
            </Stack>
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 5 }}>
          <Box pos="sticky" top={92}>
            <Plate size="lg">
              {current ? <Panel key={current.code} r={current} pre={pre} requested={{ amount, term }} /> : <Text c="dimmed">{rec.isLoading ? 'Считаем…' : 'Нет подходящих продуктов — измените сумму или срок.'}</Text>}
              {error && (
                <Alert color="bad" mt="md">
                  {error}
                </Alert>
              )}
              <Box mt={24} visibleFrom="md">
                {cta}
              </Box>
            </Plate>
            {others.length > 0 && (
              <Box mt={20}>
                <Text size="sm" fw={600} mb={4}>
                  Другие варианты
                </Text>
                <div className="rows">
                  {others.map((r) => (
                    <UnstyledButton key={r.code} className="row" onClick={() => r.eligible && setSelected(r.code)} style={{ opacity: r.eligible ? 1 : 0.55, cursor: r.eligible ? 'pointer' : 'default', padding: '11px 0' }}>
                      <Box style={{ flex: 1, minWidth: 0 }}>
                        <Text size="sm" fw={500} className="row-title" truncate>
                          {r.name}
                        </Text>
                        <Text size="xs" c="dimmed" truncate>
                          {r.eligible ? r.tagline : r.blockers[0]}
                        </Text>
                      </Box>
                      <Box ta="right">
                        <Text size="sm" fw={600} className="num">
                          от {pct(r.rate_from)}
                        </Text>
                        {r.eligible && (
                          <Text size="xs" c="dimmed" className="num">
                            {money(r.monthly_payment_from)}/мес
                          </Text>
                        )}
                      </Box>
                    </UnstyledButton>
                  ))}
                </div>
                <button type="button" className="link-btn" style={{ fontSize: 13.5, marginTop: 10 }} onClick={() => setCatalog(true)}>
                  Все продукты и условия
                </button>
              </Box>
            )}
          </Box>
        </Grid.Col>
      </Grid>

      {current && (
        <Box className="sticky-cta" hiddenFrom="md">
          <Group justify="space-between" wrap="nowrap" gap="md">
            <Box>
              <Text size="xs" c="dimmed">
                {current.name}
              </Text>
              <Money value={current.monthly_payment_from} prefix="от" size={20} animate />
              <Text span size="xs" c="dimmed">
                {' '}
                в мес.
              </Text>
            </Box>
            <Box w={180}>{cta}</Box>
          </Group>
        </Box>
      )}

      <Modal opened={catalog} onClose={() => setCatalog(false)} size="xl" title="Продукты и условия">
        <div className="rows">
          {products.data?.items.map((p) => (
            <Box key={p.code} py={14}>
              <Group justify="space-between" wrap="nowrap" align="flex-start">
                <Box>
                  <Text fw={600}>{p.name}</Text>
                  <Text size="sm" c="dimmed">
                    {p.description}
                  </Text>
                </Box>
                <Text fw={600} className="num" style={{ flex: 'none' }}>
                  от {pct(p.rate_from)}
                </Text>
              </Group>
              <Text size="sm" mt={6} className="num">
                {money(p.min_amount)} – {money(p.max_amount)} · {p.min_term}–{p.max_term} мес.
              </Text>
              <Group gap={6} mt={8}>
                {p.features.map((f) => (
                  <Tag key={f}>{f}</Tag>
                ))}
              </Group>
              {!p.eligible && (
                <Text size="xs" c="bad" mt={6}>
                  {p.blockers.join('; ')}
                </Text>
              )}
            </Box>
          ))}
        </div>
      </Modal>
    </Box>
  );
}
