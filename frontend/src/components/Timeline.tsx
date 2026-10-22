import { Text, Timeline as MTimeline } from '@mantine/core';
import { dateTime } from '../lib/format';

interface Ev {
  id: number;
  kind: string;
  title: string;
  details?: string | null;
  actor_type: string;
  actor_name?: string | null;
  created_at: string;
  visibility?: string;
}

const COLOR: Record<string, string> = { client: 'warn', bank: 'info', system: 'ink' };
const WHO: Record<string, string> = { client: 'вы', bank: 'банк', system: 'система' };

/** История заявки: кто и что сделал. Цвет точки — сторона: клиент, банк, система. */
export function Timeline({ events, newestFirst = true, limit, bank }: { events: Ev[]; newestFirst?: boolean; limit?: number; bank?: boolean }) {
  let list = newestFirst ? [...events].reverse() : events;
  if (limit) list = list.slice(0, limit);
  return (
    <MTimeline bulletSize={10} lineWidth={1} active={-1} styles={{ itemBullet: { borderWidth: 0 } }}>
      {list.map((e) => (
        <MTimeline.Item
          key={e.id}
          bullet={<span style={{ width: 10, height: 10, borderRadius: 5, background: `var(--mantine-color-${COLOR[e.actor_type] ?? 'ink'}-6)` }} />}
          title={
            <Text size="sm" fw={500} lh={1.35}>
              {e.title}
            </Text>
          }
        >
          {e.details && (
            <Text size="xs" c="dimmed" style={{ whiteSpace: 'pre-wrap' }} mt={2}>
              {e.details.length > 400 ? `${e.details.slice(0, 400)}…` : e.details}
            </Text>
          )}
          <Text size="xs" c="dimmed" mt={2}>
            {dateTime(e.created_at)}
            {e.actor_name ? ` · ${e.actor_name}` : !bank && WHO[e.actor_type] ? ` · ${WHO[e.actor_type]}` : ''}
            {e.visibility === 'bank' ? ' · видно только банку' : ''}
          </Text>
        </MTimeline.Item>
      ))}
    </MTimeline>
  );
}
