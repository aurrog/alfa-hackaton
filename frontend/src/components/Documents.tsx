import { ActionIcon, Box, Group, List, SimpleGrid, Stack, Text, Tooltip } from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import { IconCheck, IconDownload, IconFile, IconPaperclip, IconTrash, IconX } from '@tabler/icons-react';
import { useState } from 'react';
import { BarChart } from './MiniBars';
import { Money, Plate, Tag } from './ui';
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
      <Dropzone onDrop={drop} loading={busy} maxSize={10 * 1024 * 1024} accept={docType === 'bank_statement' ? undefined : ACCEPT} onReject={() => setError('Файл не подходит: проверьте формат и размер (до 10 МБ)')} p={compact ? 12 : 22}>
        <Group justify={compact ? 'flex-start' : 'center'} gap="sm" wrap="nowrap" style={{ pointerEvents: 'none' }}>
          <Dropzone.Accept>
            <IconCheck size={20} />
          </Dropzone.Accept>
          <Dropzone.Reject>
            <IconX size={20} />
          </Dropzone.Reject>
          <Dropzone.Idle>
            <IconPaperclip size={20} color="var(--muted)" />
          </Dropzone.Idle>
          <Box style={{ minWidth: 0 }}>
            <Text size="sm" fw={500}>
              {compact ? (label ?? 'Прикрепить файл') : 'Перетащите файл или нажмите, чтобы выбрать'}
            </Text>
            {!compact && (
              <Text size="xs" c="dimmed">
                {docType === 'bank_statement' ? 'Выгрузка из 1С (kl_to_1c.txt) или CSV — выручку посчитаем автоматически' : 'PDF, JPG, PNG, DOCX, XLSX до 10 МБ'}
              </Text>
            )}
          </Box>
        </Group>
      </Dropzone>
      {error && (
        <Text size="xs" c="bad" mt={4}>
          {error}
        </Text>
      )}
    </Box>
  );
}

export function DocumentsList({ appId, docs, onDeleted, canDelete, bank }: { appId: string; docs: DocumentInfo[]; onDeleted?: (app: Application) => void; canDelete?: boolean; bank?: boolean }) {
  if (!docs.length)
    return (
      <Text size="sm" c="dimmed">
        Документы не загружены
      </Text>
    );
  return (
    <div className="rows">
      {docs.map((d) => (
        <Group key={d.id} justify="space-between" wrap="nowrap" py={10} gap="sm">
          <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
            <IconFile size={20} color={d.status === 'rejected' ? 'var(--bad)' : d.status === 'accepted' ? 'var(--ok)' : 'var(--muted)'} style={{ flex: 'none' }} />
            <Box style={{ minWidth: 0 }}>
              <Text size="sm" fw={500} truncate>
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
              <ActionIcon onClick={() => api.download(bank ? `/api/v1/bank/documents/${d.id}/file` : `/api/v1/applications/${appId}/documents/${d.id}/file`, d.file_name)} aria-label="Скачать">
                <IconDownload size={17} />
              </ActionIcon>
            </Tooltip>
            {canDelete && onDeleted && (
              <Tooltip label="Удалить">
                <ActionIcon color="bad" aria-label="Удалить" onClick={async () => onDeleted(await api.del<Application>(`/api/v1/applications/${appId}/documents/${d.id}`))}>
                  <IconTrash size={17} />
                </ActionIcon>
              </Tooltip>
            )}
          </Group>
        </Group>
      ))}
    </div>
  );
}

/** Аналитика разобранной выписки: что система посчитала вместо клиента. */
export function StatementCard({ st }: { st: StatementInfo }) {
  return (
    <Plate size="sm">
      <Stack gap="md">
        <Group gap={8} wrap="wrap">
          <Tag tone="ok" icon={<IconCheck size={12} />}>
            Выписка разобрана
          </Tag>
          <Text size="xs" c="dimmed">
            {st.format === '1c' ? 'формат 1С' : 'CSV'} · {shortDate(st.period.from)} — {shortDate(st.period.to)} · операций: {num(st.operations)}
          </Text>
        </Group>
        <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
          <Box>
            <Text size="xs" c="dimmed">
              Поступления в месяц
            </Text>
            <Money value={st.avg_monthly_incoming} size={18} />
          </Box>
          <Box>
            <Text size="xs" c="dimmed">
              Выручка за год, оценка
            </Text>
            <Money value={st.annualized_revenue} size={18} />
          </Box>
          <Box>
            <Text size="xs" c="dimmed">
              Колебания по месяцам
            </Text>
            <Text fw={700} className="display">
              {st.turnover_volatility != null ? share(st.turnover_volatility, 0) : '—'}
            </Text>
          </Box>
          <Box>
            <Text size="xs" c="dimmed">
              Платежи по кредитам
            </Text>
            <Text fw={700} className="display num">
              {money(st.debt_payments_monthly)}/мес
            </Text>
          </Box>
        </SimpleGrid>
        <BarChart data={st.months.map((m) => ({ label: m.month.slice(5), value: m.incoming }))} />
        <Text size="xs" c="dimmed">
          Исключено из выручки: переводы между своими счетами {money(st.own_transfers_excluded)}, поступления кредитов {money(st.loan_proceeds_excluded)}.
          {st.top_payer_share != null && ` Крупнейший покупатель — ${share(st.top_payer_share, 0)} поступлений (${st.payers_count} плательщиков).`}
        </Text>
        {st.warnings.length > 0 && (
          <Plate tone="warn" size="sm">
            <List size="xs" spacing={2}>
              {st.warnings.map((w) => (
                <List.Item key={w}>{w}</List.Item>
              ))}
            </List>
          </Plate>
        )}
      </Stack>
    </Plate>
  );
}
