import { Alert, Box, Button, Code, Grid, Group, NumberInput, ScrollArea, SimpleGrid, Stack, Table, Text, Textarea, TextInput, Title } from '@mantine/core';
import { IconRefresh } from '@tabler/icons-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, errorText } from '../../api/client';
import { useAuth } from '../../auth/AuthContext';
import { ErrorAlert, Loading, PageTitle, Plate, Section, Stat, Status, Tag } from '../../components/ui';
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
      <PageTitle
        title={`Кредитная политика · версия ${p.version}`}
        sub="Параметры решения хранятся версиями и меняются без релиза. Новая версия применяется к следующим решениям сразу; каждое решение ссылается на версию политики и модели — его можно воспроизвести."
      />
      {saved && (
        <Alert color="ok" withCloseButton onClose={() => setSaved(null)} mb="lg">
          Создана версия {saved}. Ставки в каталоге и новые решения уже используют её.
        </Alert>
      )}
      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Plate>
            <Title order={3} mb="md">
              Параметры
            </Title>
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
                  variant="default"
                  styles={Number(values[e.key]) !== Number(e.value) ? { input: { borderColor: 'var(--warn)', background: 'var(--warn-soft)' } } : undefined}
                />
              ))}
            </SimpleGrid>
            {canEdit ? (
              <Stack mt="lg">
                <Textarea variant="default" label="Обоснование изменения" placeholder="Например: Банк России снизил ключевую ставку" value={comment} onChange={(e) => setComment(e.currentTarget.value)} autosize minRows={2} />
                {error && <Alert color="bad">{error}</Alert>}
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
          </Plate>
          <Section title="Полная конфигурация" mt={32}>
            <Code block mah={320} style={{ overflow: 'auto', borderRadius: 16 }}>
              {JSON.stringify(p.config, null, 2)}
            </Code>
          </Section>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Section title="История версий">
            <div className="rows">
              {p.history.map((h: Any) => (
                <Box key={h.version} py={10}>
                  <Group gap={8}>
                    <Text fw={700}>v{h.version}</Text>
                    {h.is_active && <Tag tone="ok">действует</Tag>}
                  </Group>
                  <Text size="sm">{h.comment}</Text>
                  <Text size="xs" c="dimmed">
                    {h.created_by ?? 'система'} · {dateTime(h.created_at)}
                  </Text>
                </Box>
              ))}
            </div>
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
      <PageTitle title="Журнал аудита" sub="Входы, просмотры досье, решения, подписи, скачивание документов, изменения политики — с IP и идентификатором запроса." />
      <TextInput placeholder="Фильтр по действию: auth, dossier, bank, policy, document…" value={action} onChange={(e) => setAction(e.currentTarget.value)} maw={420} />
      <Box>
        {q.isLoading ? (
          <Loading />
        ) : (
          <ScrollArea>
            <Table fz="sm" verticalSpacing={8} miw={900}>
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
                      <Tag tone={r.action.includes('failed') ? 'bad' : r.action.startsWith('bank') || r.action.startsWith('policy') ? 'info' : ''}>{r.action}</Tag>
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
      </Box>
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
      <PageTitle
        title="Мониторинг конвейера"
        sub="Очередь задач в PostgreSQL: повторы с паузой, «мёртвые письма» после исчерпания попыток, возврат зависших задач по истечении аренды. Метрики Prometheus — /metrics."
      />
      <SimpleGrid cols={{ base: 2, md: 5 }} className="enter">
        <Stat label="В очереди" value={num(st.queued ?? 0)} />
        <Stat label="Выполняются" value={num(st.running ?? 0)} color="info" />
        <Stat label="Выполнено" value={num(st.done ?? 0)} color="ok" />
        <Stat label="Неуспешные" value={num(st.failed ?? 0)} color={st.failed ? 'bad' : undefined} />
        <Stat label="Задержка очереди" value={`${num(s.queue_lag_sec, 1)} с`} hint="самая старая задача" />
      </SimpleGrid>
      <Section title="Повторы — временные сбои источников" mt={12}>{s.retrying.length ? jobsTable(s.retrying, false) : <Text size="sm" c="dimmed">Сейчас нет задач на повторе.</Text>}</Section>
      <Section title="Неуспешные задачи (dead letter)" mt={12}>{s.failed.length ? jobsTable(s.failed, true) : <Text size="sm" c="dimmed">Неуспешных задач нет.</Text>}</Section>
      <Section title="Задачи по типам" mt={12}>
        <Table fz="sm">
          <Table.Tbody>
            {s.jobs_by_kind.map((r: Any) => (
              <Table.Tr key={r.kind + r.status}>
                <Table.Td>{r.kind}</Table.Td>
                <Table.Td>
                  <Status tone={r.status === 'done' ? 'ok' : r.status === 'failed' ? 'bad' : r.status === 'running' ? 'info' : ''} size="sm">
                    {r.status}
                  </Status>
                </Table.Td>
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
