import { Badge, Box, Card, Grid, Group, Progress, SegmentedControl, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../../api/client';
import { ErrorAlert, Loading, PageHeader, Stat } from '../../components/ui';
import { millions, num, share } from '../../lib/format';
import { LEVELS } from '../../lib/labels';

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dash = Record<string, any>;

const GRADE_HEX: Record<string, string> = { A: '#86bd20', B: '#12b886', C: '#ffa112', D: '#fd7e14', E: '#f11921' };

export function DashboardPage() {
  const [days, setDays] = useState('30');
  const q = useQuery({ queryKey: ['dashboard', days], queryFn: () => api.get<Dash>('/api/v1/bank/dashboard', { days }), refetchInterval: 15000 });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const d = q.data!;
  const k = d.kpi;
  const funnelMax = Math.max(...d.funnel.map((f: Dash) => f.value), 1);
  return (
    <Stack gap="lg">
      <PageHeader
        eyebrow="Управление процессом"
        title="Дашборд кредитного конвейера"
        subtitle="Скорость, конверсия, доля автоматических решений, нагрузка на специалистов и здоровье внешних источников."
        right={<SegmentedControl value={days} onChange={setDays} data={[{ value: '7', label: '7 дней' }, { value: '30', label: '30 дней' }, { value: '90', label: '90 дней' }]} />}
      />
      <SimpleGrid cols={{ base: 2, md: 4 }}>
        <Stat label="Подано заявок" value={num(k.submitted)} hint={`решений: ${k.decided}`} />
        <Stat label="Одобрено" value={k.approval_rate != null ? share(k.approval_rate, 0) : '—'} hint="от принятых решений" color="lime.8" />
        <Stat label="Автоматических решений" value={k.auto_decision_rate != null ? share(k.auto_decision_rate, 0) : '—'} hint="без участия специалиста" color="route" />
        <Stat
          label="Время до решения (медиана)"
          value={k.median_auto_decision_sec != null ? (k.median_auto_decision_sec < 120 ? `${k.median_auto_decision_sec} с` : `${num(k.median_auto_decision_sec / 60, 1)} мин`) : '—'}
          hint={`автоматически; у специалиста — ${k.median_manual_decision_hours != null ? `${num(k.median_manual_decision_hours, 1)} ч` : 'нет данных'}`}
        />
        <Stat label="Выдано" value={millions(k.issued_amount)} hint={`${k.issued_count} кредитов`} color="teal" />
        <Stat label="У специалистов" value={num(k.in_manual_review)} hint="аналитик и комитет" color="violet" />
        <Stat label="Нарушен норматив" value={num(k.sla_breached)} hint="заявок на рассмотрении" color={k.sla_breached ? 'signal' : undefined} />
        <Stat label="Ждут клиента" value={num(k.waiting_client)} hint={`в конвейере сейчас: ${k.in_pipeline}`} color="amber.8" />
      </SimpleGrid>
      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Card>
            <Title order={3} mb="md">
              Динамика по дням
            </Title>
            <Box h={280}>
              <ResponsiveContainer>
                <ComposedChart data={d.daily.map((x: Dash) => ({ ...x, date: x.date.slice(5).split('-').reverse().join('.'), issued: Math.round(x.issued_amount / 1e6 * 10) / 10 }))}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e7ee" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis yAxisId="l" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 11 }} unit=" млн" />
                  <Tooltip formatter={(v: number, n: string) => (n === 'Выдано, млн ₽' ? `${num(v, 1)} млн ₽` : v)} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar yAxisId="l" dataKey="submitted" name="Подано" fill="#a6c1ff" radius={[4, 4, 0, 0]} />
                  <Bar yAxisId="l" dataKey="approved" name="Одобрено" fill="#9bd72e" radius={[4, 4, 0, 0]} />
                  <Line yAxisId="r" dataKey="issued" name="Выдано, млн ₽" stroke="#12b886" strokeWidth={2} dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </Box>
          </Card>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Card h="100%">
            <Title order={3} mb="md">
              Воронка
            </Title>
            <Stack gap="sm">
              {d.funnel.map((f: Dash, i: number) => (
                <Box key={f.stage}>
                  <Group justify="space-between">
                    <Text size="sm">{f.stage}</Text>
                    <Text size="sm" fw={700} className="num">
                      {f.value}
                      {i > 0 && d.funnel[0].value ? <Text span size="xs" c="dimmed"> · {share(f.value / d.funnel[0].value, 0)}</Text> : null}
                    </Text>
                  </Group>
                  <Progress value={(f.value / funnelMax) * 100} color={['route', 'violet', 'lime', 'teal', 'teal'][i]} size="lg" radius="sm" />
                </Box>
              ))}
            </Stack>
            <Group mt="lg" gap="xs">
              <Badge color="lime">одобрено {d.outcomes.approve}</Badge>
              <Badge color="amber">контрпредложений {d.outcomes.counter_offer}</Badge>
              <Badge color="signal">отказов {d.outcomes.decline}</Badge>
            </Group>
          </Card>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Card h="100%">
            <Title order={3} mb="md">
              Грейды риска
            </Title>
            <Box h={200}>
              <ResponsiveContainer>
                <BarChart data={d.grades}>
                  <XAxis dataKey="grade" />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" name="Заявок" radius={[4, 4, 0, 0]}>
                    {d.grades.map((g: Dash) => (
                      <Cell key={g.grade} fill={GRADE_HEX[g.grade]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Box>
            <Text size="sm" fw={600} mt="md" mb={4}>
              Уровни решений
            </Text>
            {Object.entries(d.decision_levels as Record<string, number>).map(([lvl, n]) => (
              <Group key={lvl} justify="space-between">
                <Text size="sm">{LEVELS[lvl]}</Text>
                <Text size="sm" fw={600}>
                  {n}
                </Text>
              </Group>
            ))}
          </Card>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Card h="100%">
            <Title order={3} mb="md">
              Продукты
            </Title>
            <Table fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Продукт</Table.Th>
                  <Table.Th ta="right">Подано</Table.Th>
                  <Table.Th ta="right">Решений</Table.Th>
                  <Table.Th ta="right">Одобрено</Table.Th>
                  <Table.Th ta="right">Уровень одобрения</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {d.by_product.map((p: Dash) => (
                  <Table.Tr key={p.code}>
                    <Table.Td>{p.name}</Table.Td>
                    <Table.Td ta="right">{p.submitted}</Table.Td>
                    <Table.Td ta="right">{p.decided}</Table.Td>
                    <Table.Td ta="right">{p.approved}</Table.Td>
                    <Table.Td ta="right">{p.approval_rate != null ? share(p.approval_rate, 0) : '—'}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            <Title order={4} mt="lg" mb="xs">
              Внешние источники за 24 часа
            </Title>
            <Table fz="sm">
              <Table.Tbody>
                {d.integration_health.map((h: Dash) => (
                  <Table.Tr key={h.source}>
                    <Table.Td>{h.title}</Table.Td>
                    <Table.Td ta="right">{h.ok + h.errors} вызовов</Table.Td>
                    <Table.Td ta="right">
                      <Badge color={h.error_rate > 0.2 ? 'signal' : h.error_rate > 0.05 ? 'amber' : 'lime'}>ошибок {share(h.error_rate, 0)}</Badge>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
