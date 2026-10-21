import { Group, Text, Tooltip } from '@mantine/core';
import type { Stage } from '../api/types';

const STATE_TEXT: Record<Stage['state'], string> = {
  done: 'готово',
  current: 'сейчас',
  upcoming: 'впереди',
  failed: 'остановлено',
  skipped: '—',
};

/** Маршрут заявки: шесть шагов, цвет текущего шага — «чей ход». */
export function RouteMap({ stages, waiting, compact, hint }: { stages: Stage[]; waiting: string; compact?: boolean; hint?: string }) {
  if (compact) {
    return (
      <div className="route compact" aria-label="Маршрут заявки">
        {stages.map((s) => (
          <Tooltip key={s.key} label={`${s.title}: ${STATE_TEXT[s.state]}`}>
            <div className={`route-step ${s.state} ${s.state === 'current' ? waiting : ''}`}>
              <div className="bar" />
            </div>
          </Tooltip>
        ))}
      </div>
    );
  }
  return (
    <div>
      <div className="route" role="list" aria-label="Маршрут заявки">
        {stages.map((s, i) => (
          <div key={s.key} role="listitem" className={`route-step ${s.state} ${s.state === 'current' ? waiting : ''}`}>
            <div className="bar" />
            <div className="title">
              {i + 1}. {s.title}
            </div>
            <div className="state">{STATE_TEXT[s.state]}</div>
          </div>
        ))}
      </div>
      {hint && (
        <Group mt="sm" gap={6}>
          <Text size="sm" c="dimmed">
            {hint}
          </Text>
        </Group>
      )}
    </div>
  );
}
