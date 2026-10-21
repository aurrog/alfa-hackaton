import { Alert, Badge, Box, Button, Card, Code, Grid, Group, NumberInput, ScrollArea, SimpleGrid, Stack, Table, Text, Textarea, TextInput, Title } from '@mantine/core';
import { IconRefresh } from '@tabler/icons-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, errorText } from '../../api/client';
import { useAuth } from '../../auth/AuthContext';
import { ErrorAlert, Loading, PageHeader, Section, Stat } from '../../components/ui';
import { dateTime, num } from '../../lib/format';

/* eslint-disable @typescript-eslint/no-explicit-any */
type Any = Record<string, any>;

export function PolicyPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ['policy'], queryFn: () => api.get<Any>('/api/v1/bank/policy') });
  const [values, setValues] = useState<Record<string, number | string>>({});
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<number | null>(null);
  useEffect(() => {
    if (q.data) setValues(Object.fromEntries(q.data.editable.map((e: Any) => [e.key, e.value])));
  }, [q.data]);
  const save = useMutation({
    mutationFn: () => {
      const changes: Record<string, number> = {};
      q.data!.editable.forEach((e: Any) => {
        if (Number(values[e.key]) !== Number(e.value)) changes[e.key] = Number(values[e.key]);
      });
      return api.post<Any>('/api/v1/bank/policy', { changes, comment });
    },
    onSuccess: (p) => {
      qc.setQueryData(['policy'], p);
      setComment('');
      setError(null);
      setSaved(p.version);
      void qc.invalidateQueries({ queryKey: ['products'] });
    },
    onError: (e) => setError(errorText(e)),
  });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const p = q.data!;
  const canEdit = user?.bank_role === 'admin' || user?.bank_role === 'risk_manager';
  const changed = p.editable.filter((e: Any) => Number(values[e.key]) !== Number(e.value));
  return (
    <Stack gap="lg">
      <PageHeader
        eyebrow="Управление без релиза"
        title={`Кредитная политика · версия ${p.version}`}
        subtitle="Параметры решения хранятся версиями. Новая версия применяется к следующим решениям сразу; каждое решение ссылается на версию политики и модели — его можно воспроизвести."
      />
      {saved && (
        <Alert color="lime" variant="light" withCloseButton onClose={() => setSaved(null)}>
          Создана версия {saved}. Ставки в каталоге и новые решения уже используют её.
        </Alert>
      )}
      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Section title="Параметры">
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              {p.editable.map((e: Any) => (
                <NumberInput
                  key={e.key}
                  label={e.title}
                  value={values[e.key]}
                  onChange={(v) => setValues((s) => ({ ...s, [e.key]: v }))}
                  min={e.min}
                  max={e.max}
                  step={e.step}
                  decimalScale={e.type === 'money' || e.type === 'int' ? 0 : 2}
                  disabled={!canEdit}
                  styles={Number(values[e.key]) !== Number(e.value) ? { input: { borderColor: 'var(--mantine-color-amber-5)' } } : undefined}
                />
              ))}
            </SimpleGrid>
            {canEdit ? (
              <Stack mt="lg">
                <Textarea label="Обоснование изменения" placeholder="Например: Банк России снизил ключевую ставку" value={comment} onChange={(e) => setComment(e.currentTarget.value)} autosize minRows={2} />
                {error && <Alert color="signal" variant="light">{error}</Alert>}
                <Group justify="flex-end">
                  <Text size="sm" c="dimmed">
                    Изменено параметров: {changed.length}
                  </Text>
                  <Button disabled={!changed.length || comment.trim().length < 5} loading={save.isPending} onClick={() => save.mutate()}>
                    Создать версию {p.version + 1}
                  </Button>
                </Group>
              </Stack>
            ) : (
              <Text size="sm" c="dimmed" mt="md">
                Изменять политику могут владелец продукта и риск-менеджер.
              </Text>
            )}
          </Section>
          <Section title="Полная конфигурация" mt="lg">
            <Code block mah={320} style={{ overflow: 'auto' }}>
              {JSON.stringify(p.config, null, 2)}
            </Code>
          </Section>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Section title="История версий">
            <Stack gap="sm">
              {p.history.map((h: Any) => (
                <Box key={h.version}>
                  <Group gap={6}>
                    <Text fw={700}>v{h.version}</Text>
                    {h.is_active && <Badge color="lime">действует</Badge>}
                  </Group>
                  <Text size="sm">{h.comment}</Text>
                  <Text size="xs" c="dimmed">
                    {h.created_by ?? 'система'} · {dateTime(h.created_at)}
                  </Text>
                </Box>
              ))}
            </Stack>
          </Section>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}

export function AuditPage() {
  const [action, setAction] = useState('');
  const q = useQuery({ queryKey: ['audit', action], queryFn: () => api.get<{ items: Any[] }>('/api/v1/bank/audit', { action, limit: 200 }), refetchInterval: 10000 });
  return (
    <Stack gap="lg">
      <PageHeader eyebrow="Безопасность" title="Журнал аудита" subtitle="Входы, просмотры досье, решения, подписи, скачивание документов, изменения политики — с IP и идентификатором запроса." />
      <Card padding="md">
        <TextInput placeholder="Фильтр по действию: auth, dossier, bank, policy, document…" value={action} onChange={(e) => setAction(e.currentTarget.value)} maw={420} />
      </Card>
      <Card padding={0}>
        {q.isLoading ? (
          <Loading />
        ) : (
          <ScrollArea>
            <Table fz="sm" verticalSpacing={6} miw={900} striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Время</Table.Th>
                  <Table.Th>Действие</Table.Th>
                  <Table.Th>Кто</Table.Th>
                  <Table.Th>Объект</Table.Th>
                  <Table.Th>IP</Table.Th>
                  <Table.Th>Детали</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {q.data?.items.map((r) => (
                  <Table.Tr key={r.id}>
                    <Table.Td>{dateTime(r.created_at)}</Table.Td>
                    <Table.Td>
                      <Badge variant="light" color={r.action.includes('failed') ? 'signal' : r.action.startsWith('bank') || r.action.startsWith('policy') ? 'violet' : 'gray'}>
                        {r.action}
                      </Badge>
                    </Table.Td>
                    <Table.Td>{r.actor_email ?? '—'}</Table.Td>
                    <Table.Td>
                      {r.entity_type === 'application' ? <Link to={`/bank/applications/${r.entity_id}`}>заявка</Link> : r.entity_type ?? '—'}
                    </Table.Td>
                    <Table.Td>{r.ip ?? '—'}</Table.Td>
                    <Table.Td>
                      <Text size="xs" className="mono" lineClamp={2} maw={360}>
                        {r.details ? JSON.stringify(r.details) : ''}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        )}
      </Card>
    </Stack>
  );
}

export function SystemPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ['system'], queryFn: () => api.get<Any>('/api/v1/bank/system'), refetchInterval: 3000 });
  const retry = useMutation({ mutationFn: (id: number) => api.post(`/api/v1/bank/jobs/${id}/retry`), onSuccess: () => qc.invalidateQueries({ queryKey: ['system'] }) });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const s = q.data!;
  const st = s.jobs_by_status;
  const jobsTable = (rows: Any[], withRetry: boolean) => (
    <ScrollArea>
      <Table fz="xs" verticalSpacing={4} miw={700}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>#</Table.Th>
            <Table.Th>Задача</Table.Th>
            <Table.Th>Заявка</Table.Th>
            <Table.Th>Попытки</Table.Th>
            <Table.Th>Ошибка</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((j) => (
            <Table.Tr key={j.id}>
              <Table.Td>{j.id}</Table.Td>
              <Table.Td>{j.kind}</Table.Td>
              <Table.Td>{j.application_id ? <Link to={`/bank/applications/${j.application_id}`}>открыть</Link> : '—'}</Table.Td>
              <Table.Td>
                {j.attempts}/{j.max_attempts}
              </Table.Td>
              <Table.Td>
                <Text size="xs" lineClamp={2} maw={380}>
                  {j.last_error}
                </Text>
              </Table.Td>
              <Table.Td>
                {withRetry && (
                  <Button size="compact-xs" variant="light" leftSection={<IconRefresh size={12} />} onClick={() => retry.mutate(j.id)}>
                    Повторить
                  </Button>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </ScrollArea>
  );
  return (
    <Stack gap="lg">
      <PageHeader
        eyebrow="Надёжность"
        title="Мониторинг конвейера"
        subtitle="Очередь задач в PostgreSQL: повторы с паузой, «мёртвые письма» после исчерпания попыток, возврат зависших задач по истечении аренды. Метрики Prometheus — /metrics."
      />
      <SimpleGrid cols={{ base: 2, md: 5 }}>
        <Stat label="В очереди" value={num(st.queued ?? 0)} />
        <Stat label="Выполняются" value={num(st.running ?? 0)} color="route" />
        <Stat label="Выполнено" value={num(st.done ?? 0)} color="lime.8" />
        <Stat label="Неуспешные" value={num(st.failed ?? 0)} color={st.failed ? 'signal' : undefined} />
        <Stat label="Задержка очереди" value={`${num(s.queue_lag_sec, 1)} с`} hint="самая старая задача" />
      </SimpleGrid>
      <Section title="Повторы (временные сбои источников)">{s.retrying.length ? jobsTable(s.retrying, false) : <Text size="sm" c="dimmed">Сейчас нет задач на повторе.</Text>}</Section>
      <Section title="Неуспешные задачи (dead letter)">{s.failed.length ? jobsTable(s.failed, true) : <Text size="sm" c="dimmed">Неуспешных задач нет.</Text>}</Section>
      <Section title="Задачи по типам">
        <Table fz="sm">
          <Table.Tbody>
            {s.jobs_by_kind.map((r: Any) => (
              <Table.Tr key={r.kind + r.status}>
                <Table.Td>{r.kind}</Table.Td>
                <Table.Td>{r.status}</Table.Td>
                <Table.Td ta="right">{r.count}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Title order={4} mt="md">
          Симулятор сбоев
        </Title>
        <Text size="sm" c="dimmed">
          Включить отказ источника: <Code>curl -X POST localhost:8081/admin/faults -H 'Content-Type: application/json' -d {`'{"inn":"*","source":"bki_company","mode":"outage","seconds":60}'`}</Code>
        </Text>
      </Section>
    </Stack>
  );
}
