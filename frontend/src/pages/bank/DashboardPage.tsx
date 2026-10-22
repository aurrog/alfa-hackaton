import { Box, Grid, Group, Progress, SegmentedControl, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../../api/client';
import { ErrorAlert, Loading, PageTitle, Plate, Stat, Status } from '../../components/ui';
import { millions, num, share } from '../../lib/format';
import { GRADE_HEX, LEVELS } from '../../lib/labels';
import { AnimatedNumber } from '../../lib/motion';

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dash = Record<string, any>;

const AXIS = { fontSize: 11, fill: '#747883' };

export function DashboardPage() {
  const [days, setDays] = useState('30');
  const q = useQuery({ queryKey: ['dashboard', days], queryFn: () => api.get<Dash>('/api/v1/bank/dashboard', { days }), refetchInterval: 15000 });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const d = q.data!;
  const k = d.kpi;
  const funnelMax = Math.max(...d.funnel.map((f: Dash) => f.value), 1);
  const pctF = (v: number) => share(v, 0);
  return (
    <Box>
      <PageTitle
        title="Дашборд кредитного конвейера"
        sub="Скорость, конверсия, доля автоматических решений, нагрузка на специалистов и здоровье внешних источников."
        right={<SegmentedControl value={days} onChange={setDays} data={[{ value: '7', label: '7 дней' }, { value: '30', label: '30 дней' }, { value: '90', label: '90 дней' }]} />}
      />
      <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }} spacing="md" className="enter">
        <Stat label="Подано заявок" value={<AnimatedNumber value={k.submitted} format={(v) => num(Math.round(v))} />} hint={`решений: ${k.decided}`} />
        <Stat label="Одобрено" value={k.approval_rate != null ? <AnimatedNumber value={k.approval_rate} format={pctF} /> : '—'} hint="от принятых решений" color="ok" />
        <Stat label="Автоматических решений" value={k.auto_decision_rate != null ? <AnimatedNumber value={k.auto_decision_rate} format={pctF} /> : '—'} hint="без участия специалиста" />
        <Stat
          label="Время до решения, медиана"
          value={k.median_auto_decision_sec != null ? (k.median_auto_decision_sec < 120 ? `${k.median_auto_decision_sec} с` : `${num(k.median_auto_decision_sec / 60, 1)} мин`) : '—'}
          hint={`автоматически; у специалиста — ${k.median_manual_decision_hours != null ? `${num(k.median_manual_decision_hours, 1)} ч` : 'нет данных'}`}
        />
        <Stat label="Выдано" value={<AnimatedNumber value={k.issued_amount} format={(v) => millions(Math.round(v / 100_000) * 100_000)} />} hint={`${k.issued_count} кредитов`} />
        <Stat label="У специалистов" value={num(k.in_manual_review)} hint="аналитик и комитет" color="info" />
        <Stat label="Нарушен норматив" value={num(k.sla_breached)} hint="заявок на рассмотрении" color={k.sla_breached ? 'bad' : undefined} />
        <Stat label="Ждут клиента" value={num(k.waiting_client)} hint={`в конвейере сейчас: ${k.in_pipeline}`} color="var(--warn-ink)" />
      </SimpleGrid>
      <Grid gutter="lg" mt="lg">
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Plate>
            <Title order={3} mb="md">
              Динамика по дням
            </Title>
            <Box h={280}>
              <ResponsiveContainer>
                <ComposedChart data={d.daily.map((x: Dash) => ({ ...x, date: x.date.slice(5).split('-').reverse().join('.'), issued: Math.round((x.issued_amount / 1e6) * 10) / 10 }))}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#dfe2e7" />
                  <XAxis dataKey="date" tick={AXIS} interval="preserveStartEnd" axisLine={false} tickLine={false} />
                  <YAxis yAxisId="l" allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} />
                  <YAxis yAxisId="r" orientation="right" tick={AXIS} unit=" млн" axisLine={false} tickLine={false} />
                  <Tooltip formatter={(v: number, n: string) => (n === 'Выдано, млн ₽' ? `${num(v, 1)} млн ₽` : v)} contentStyle={{ borderRadius: 12, border: '1px solid #e6e8ec' }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} formatter={(v: string) => <span style={{ color: '#44474f' }}>{v}</span>} />
                  <Bar yAxisId="l" dataKey="submitted" name="Подано" fill="#c9cdd4" radius={[4, 4, 0, 0]} />
                  <Bar yAxisId="l" dataKey="approved" name="Одобрено" fill="#0e0f11" radius={[4, 4, 0, 0]} />
                  <Line yAxisId="r" dataKey="issued" name="Выдано, млн ₽" stroke="#ef3124" strokeWidth={2} dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </Box>
          </Plate>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Plate style={{ height: '100%' }}>
            <Title order={3} mb="md">
              Воронка
            </Title>
            <Stack gap="md">
              {d.funnel.map((f: Dash, i: number) => (
                <Box key={f.stage}>
                  <Group justify="space-between" mb={4}>
                    <Text size="sm">{f.stage}</Text>
                    <Text size="sm" fw={700} className="num">
                      {f.value}
                      {i > 0 && d.funnel[0].value ? (
                        <Text span size="xs" c="dimmed" fw={500}>
                          {' '}
                          · {share(f.value / d.funnel[0].value, 0)}
                        </Text>
                      ) : null}
                    </Text>
                  </Group>
                  <Progress value={(f.value / funnelMax) * 100} color={i === d.funnel.length - 1 ? 'brand' : 'ink'} size="md" transitionDuration={700} />
                </Box>
              ))}
            </Stack>
            <Group mt="lg" gap="md">
              <Status tone="ok" size="sm">
                одобрено {d.outcomes.approve}
              </Status>
              <Status tone="warn" size="sm">
                другие условия {d.outcomes.counter_offer}
              </Status>
              <Status tone="bad" size="sm">
                отказы {d.outcomes.decline}
              </Status>
            </Group>
          </Plate>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Plate style={{ height: '100%' }}>
            <Title order={3} mb="md">
              Грейды риска
            </Title>
            <Box h={200}>
              <ResponsiveContainer>
                <BarChart data={d.grades}>
                  <XAxis dataKey="grade" tick={AXIS} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #e6e8ec' }} />
                  <Bar dataKey="count" name="Заявок" radius={[6, 6, 0, 0]}>
                    {d.grades.map((g: Dash) => (
                      <Cell key={g.grade} fill={GRADE_HEX[g.grade]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Box>
            <Text size="sm" fw={600} mt="md" mb={2}>
              Уровни решений
            </Text>
            <div className="rows">
              {Object.entries(d.decision_levels as Record<string, number>).map(([lvl, n]) => (
                <Group key={lvl} justify="space-between" py={6}>
                  <Text size="sm">{LEVELS[lvl]}</Text>
                  <Text size="sm" fw={600} className="num">
                    {n}
                  </Text>
                </Group>
              ))}
            </div>
          </Plate>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Plate style={{ height: '100%' }}>
            <Title order={3} mb="sm">
              Продукты
            </Title>
            <Table>
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
                    <Table.Td ta="right" className="num">
                      {p.submitted}
                    </Table.Td>
                    <Table.Td ta="right" className="num">
                      {p.decided}
                    </Table.Td>
                    <Table.Td ta="right" className="num">
                      {p.approved}
                    </Table.Td>
                    <Table.Td ta="right" className="num">
                      {p.approval_rate != null ? share(p.approval_rate, 0) : '—'}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            <Title order={4} mt="xl" mb="xs">
              Внешние источники за 24 часа
            </Title>
            <Table>
              <Table.Tbody>
                {d.integration_health.map((h: Dash) => (
                  <Table.Tr key={h.source}>
                    <Table.Td>{h.title}</Table.Td>
                    <Table.Td ta="right" className="num">
                      {h.ok + h.errors} вызовов
                    </Table.Td>
                    <Table.Td ta="right">
                      <Status tone={h.error_rate > 0.2 ? 'bad' : h.error_rate > 0.05 ? 'warn' : 'ok'} size="sm">
                        ошибок {share(h.error_rate, 0)}
                      </Status>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Plate>
        </Grid.Col>
      </Grid>
    </Box>
  );
}
