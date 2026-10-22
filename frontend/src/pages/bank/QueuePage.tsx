import { Box, Group, ScrollArea, SegmentedControl, Select, Table, Text, TextInput, Tooltip } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconSearch } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { QueueItem } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { Empty, GradeChip, Loading, PageTitle, Status, StatusBadge } from '../../components/ui';
import { fromNow, millions, months, slaLeft } from '../../lib/format';
import { LEVELS, OUTCOME } from '../../lib/labels';

const SLA_TONE = { ok: 'ok', warning: 'warn', breached: 'bad', none: '' } as const;

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
    <Box>
      <PageTitle title="Очередь заявок" sub="Заявки, которым нужно решение специалиста или кредитного комитета. Сверху — те, у кого раньше истекает норматив." />
      <Group justify="space-between" wrap="wrap" gap="sm" mb="lg">
        <ScrollArea type="never" maw="100%">
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
        </ScrollArea>
        <Group gap="sm">
          <Select placeholder="Исполнитель" clearable value={assigned} onChange={setAssigned} data={[{ value: 'me', label: 'Мои' }, { value: 'unassigned', label: 'Не назначены' }]} w={170} />
          <TextInput placeholder="Номер, компания, ИНН" leftSection={<IconSearch size={16} />} value={search} onChange={(e) => setSearch(e.currentTarget.value)} w={250} />
        </Group>
      </Group>
      {q.isLoading && <Loading />}
      {q.data && !q.data.items.length && <Empty title="Очередь пуста" text="Новые заявки появятся здесь автоматически." />}
      {!!q.data?.items.length && (
        <ScrollArea>
          <Table highlightOnHover miw={1080} verticalSpacing={12}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Заявка</Table.Th>
                <Table.Th>Клиент</Table.Th>
                <Table.Th ta="right">Сумма</Table.Th>
                <Table.Th ta="center">Грейд</Table.Th>
                <Table.Th>Рекомендация</Table.Th>
                <Table.Th>Уровень</Table.Th>
                <Table.Th>Норматив</Table.Th>
                <Table.Th>Исполнитель</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {q.data.items.map((a) => {
                const sla = slaLeft(a.sla_due_at);
                const rec = a.recommendation ? OUTCOME[a.recommendation] : null;
                return (
                  <Table.Tr key={a.id} style={{ cursor: 'pointer' }} onClick={() => nav(`/bank/applications/${a.id}`)}>
                    <Table.Td>
                      <Text fw={600} size="sm" className="num">
                        {a.number}
                      </Text>
                      <StatusBadge label={a.status_label} tone={a.status_tone} size="sm" />
                    </Table.Td>
                    <Table.Td maw={320}>
                      <Text size="sm" fw={600} truncate>
                        {a.company_name}
                      </Text>
                      <Text size="xs" c="dimmed" truncate>
                        ИНН {a.inn} · {a.product_name}
                      </Text>
                      {a.manual_reasons.length > 0 && (
                        <Tooltip label={a.manual_reasons.join('\n')} style={{ whiteSpace: 'pre-line' }}>
                          <Text size="xs" c="var(--info)" truncate>
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
                    <Table.Td ta="center">
                      <GradeChip grade={a.risk_grade} />
                    </Table.Td>
                    <Table.Td>{rec ? <Status tone={rec.color} size="sm">{rec.short}</Status> : <Text c="dimmed">—</Text>}</Table.Td>
                    <Table.Td>
                      <Text size="sm">{a.review_level ? LEVELS[a.review_level] : '—'}</Text>
                    </Table.Td>
                    <Table.Td>
                      {sla ? (
                        <Status tone={SLA_TONE[a.sla_state]} size="sm">
                          {sla.text}
                        </Status>
                      ) : (
                        <Text size="xs" c="dimmed">
                          подана {fromNow(a.submitted_at)}
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c={a.assigned_name ? undefined : 'dimmed'}>
                        {a.assigned_name ?? 'не назначен'}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </ScrollArea>
      )}
    </Box>
  );
}
