import type { CSSProperties } from 'react';
import type { Stage } from '../api/types';

/**
 * Маршрут заявки как трекер доставки: сегменты этапов, текущий окрашен по тому, чей ход
 * (оранжевый — клиент, синий — банк, синие полосы в движении — работает автоматика).
 */
export function RouteMap({ stages, waiting, compact }: { stages: Stage[]; waiting: string; compact?: boolean }) {
  const style = { '--n': stages.length } as CSSProperties;
  return (
    <div>
      <div className={`track${compact ? ' thin' : ''}`} style={style} aria-label="Маршрут заявки">
        {stages.map((s, i) => (
          <div key={s.key} className={`seg ${s.state} ${s.state === 'current' ? waiting : ''}`} title={s.title} style={{ '--i': i } as CSSProperties} />
        ))}
      </div>
      {!compact && (
        <div className="track-labels" style={style}>
          {stages.map((s) => (
            <span key={s.key} className={s.state}>
              {s.title}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/** Текущий этап для мобильной подписи: «Этап 3 из 6 · Оценка». */
export function currentStage(stages: Stage[]): { index: number; title: string } | null {
  const i = stages.findIndex((s) => s.state === 'current' || s.state === 'failed');
  if (i < 0) return null;
  return { index: i, title: stages[i].title };
}
