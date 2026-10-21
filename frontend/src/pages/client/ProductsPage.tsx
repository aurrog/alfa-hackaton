import { Alert, Badge, Box, Button, Card, Collapse, Grid, Group, List, NumberInput, SegmentedControl, SimpleGrid, Slider, Stack, Switch, Text, ThemeIcon, Title, UnstyledButton } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconAlertTriangle, IconBan, IconBox, IconCheck, IconClock, IconDots, IconFileText, IconRocket, IconStar, IconTool } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { api, errorText } from '../../api/client';
import type { Application, Preapproved, Recommendation } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { PageHeader } from '../../components/ui';
import { money, months, pct } from '../../lib/format';
import { PRODUCT_KIND, PURPOSES } from '../../lib/labels';
import { useProducts } from './hooks';

const ICONS: Record<string, JSX.Element> = {
  box: <IconBox size={20} />, tool: <IconTool size={20} />, clock: <IconClock size={20} />, file: <IconFileText size={20} />,
  rocket: <IconRocket size={20} />, dots: <IconDots size={20} />,
};
const TERMS = ['6', '12', '18', '24', '36', '48', '60', '84'];

export function ProductsPage() {
  const { company } = useAuth();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const [purpose, setPurpose] = useState(sp.get('purpose') ?? 'working_capital');
  const [amount, setAmount] = useState<number>(Number(sp.get('amount')) || 1_500_000);
  const [term, setTerm] = useState(sp.get('term') ?? '24');
  const [urgent, setUrgent] = useState(true);
  const [regular, setRegular] = useState(purpose === 'cash_gap');
  const [collateral, setCollateral] = useState(false);
  const [creating, setCreating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [catalog, setCatalog] = useState(false);
  const [need] = useDebouncedValue({ purpose, amount, term: Number(term), urgent, regular, collateral }, 350);
  const products = useProducts(company?.id);

  const rec = useQuery({
    queryKey: ['recommend', company?.id, need],
    queryFn: () =>
      api.post<{ items: Recommendation[]; preapproved: Preapproved[]; key_rate: number }>('/api/v1/products/recommend', {
        company_id: company!.id, purpose: need.purpose, amount: need.amount || 100_000, term_months: need.term,
        urgent: need.urgent, regular: need.regular, has_collateral: need.collateral,
      }),
    enabled: !!company && need.amount > 0,
    placeholderData: (prev) => prev,
  });
  const pre = rec.data?.preapproved?.[0];
  const items = useMemo(() => rec.data?.items ?? [], [rec.data]);
  if (!company) return <Navigate to="/companies/connect" replace />;

  // цель заявки должна входить в цели продукта: иначе берём первую подходящую
  const purposeFor = (code: string) => {
    const ps = products.data?.items.find((p) => p.code === code)?.purposes.map((x) => x.code) ?? [];
    if (!ps.length || ps.includes(purpose) || ps.includes('any')) return purpose;
    return ps[0];
  };

  const create = async (r: Recommendation) => {
    setCreating(r.code);
    setError(null);
    try {
      const app = await api.post<Application>('/api/v1/applications', {
        company_id: company.id, product_code: r.code, amount: r.amount, term_months: r.term_months,
        purpose: purposeFor(r.code),
        preapproved: !!pre && pre.product_code === r.code && r.amount <= pre.max_amount,
      });
      nav(`/applications/${app.id}/edit`);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setCreating(null);
    }
  };

  return (
    <Stack gap="lg">
      <PageHeader
        eyebrow="Подбор финансирования"
        title="Какая задача у бизнеса?"
        subtitle="Опишите задачу — подберём продукт, объясним, почему он подходит и что может помешать, и покажем платёж ещё до заявки."
      />
      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Card>
            <Stack gap="md">
              <SimpleGrid cols={2} spacing="xs">
                {Object.entries(PURPOSES).map(([code, p]) => (
                  <UnstyledButton
                    key={code}
                    onClick={() => {
                      setPurpose(code);
                      if (code === 'cash_gap') setRegular(true);
                    }}
                    p="sm"
                    style={{ borderRadius: 12, border: `2px solid ${purpose === code ? 'var(--mantine-color-route-5)' : 'var(--line)'}`, background: purpose === code ? 'var(--mantine-color-route-0)' : undefined }}
                  >
                    <ThemeIcon variant={purpose === code ? 'filled' : 'light'} size={32} radius="md">
                      {ICONS[p.icon]}
                    </ThemeIcon>
                    <Text size="sm" fw={700} mt={6} lh={1.2}>
                      {p.title}
                    </Text>
                    <Text size="xs" c="dimmed" lh={1.3} mt={2}>
                      {p.hint}
                    </Text>
                  </UnstyledButton>
                ))}
              </SimpleGrid>
              <Box>
                <NumberInput label="Сколько нужно" value={amount} onChange={(v) => setAmount(Number(v) || 0)} min={100_000} max={200_000_000} step={100_000} suffix=" ₽" />
                <Slider mt="xs" value={Math.min(amount, 50_000_000)} onChange={setAmount} min={100_000} max={50_000_000} step={100_000} label={null} />
              </Box>
              <Box>
                <Text size="sm" fw={500} mb={4}>
                  На какой срок, мес.
                </Text>
                <SegmentedControl fullWidth value={term} onChange={setTerm} data={TERMS} />
              </Box>
              <Stack gap={8}>
                <Switch checked={urgent} onChange={(e) => setUrgent(e.currentTarget.checked)} label="Деньги нужны быстро" />
                <Switch checked={regular} onChange={(e) => setRegular(e.currentTarget.checked)} label="Потребность повторяется (оборот, разрывы)" />
                <Switch checked={collateral} onChange={(e) => setCollateral(e.currentTarget.checked)} label="Есть залог (недвижимость, оборудование, транспорт)" />
              </Stack>
            </Stack>
          </Card>
          {pre && (
            <Alert mt="md" color="lime" variant="light" icon={<IconStar size={18} />} title={`Вам предварительно одобрено до ${money(pre.max_amount)}`}>
              {pre.product_name}, ставка от {pct(pre.rate_from)}. {pre.basis[2]}
            </Alert>
          )}
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Stack gap="md">
            {error && (
              <Alert color="signal" variant="light" withCloseButton onClose={() => setError(null)}>
                {error}
              </Alert>
            )}
            {items.map((r) => (
              <Card key={r.code} style={r.best ? { borderColor: 'var(--mantine-color-route-5)', borderWidth: 2 } : r.eligible ? undefined : { opacity: 0.75 }}>
                <Group justify="space-between" align="flex-start" wrap="nowrap">
                  <Box>
                    <Group gap={8}>
                      <Title order={3}>{r.name}</Title>
                      {r.best && <Badge color="route" variant="filled">Лучший вариант</Badge>}
                      {r.gov_program && <Badge color="lime">Господдержка</Badge>}
                      {!r.eligible && <Badge color="gray">Недоступен</Badge>}
                    </Group>
                    <Text size="sm" c="dimmed" mt={2}>
                      {r.tagline}
                    </Text>
                  </Box>
                  <Box ta="right" style={{ flexShrink: 0 }}>
                    <Text size="xs" c="dimmed">
                      ставка от
                    </Text>
                    <Text fw={700} fz={22} className="num" ff="Unbounded, Onest, sans-serif">
                      {pct(r.rate_from)}
                    </Text>
                  </Box>
                </Group>
                <SimpleGrid cols={3} mt="md" spacing="xs">
                  <Box>
                    <Text size="xs" c="dimmed">
                      Сумма
                    </Text>
                    <Text fw={600} className="num">
                      {money(r.amount)}
                    </Text>
                  </Box>
                  <Box>
                    <Text size="xs" c="dimmed">
                      Срок
                    </Text>
                    <Text fw={600}>{months(r.term_months)}</Text>
                  </Box>
                  <Box>
                    <Text size="xs" c="dimmed">
                      {r.payment_kind === 'annuity' ? 'Платёж в месяц от' : 'Проценты в месяц от'}
                    </Text>
                    <Text fw={600} className="num">
                      {money(r.monthly_payment_from)}
                    </Text>
                  </Box>
                </SimpleGrid>
                <List mt="md" spacing={4} size="sm">
                  {r.pros.map((p) => (
                    <List.Item key={p} icon={<ThemeIcon size={18} radius="xl" color="lime" variant="light"><IconCheck size={12} /></ThemeIcon>}>
                      {p}
                    </List.Item>
                  ))}
                  {r.warnings.map((p) => (
                    <List.Item key={p} icon={<ThemeIcon size={18} radius="xl" color="amber" variant="light"><IconAlertTriangle size={12} /></ThemeIcon>}>
                      {p}
                    </List.Item>
                  ))}
                  {r.blockers.map((p) => (
                    <List.Item key={p} icon={<ThemeIcon size={18} radius="xl" color="signal" variant="light"><IconBan size={12} /></ThemeIcon>}>
                      {p}
                    </List.Item>
                  ))}
                </List>
                <Group justify="space-between" mt="md">
                  <Text size="xs" c="dimmed">
                    {PRODUCT_KIND[r.kind]} · {r.decision_time}
                  </Text>
                  <Button disabled={!r.eligible} loading={creating === r.code} onClick={() => create(r)} variant={r.best ? 'filled' : 'light'}>
                    Оформить заявку
                  </Button>
                </Group>
              </Card>
            ))}
            <Button variant="subtle" onClick={() => setCatalog((c) => !c)}>
              {catalog ? 'Скрыть каталог' : 'Все продукты и условия'}
            </Button>
            <Collapse in={catalog}>
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                {products.data?.items.map((p) => (
                  <Card key={p.code} padding="md">
                    <Text fw={700}>{p.name}</Text>
                    <Text size="sm" c="dimmed">
                      {p.description}
                    </Text>
                    <Text size="sm" mt="xs" className="num">
                      {money(p.min_amount)} – {money(p.max_amount)} · {p.min_term}–{p.max_term} мес. · от {pct(p.rate_from)}
                    </Text>
                    <Group gap={4} mt="xs">
                      {p.features.map((f) => (
                        <Badge key={f} size="xs" variant="outline" color="gray">
                          {f}
                        </Badge>
                      ))}
                    </Group>
                    {!p.eligible && (
                      <Text size="xs" c="signal" mt="xs">
                        {p.blockers.join('; ')}
                      </Text>
                    )}
                  </Card>
                ))}
              </SimpleGrid>
            </Collapse>
          </Stack>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
