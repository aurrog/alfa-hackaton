import { Alert, Badge, Box, Card, Group, Stack, Text, ThemeIcon, Title, Tooltip, type BadgeProps } from '@mantine/core';
import { IconDatabase, IconInfoCircle, IconLoader2 } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { WAITING_COLOR, WAITING_TITLE } from '../theme';
import { dateTime, slaLeft } from '../lib/format';
import { TONE } from '../lib/labels';

export function PageHeader({ title, subtitle, right, eyebrow }: { title: ReactNode; subtitle?: ReactNode; right?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <Group justify="space-between" align="flex-end" mb="lg" wrap="wrap" gap="sm">
      <Box>
        {eyebrow && (
          <Text size="xs" tt="uppercase" fw={600} c="dimmed" mb={4} style={{ letterSpacing: 0.6 }}>
            {eyebrow}
          </Text>
        )}
        <Title order={1}>{title}</Title>
        {subtitle && (
          <Text c="dimmed" mt={6} maw={760}>
            {subtitle}
          </Text>
        )}
      </Box>
      {right}
    </Group>
  );
}

export function StatusBadge({ label, tone, size = 'md', pulse }: { label: string; tone: string; size?: BadgeProps['size']; pulse?: boolean }) {
  return (
    <Badge color={TONE[tone] ?? tone} size={size} variant="light" className={pulse ? 'pulse' : undefined}>
      {label}
    </Badge>
  );
}

export function WaitingChip({ waiting, due }: { waiting: string; due?: string | null }) {
  const sla = waiting !== 'none' ? slaLeft(due) : null;
  return (
    <Group gap={6} wrap="nowrap">
      <Badge color={WAITING_COLOR[waiting] ?? 'gray'} variant="dot" size="md">
        {WAITING_TITLE[waiting] ?? waiting}
      </Badge>
      {sla && waiting === 'bank' && (
        <Text size="xs" c={sla.overdue ? 'signal' : 'dimmed'}>
          норматив: {sla.text}
        </Text>
      )}
    </Group>
  );
}

/** Метка «откуда взялись данные» у автозаполненного поля. */
export function SourceMark({ source }: { source?: { source: string; at?: string; edited?: boolean } }) {
  if (!source) return null;
  return (
    <Tooltip label={`${source.edited ? 'Изменено вами. Исходно: ' : 'Заполнено автоматически: '}${source.source}${source.at ? ` · ${dateTime(source.at)}` : ''}`}>
      <Badge size="xs" variant={source.edited ? 'outline' : 'light'} color={source.edited ? 'gray' : 'route'} leftSection={<IconDatabase size={10} />}>
        {source.edited ? 'изменено' : source.source.length > 26 ? `${source.source.slice(0, 24)}…` : source.source}
      </Badge>
    </Tooltip>
  );
}

export function KV({ items, cols = 2 }: { items: [ReactNode, ReactNode][]; cols?: number }) {
  return (
    <Box style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, gap: '12px 24px' }}>
      {items.map(([k, v], i) => (
        <Box key={i}>
          <Text size="xs" c="dimmed">
            {k}
          </Text>
          <Text size="sm" fw={500} style={{ wordBreak: 'break-word' }}>
            {v ?? '—'}
          </Text>
        </Box>
      ))}
    </Box>
  );
}

export function Section({ title, children, right, ...rest }: { title?: ReactNode; children: ReactNode; right?: ReactNode } & Record<string, unknown>) {
  return (
    <Card {...rest}>
      {(title || right) && (
        <Group justify="space-between" mb="md" wrap="nowrap">
          {title && <Title order={3}>{title}</Title>}
          {right}
        </Group>
      )}
      {children}
    </Card>
  );
}

export function Empty({ title, text, icon, action }: { title: string; text?: ReactNode; icon?: ReactNode; action?: ReactNode }) {
  return (
    <Stack align="center" gap="xs" py="xl">
      <ThemeIcon size={48} radius="xl" variant="light" color="gray">
        {icon ?? <IconInfoCircle />}
      </ThemeIcon>
      <Text fw={600}>{title}</Text>
      {text && (
        <Text c="dimmed" size="sm" ta="center" maw={420}>
          {text}
        </Text>
      )}
      {action}
    </Stack>
  );
}

export function Loading({ text = 'Загружаем…' }: { text?: string }) {
  return (
    <Group justify="center" py="xl" c="dimmed">
      <IconLoader2 className="pulse" />
      <Text c="dimmed">{text}</Text>
    </Group>
  );
}

export function ErrorAlert({ error, title = 'Не удалось загрузить данные' }: { error: unknown; title?: string }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <Alert color="signal" title={title} variant="light">
      {msg}
    </Alert>
  );
}

export function Stat({ label, value, hint, color }: { label: ReactNode; value: ReactNode; hint?: ReactNode; color?: string }) {
  return (
    <Card padding="md">
      <Text size="xs" c="dimmed" fw={500}>
        {label}
      </Text>
      <Text fz={26} fw={700} className="num" c={color} ff="Unbounded, Onest, sans-serif" mt={4}>
        {value}
      </Text>
      {hint && (
        <Text size="xs" c="dimmed" mt={2}>
          {hint}
        </Text>
      )}
    </Card>
  );
}
