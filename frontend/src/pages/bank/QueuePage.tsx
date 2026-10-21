import { Badge, Box, Card, Group, ScrollArea, SegmentedControl, Select, Stack, Table, Text, TextInput, Tooltip } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconSearch } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { QueueItem } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { Empty, Loading, PageHeader, StatusBadge } from '../../components/ui';
import { fromNow, millions, months, slaLeft } from '../../lib/format';
import { GRADE_COLOR, LEVELS, OUTCOME } from '../../lib/labels';

const SLA_COLOR = { ok: 'lime', warning: 'amber', breached: 'signal', none: 'gray' } as const;

export function QueuePage() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [status, setStatus] = useState(user?.bank_role === 'risk_manager' ? 'committee_review' : 'active');
  const [assigned, setAssigned] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [debounced] = useDebouncedValue(search, 300);
  const q = useQuery({
    queryKey: ['queue', status, assigned, debounced],
    queryFn: () => api.get<{ items: QueueItem[]; counts: Record<string, number> }>('/api/v1/bank/queue', { status, assigned, search: debounced }),
    refetchInterval: 5000,
  });
  const c = q.data?.counts ?? {};
  return (
    <Stack>
      <PageHeader
        eyebrow="Рабочее место банка"
        title="Очередь заявок"
        subtitle="Заявки, которые требуют решения специалиста или кредитного комитета. Сортировка — по нормативу рассмотрения."
      />
      <Card padding="md">
        <Group justify="space-between" wrap="wrap" gap="sm">
          <SegmentedControl
            value={status}
            onChange={setStatus}
            data={[
              { value: 'active', label: `На рассмотрении · ${(c.manual_review ?? 0) + (c.committee_review ?? 0)}` },
              { value: 'manual_review', label: `Аналитик · ${c.manual_review ?? 0}` },
              { value: 'committee_review', label: `Комитет · ${c.committee_review ?? 0}` },
              { value: 'pipeline', label: 'В конвейере' },
              { value: 'all', label: 'Все' },
            ]}
          />
          <Group gap="sm">
            <Select placeholder="Исполнитель" clearable value={assigned} onChange={setAssigned} data={[{ value: 'me', label: 'Мои' }, { value: 'unassigned', label: 'Не назначены' }]} w={170} />
            <TextInput placeholder="Номер, компания, ИНН" leftSection={<IconSearch size={16} />} value={search} onChange={(e) => setSearch(e.currentTarget.value)} w={240} />
          </Group>
        </Group>
      </Card>
      <Card padding={0}>
        {q.isLoading && <Loading />}
        {q.data && !q.data.items.length && <Empty title="Очередь пуста" text="Новые заявки появятся здесь автоматически." />}
        {!!q.data?.items.length && (
          <ScrollArea>
            <Table highlightOnHover verticalSpacing="sm" horizontalSpacing="md" miw={1050}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Заявка</Table.Th>
                  <Table.Th>Клиент</Table.Th>
                  <Table.Th ta="right">Сумма</Table.Th>
                  <Table.Th>Грейд</Table.Th>
                  <Table.Th>Рекомендация</Table.Th>
                  <Table.Th>Уровень</Table.Th>
                  <Table.Th>Норматив</Table.Th>
                  <Table.Th>Исполнитель</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {q.data.items.map((a) => {
                  const sla = slaLeft(a.sla_due_at);
                  return (
                    <Table.Tr key={a.id} style={{ cursor: 'pointer' }} onClick={() => nav(`/bank/applications/${a.id}`)}>
                      <Table.Td>
                        <Text fw={700} size="sm">
                          {a.number}
                        </Text>
                        <StatusBadge label={a.status_label} tone={a.status_tone} size="xs" />
                      </Table.Td>
                      <Table.Td maw={280}>
                        <Text size="sm" fw={600} truncate>
                          {a.company_name}
                        </Text>
                        <Text size="xs" c="dimmed">
                          ИНН {a.inn} · {a.product_name}
                        </Text>
                        {a.manual_reasons.length > 0 && (
                          <Tooltip label={a.manual_reasons.join('\n')} style={{ whiteSpace: 'pre-line' }}>
                            <Text size="xs" c="violet" truncate>
                              {a.manual_reasons[0]}
                              {a.manual_reasons.length > 1 ? ` (+${a.manual_reasons.length - 1})` : ''}
                            </Text>
                          </Tooltip>
                        )}
                      </Table.Td>
                      <Table.Td ta="right">
                        <Text size="sm" fw={600} className="num">
                          {millions(a.amount)}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {months(a.term_months)}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        {a.risk_grade ? (
                          <Badge color={GRADE_COLOR[a.risk_grade]} variant="filled" size="lg" w={36}>
                            {a.risk_grade}
                          </Badge>
                        ) : (
                          '—'
                        )}
                      </Table.Td>
                      <Table.Td>{a.recommendation ? <Badge color={OUTCOME[a.recommendation]?.color}>{OUTCOME[a.recommendation]?.title ?? a.recommendation}</Badge> : '—'}</Table.Td>
                      <Table.Td>
                        <Text size="sm">{a.review_level ? LEVELS[a.review_level] : '—'}</Text>
                      </Table.Td>
                      <Table.Td>
                        {sla ? (
                          <Badge color={SLA_COLOR[a.sla_state]} variant={a.sla_state === 'breached' ? 'filled' : 'light'}>
                            {sla.text}
                          </Badge>
                        ) : (
                          <Text size="xs" c="dimmed">
                            подана {fromNow(a.submitted_at)}
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td>
                        <Box>
                          <Text size="sm">{a.assigned_name ?? '—'}</Text>
                        </Box>
                      </Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        )}
      </Card>
    </Stack>
  );
}
