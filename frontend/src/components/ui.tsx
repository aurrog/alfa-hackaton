import { Alert, Box, Group, Loader, Stack, Text, Title } from '@mantine/core';
import { IconArrowLeft } from '@tabler/icons-react';
import type { CSSProperties, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { dateTime, num, slaLeft } from '../lib/format';
import { GRADE_HEX, TONE } from '../lib/labels';
import { useTween } from '../lib/motion';
import { WAITING_COLOR, WAITING_TITLE } from '../theme';

/** Заголовок страницы: ссылка назад, заголовок, подзаголовок и место для действий справа. */
export function PageTitle({ title, sub, right, back, top }: { title: ReactNode; sub?: ReactNode; right?: ReactNode; back?: { to: string; label: string }; top?: ReactNode }) {
  return (
    <Box mb={28}>
      {back && <BackLink to={back.to}>{back.label}</BackLink>}
      {top && <Box mt={back ? 18 : 0} mb={14}>{top}</Box>}
      <Group justify="space-between" align="flex-end" wrap="wrap" gap="md" mt={back && !top ? 10 : 0}>
        <Box style={{ minWidth: 0 }}>
          <Title order={1} fz={{ base: 28, sm: 36 }}>
            {title}
          </Title>
          {sub && (
            <Text c="dimmed" mt={8} maw={760} fz={15}>
              {sub}
            </Text>
          )}
        </Box>
        {right}
      </Group>
    </Box>
  );
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--muted)', textDecoration: 'none', fontSize: 14 }}>
      <IconArrowLeft size={16} />
      {children}
    </Link>
  );
}

type Tone = '' | 'ok' | 'warn' | 'bad' | 'info' | 'white';

/** Серая плашка — основной контейнер интерфейса (без рамок и теней). */
export function Plate({ children, tone = '', size, className, style, id }: { children: ReactNode; tone?: Tone; size?: 'sm' | 'lg'; className?: string; style?: CSSProperties; id?: string }) {
  return (
    <div id={id} className={['plate', tone, size, className].filter(Boolean).join(' ')} style={style}>
      {children}
    </div>
  );
}

/** Раздел: заголовок и действие справа, без собственного контейнера. */
export function Section({ title, right, children, mt, sub }: { title: ReactNode; right?: ReactNode; children: ReactNode; mt?: number | string; sub?: ReactNode }) {
  return (
    <Box mt={mt}>
      <Group justify="space-between" align="flex-end" mb={sub ? 4 : 12} wrap="nowrap" gap="sm">
        <Title order={3}>{title}</Title>
        {right}
      </Group>
      {sub && (
        <Text size="sm" c="dimmed" mb={12}>
          {sub}
        </Text>
      )}
      {children}
    </Box>
  );
}

/**
 * Сумма: крупные табличные цифры и уменьшенный знак рубля.
 * animate — плавно докручивать к новому значению, countUp — при первом показе считать от нуля.
 */
export function Money({ value, size = 28, prefix, color, digits = 0, className, animate, countUp }: { value: number | null | undefined; size?: number | string; prefix?: string; color?: string; digits?: number; className?: string; animate?: boolean; countUp?: boolean }) {
  const empty = value === null || value === undefined || Number.isNaN(value);
  const shown = useTween(empty ? 0 : value, countUp ? 900 : animate ? 420 : 0, countUp ? 0 : undefined);
  if (empty) return <span className="money">—</span>;
  return (
    <span className={`money ${className ?? ''}`} style={{ fontSize: size, color }}>
      {prefix && <span className="pre">{prefix}</span>}
      {num(shown, digits)}
      <span className="cur">₽</span>
    </span>
  );
}

/** Статус: цветная точка и текст. tone — warn | info | ok | bad | '' . */
export function Status({ tone = '', children, pulse, size }: { tone?: string; children: ReactNode; pulse?: boolean; size?: 'sm' }) {
  return (
    <span className={['status', tone, size].filter(Boolean).join(' ')}>
      <span className={`dot${pulse ? ' pulse' : ''}`} />
      {children}
    </span>
  );
}

/** Статус заявки по полям status_label/status_tone из API. */
export function StatusBadge({ label, tone, pulse, size }: { label: string; tone: string; pulse?: boolean; size?: 'sm' }) {
  return (
    <Status tone={TONE[tone] ?? ''} pulse={pulse} size={size}>
      {label}
    </Status>
  );
}

/** Чей сейчас ход + сколько осталось до норматива банка. */
export function WaitingChip({ waiting, due }: { waiting: string; due?: string | null }) {
  const sla = waiting === 'bank' ? slaLeft(due) : null;
  return (
    <Group gap={10} wrap="nowrap">
      <Status tone={WAITING_COLOR[waiting] === 'ink' ? '' : WAITING_COLOR[waiting]} pulse={waiting === 'system'} size="sm">
        {WAITING_TITLE[waiting] ?? waiting}
      </Status>
      {sla && (
        <Text size="xs" c={sla.overdue ? 'bad' : 'dimmed'}>
          {sla.text}
        </Text>
      )}
    </Group>
  );
}

export function Tag({ tone = '', children, icon }: { tone?: string; children: ReactNode; icon?: ReactNode }) {
  return (
    <span className={`tag ${tone}`}>
      {icon}
      {children}
    </span>
  );
}

/** Подпись под автозаполненным полем: откуда взялось значение. */
export function SourceNote({ source }: { source?: { source: string; at?: string; edited?: boolean } }) {
  if (!source) return null;
  return (
    <div className="field-source">
      {source.edited ? `Изменено вами · исходно: ${source.source}` : `Заполнено: ${source.source}`}
      {source.at && !source.edited ? ` · ${dateTime(source.at)}` : ''}
    </div>
  );
}

export function KV({ items, cols = 2 }: { items: [ReactNode, ReactNode][]; cols?: number }) {
  return (
    <div className="kv" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
      {items.map(([k, v], i) => (
        <div key={i}>
          <div className="k">{k}</div>
          <div className="v">{v ?? '—'}</div>
        </div>
      ))}
    </div>
  );
}

export function Empty({ title, text, action }: { title: string; text?: ReactNode; action?: ReactNode }) {
  return (
    <Plate>
      <Stack align="flex-start" gap={6} py={6}>
        <Text fw={600} fz={17}>
          {title}
        </Text>
        {text && (
          <Text c="dimmed" size="sm" maw={520}>
            {text}
          </Text>
        )}
        {action && <Box mt={8}>{action}</Box>}
      </Stack>
    </Plate>
  );
}

/** Пока данные грузятся — мерцающие заготовки блоков (подпись видна только экранному диктору). */
export function Loading({ text = 'Загружаем…', compact }: { text?: string; compact?: boolean }) {
  return (
    <Stack gap={12} py={compact ? 0 : 8} aria-busy="true" aria-label={text}>
      {!compact && <div className="skel" style={{ height: 34, width: '38%', borderRadius: 10 }} />}
      <div className="skel" style={{ height: compact ? 120 : 200, borderRadius: 20 }} />
      <div className="skel" style={{ height: 88, width: '72%', borderRadius: 20 }} />
    </Stack>
  );
}

/** Маленький индикатор загрузки внутри строки. */
export function InlineLoading({ text }: { text: string }) {
  return (
    <Group gap="sm" py="md">
      <Loader size="xs" color="ink" type="dots" />
      <Text c="dimmed" size="sm">
        {text}
      </Text>
    </Group>
  );
}

export function ErrorAlert({ error, title = 'Не удалось загрузить данные' }: { error: unknown; title?: string }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <Alert color="bad" title={title}>
      {msg}
    </Alert>
  );
}

/** Показатель: подпись, крупное значение, пояснение. */
export function Stat({ label, value, hint, color }: { label: ReactNode; value: ReactNode; hint?: ReactNode; color?: string }) {
  return (
    <Plate size="sm">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text fz={26} fw={700} className="num display" c={color} mt={6} lh={1.1}>
        {value}
      </Text>
      {hint && (
        <Text size="xs" c="dimmed" mt={6}>
          {hint}
        </Text>
      )}
    </Plate>
  );
}

/** «Шаг 2 из 3 · Данные» и полоса шагов оформления. */
export function Steps({ current, titles }: { current: number; titles: string[] }) {
  return (
    <Box maw={360} w="100%">
      <Text size="sm" c="dimmed">
        Шаг {current + 1} из {titles.length} · <Text span c="var(--ink)" fw={600}>{titles[current]}</Text>
      </Text>
      <div className="steps">
        {titles.map((t, i) => (
          <i key={t} className={i <= current ? 'on' : undefined} />
        ))}
      </div>
    </Box>
  );
}

/** Грейд риска: квадрат с буквой (A — зелёный … E — красный). */
export function GradeChip({ grade, size = 28 }: { grade?: string | null; size?: number }) {
  if (!grade) return <Text c="dimmed">—</Text>;
  return (
    <span
      className="display"
      style={{ display: 'inline-grid', placeItems: 'center', width: size, height: size, borderRadius: 8, background: GRADE_HEX[grade] ?? 'var(--muted)', color: '#fff', fontWeight: 700, fontSize: size * 0.5 }}
    >
      {grade}
    </span>
  );
}

