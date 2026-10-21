import { Badge, Box, Button, Card, Grid, Group, List, SimpleGrid, Stack, Text, ThemeIcon, Title, UnstyledButton } from '@mantine/core';
import { IconArrowRight, IconBolt, IconCheck, IconSparkles } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { ApplicationSummary, Loan } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { Feed } from '../../components/Feed';
import { RouteMap } from '../../components/RouteMap';
import { StatusBadge, WaitingChip } from '../../components/ui';
import { date, money, months, pct } from '../../lib/format';
import { MSP } from '../../lib/labels';
import { useCompany } from './hooks';

const STAGE_BY_STATUS: Record<string, number> = {
  draft: 0, pending_signature: 0, submitted: 1, data_check: 1, info_requested: 1, enrichment: 2, scoring: 2,
  manual_review: 3, committee_review: 3, offer_issued: 4, offer_accepted: 4, disbursement: 5,
};
const TITLES = ['Заявка', 'Проверка данных', 'Оценка', 'Решение', 'Подписание', 'Выдача'];

function miniStages(status: string) {
  const idx = STAGE_BY_STATUS[status] ?? 0;
  return TITLES.map((title, i) => ({ key: String(i), title, state: (i < idx ? 'done' : i === idx ? 'current' : 'upcoming') as 'done' | 'current' | 'upcoming' }));
}

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? 'Доброй ночи' : h < 12 ? 'Доброе утро' : h < 18 ? 'Добрый день' : 'Добрый вечер';
}

export function HomePage() {
  const { user, company } = useAuth();
  const nav = useNavigate();
  const details = useCompany(company?.id);
  const apps = useQuery({
    queryKey: ['applications', company?.id],
    queryFn: () => api.get<{ items: ApplicationSummary[] }>('/api/v1/applications', { company_id: company?.id }),
    enabled: !!company,
    refetchInterval: 6000,
  });
  const loans = useQuery({ queryKey: ['loans', company?.id], queryFn: () => api.get<{ items: Loan[] }>('/api/v1/loans', { company_id: company?.id }), enabled: !!company });
  if (!company) return <Navigate to="/companies/connect" replace />;
  const active = (apps.data?.items ?? []).filter((a) => !a.terminal);
  const recent = (apps.data?.items ?? []).filter((a) => a.terminal).slice(0, 3);
  const pre = details.data?.preapproved?.[0];
  const firstName = user?.full_name.split(' ')[1] ?? user?.full_name;

  return (
    <Stack gap="lg">
      <Box>
        <Title order={1}>
          {greeting()}, {firstName}
        </Title>
        <Text c="dimmed" mt={4}>
          {company.short_name} · ИНН {company.inn} · {company.sector}
          {company.msp_category ? ` · ${MSP[company.msp_category]}` : ''}
          {company.is_bank_client ? ' · клиент банка' : ''}
        </Text>
      </Box>
      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Stack gap="lg">
            {pre && (
              <Card className="hero" padding="xl">
                <Group gap={8}>
                  <ThemeIcon color="lime" variant="filled" radius="xl" size={26}>
                    <IconBolt size={16} color="#14161f" />
                  </ThemeIcon>
                  <Text fw={700} c="lime.4">
                    Предварительно одобрено
                  </Text>
                </Group>
                <Text fz={{ base: 30, sm: 40 }} fw={700} ff="Unbounded, Onest, sans-serif" mt="sm" className="num">
                  до {money(pre.max_amount)}
                </Text>
                <Text className="muted" mt={4}>
                  {pre.product_name} на {months(pre.term_months)} · ставка от {pct(pre.rate_from)} · платёж от {money(pre.monthly_payment)} в месяц · до {date(pre.valid_until)}
                </Text>
                <List mt="md" spacing={4} size="sm" icon={<IconCheck size={14} color="#b5e853" />}>
                  {pre.basis.map((b) => (
                    <List.Item key={b}>
                      <Text size="sm" c="#d9ddea">
                        {b}
                      </Text>
                    </List.Item>
                  ))}
                </List>
                <Group mt="lg">
                  <Button color="lime" c="ink.9" rightSection={<IconArrowRight size={16} />} onClick={() => nav(`/products?purpose=any&amount=${Math.min(pre.max_amount, 1_000_000)}&term=${pre.term_months}`)}>
                    Получить без документов
                  </Button>
                </Group>
              </Card>
            )}
            <Card>
              <Group justify="space-between" mb="md">
                <Title order={3}>Заявки в работе</Title>
                <Button variant="light" size="xs" component={Link} to="/products">
                  Новая заявка
                </Button>
              </Group>
              {!active.length && (
                <Stack align="flex-start" gap="xs">
                  <Text c="dimmed" size="sm">
                    Активных заявок нет. Опишите задачу — подберём продукт, покажем платёж и заполним заявку данными, которые уже известны.
                  </Text>
                  <Button rightSection={<IconArrowRight size={16} />} component={Link} to="/products">
                    Подобрать финансирование
                  </Button>
                </Stack>
              )}
              <Stack gap="sm">
                {active.map((a) => (
                  <Card key={a.id} padding="md" withBorder component={Link} to={a.status === 'draft' || a.status === 'pending_signature' ? `/applications/${a.id}/edit` : `/applications/${a.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                    <Group justify="space-between" wrap="nowrap">
                      <Box>
                        <Group gap={8}>
                          <Text fw={700}>{a.product_name}</Text>
                          <StatusBadge label={a.status_label} tone={a.status_tone} size="sm" />
                        </Group>
                        <Text size="sm" c="dimmed" className="num">
                          {a.number} · {money(a.amount)} · {months(a.term_months)}
                        </Text>
                      </Box>
                      <WaitingChip waiting={a.waiting} due={a.sla_due_at} />
                    </Group>
                    <Box mt="sm">
                      <RouteMap stages={miniStages(a.status)} waiting={a.waiting} compact />
                    </Box>
                    {a.next_action && (
                      <Text size="sm" mt="xs" fw={600} c={a.waiting === 'client' ? 'amber.8' : undefined}>
                        → {a.next_action}
                        {a.open_tasks ? ` (задач: ${a.open_tasks})` : ''}
                      </Text>
                    )}
                  </Card>
                ))}
              </Stack>
              {recent.length > 0 && (
                <Stack gap={6} mt="md">
                  <Text size="xs" c="dimmed" fw={600} tt="uppercase">
                    Завершённые
                  </Text>
                  {recent.map((a) => (
                    <UnstyledButton key={a.id} component={Link} to={`/applications/${a.id}`}>
                      <Group justify="space-between">
                        <Text size="sm">
                          {a.number} · {a.product_name} · {money(a.amount)}
                        </Text>
                        <StatusBadge label={a.status_label} tone={a.status_tone} size="sm" />
                      </Group>
                    </UnstyledButton>
                  ))}
                </Stack>
              )}
            </Card>
            {!!loans.data?.items.length && (
              <Card>
                <Group justify="space-between" mb="sm">
                  <Title order={3}>Кредиты</Title>
                  <Button variant="subtle" size="xs" component={Link} to="/loans">
                    Все кредиты
                  </Button>
                </Group>
                <SimpleGrid cols={{ base: 1, sm: 2 }}>
                  {loans.data.items.slice(0, 2).map((l) => (
                    <Box key={l.id}>
                      <Text fw={600}>{l.product_name}</Text>
                      <Text size="sm" c="dimmed" className="num">
                        {money(l.amount)} · {pct(l.rate)} · платёж {money(l.monthly_payment)}
                      </Text>
                      {l.next_payment && (
                        <Badge mt={4} variant="light" color="amber">
                          ближайший платёж {date(l.next_payment.date)}
                        </Badge>
                      )}
                    </Box>
                  ))}
                </SimpleGrid>
              </Card>
            )}
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Card bg="transparent" withBorder={false} p={0}>
            <Group gap={6} mb="xs">
              <IconSparkles size={16} />
              <Text size="xs" c="dimmed" fw={600} tt="uppercase">
                Персонально
              </Text>
            </Group>
            <Feed companyId={company.id} limit={8} />
          </Card>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
