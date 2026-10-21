import { ActionIcon, Alert, Badge, Box, Group, List, Progress, SimpleGrid, Stack, Text, ThemeIcon, Tooltip } from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import { IconCheck, IconCloudUpload, IconDownload, IconFile, IconTrash, IconX } from '@tabler/icons-react';
import { useState } from 'react';
import { BarChart } from './MiniBars';
import { api, errorText } from '../api/client';
import type { Application, DocumentInfo, StatementInfo } from '../api/types';
import { fileSize, money, num, share, shortDate } from '../lib/format';

const ACCEPT = ['application/pdf', 'image/jpeg', 'image/png', 'text/plain', 'text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/xml', 'text/xml'];

export function DocDropzone({ appId, docType, onUploaded, compact, label }: { appId: string; docType: string; onUploaded: (app: Application) => void; compact?: boolean; label?: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const drop = async (files: File[]) => {
    setBusy(true);
    setError(null);
    try {
      for (const f of files) {
        const fd = new FormData();
        fd.append('doc_type', docType);
        fd.append('file', f);
        const r = await api.upload<{ application: Application }>(`/api/v1/applications/${appId}/documents`, fd);
        onUploaded(r.application);
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Box>
      <Dropzone onDrop={drop} loading={busy} maxSize={10 * 1024 * 1024} accept={docType === 'bank_statement' ? undefined : ACCEPT} onReject={() => setError('Файл не подходит: проверьте формат и размер (до 10 МБ)')} p={compact ? 'xs' : 'md'} radius="md">
        <Group justify="center" gap="sm" mih={compact ? 36 : 70} style={{ pointerEvents: 'none' }}>
          <Dropzone.Accept>
            <IconCheck size={22} />
          </Dropzone.Accept>
          <Dropzone.Reject>
            <IconX size={22} />
          </Dropzone.Reject>
          <Dropzone.Idle>
            <IconCloudUpload size={22} color="var(--mantine-color-route-6)" />
          </Dropzone.Idle>
          <Box>
            <Text size="sm" fw={600}>
              {label ?? 'Перетащите файл или нажмите, чтобы выбрать'}
            </Text>
            {!compact && (
              <Text size="xs" c="dimmed">
                {docType === 'bank_statement' ? 'Выгрузка 1С (kl_to_1c.txt) или CSV — обороты посчитаются автоматически' : 'PDF, JPG, PNG, DOCX, XLSX до 10 МБ'}
              </Text>
            )}
          </Box>
        </Group>
      </Dropzone>
      {error && (
        <Text size="xs" c="signal" mt={4}>
          {error}
        </Text>
      )}
    </Box>
  );
}

export function DocumentsList({ appId, docs, onDeleted, canDelete, bank }: { appId: string; docs: DocumentInfo[]; onDeleted?: (app: Application) => void; canDelete?: boolean; bank?: boolean }) {
  if (!docs.length) return <Text size="sm" c="dimmed">Документы не загружены</Text>;
  return (
    <Stack gap={6}>
      {docs.map((d) => (
        <Group key={d.id} justify="space-between" wrap="nowrap" p={8} style={{ border: '1px solid var(--line)', borderRadius: 10 }}>
          <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
            <ThemeIcon variant="light" color={d.status === 'rejected' ? 'signal' : d.status === 'accepted' ? 'lime' : 'gray'}>
              <IconFile size={16} />
            </ThemeIcon>
            <Box style={{ minWidth: 0 }}>
              <Text size="sm" fw={600} truncate>
                {d.file_name}
              </Text>
              <Text size="xs" c="dimmed">
                {d.doc_title} · {fileSize(d.size_bytes)} · {shortDate(d.created_at)}
                {d.parsed ? ' · разобрана автоматически' : ''}
                {d.status === 'accepted' ? ' · принят банком' : d.status === 'rejected' ? ` · отклонён: ${d.review_comment ?? ''}` : ''}
              </Text>
            </Box>
          </Group>
          <Group gap={2} wrap="nowrap">
            <Tooltip label="Скачать">
              <ActionIcon variant="subtle" onClick={() => api.download(bank ? `/api/v1/bank/documents/${d.id}/file` : `/api/v1/applications/${appId}/documents/${d.id}/file`, d.file_name)} aria-label="Скачать">
                <IconDownload size={16} />
              </ActionIcon>
            </Tooltip>
            {canDelete && onDeleted && (
              <Tooltip label="Удалить">
                <ActionIcon variant="subtle" color="signal" aria-label="Удалить" onClick={async () => onDeleted(await api.del<Application>(`/api/v1/applications/${appId}/documents/${d.id}`))}>
                  <IconTrash size={16} />
                </ActionIcon>
              </Tooltip>
            )}
          </Group>
        </Group>
      ))}
    </Stack>
  );
}

/** Аналитика разобранной выписки: что система посчитала вместо клиента. */
export function StatementCard({ st }: { st: StatementInfo }) {
  return (
    <Stack gap="sm">
      <Group gap={8}>
        <Badge color="lime" leftSection={<IconCheck size={11} />}>
          Выписка разобрана
        </Badge>
        <Text size="xs" c="dimmed">
          {st.format === '1c' ? 'формат 1С' : 'CSV'} · {shortDate(st.period.from)} — {shortDate(st.period.to)} · операций: {num(st.operations)}
        </Text>
      </Group>
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="xs">
        <Box>
          <Text size="xs" c="dimmed">Поступления в месяц</Text>
          <Text fw={700} className="num">{money(st.avg_monthly_incoming)}</Text>
        </Box>
        <Box>
          <Text size="xs" c="dimmed">Выручка за год (оценка)</Text>
          <Text fw={700} className="num">{money(st.annualized_revenue)}</Text>
        </Box>
        <Box>
          <Text size="xs" c="dimmed">Колебания по месяцам</Text>
          <Text fw={700}>{st.turnover_volatility != null ? share(st.turnover_volatility, 0) : '—'}</Text>
        </Box>
        <Box>
          <Text size="xs" c="dimmed">Платежи по кредитам</Text>
          <Text fw={700} className="num">{money(st.debt_payments_monthly)}/мес</Text>
        </Box>
      </SimpleGrid>
      <BarChart data={st.months.map((m) => ({ label: m.month.slice(5), value: m.incoming }))} />
      <Text size="xs" c="dimmed">
        Исключено из выручки: переводы между своими счетами {money(st.own_transfers_excluded)}, поступления кредитов {money(st.loan_proceeds_excluded)}.
        {st.top_payer_share != null && ` Крупнейший покупатель — ${share(st.top_payer_share, 0)} поступлений (${st.payers_count} плательщиков).`}
      </Text>
      {st.warnings.length > 0 && (
        <Alert color="amber" variant="light" p="xs">
          <List size="xs">
            {st.warnings.map((w) => (
              <List.Item key={w}>{w}</List.Item>
            ))}
          </List>
        </Alert>
      )}
      {st.months_covered < 6 && <Progress value={(st.months_covered / 6) * 100} color="amber" />}
    </Stack>
  );
}
