import { Text, Timeline as MTimeline } from '@mantine/core';
import { IconBuildingBank, IconCpu, IconUser } from '@tabler/icons-react';
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

const ICON: Record<string, JSX.Element> = {
  client: <IconUser size={12} />,
  bank: <IconBuildingBank size={12} />,
  system: <IconCpu size={12} />,
};
const COLOR: Record<string, string> = { client: 'amber', bank: 'violet', system: 'route' };

export function Timeline({ events, newestFirst = true, limit }: { events: Ev[]; newestFirst?: boolean; limit?: number }) {
  let list = newestFirst ? [...events].reverse() : events;
  if (limit) list = list.slice(0, limit);
  return (
    <MTimeline bulletSize={22} lineWidth={2} active={-1}>
      {list.map((e) => (
        <MTimeline.Item key={e.id} bullet={ICON[e.actor_type]} color={COLOR[e.actor_type] ?? 'gray'} title={<Text size="sm" fw={600}>{e.title}</Text>}>
          {e.details && (
            <Text size="xs" c="dimmed" style={{ whiteSpace: 'pre-wrap' }}>
              {e.details.length > 400 ? `${e.details.slice(0, 400)}…` : e.details}
            </Text>
          )}
          <Text size="xs" c="dimmed" mt={2}>
            {dateTime(e.created_at)}
            {e.actor_name ? ` · ${e.actor_name}` : ''}
            {e.visibility === 'bank' ? ' · видно только банку' : ''}
          </Text>
        </MTimeline.Item>
      ))}
    </MTimeline>
  );
}
