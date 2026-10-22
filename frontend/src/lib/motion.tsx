import { useEffect, useRef, useState, type CSSProperties } from 'react';

/** Пользователь попросил систему уменьшить движение — анимации отключаем. */
export const reducedMotion = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

const easeOutCubic = (t: number) => 1 - (1 - t) ** 3;

/**
 * Плавно «докручивает» число к новому значению (платёж при движении ползунка, сумма решения).
 * from — с чего начать при первом показе (0 — эффект счётчика); duration 0 — без анимации.
 */
export function useTween(value: number, duration = 450, from?: number): number {
  const [shown, setShown] = useState(from ?? value);
  const current = useRef(from ?? value);
  useEffect(() => {
    if (duration <= 0 || reducedMotion() || !Number.isFinite(value)) {
      current.current = value;
      setShown(value);
      return;
    }
    const start = current.current;
    const delta = value - start;
    if (Math.abs(delta) < 0.5) {
      current.current = value;
      setShown(value);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - t0) / duration);
      const v = start + delta * easeOutCubic(t);
      current.current = v;
      setShown(v);
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);
  return shown;
}

/** Число с анимацией и произвольным форматом (показатели дашборда). */
export function AnimatedNumber({ value, format, duration = 700, countUp = true }: { value: number; format: (v: number) => string; duration?: number; countUp?: boolean }) {
  const v = useTween(value, duration, countUp ? 0 : undefined);
  return <>{format(v)}</>;
}

/** Галочка, которая «рисуется»: круг появляется, затем проводится штрих. */
export function CheckDraw({ size = 22, color = 'var(--ok)', delay = 0, style }: { size?: number; color?: string; delay?: number; style?: CSSProperties }) {
  const d = { animationDelay: `${delay}ms` };
  const d2 = { animationDelay: `${delay + 180}ms` };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className="check-draw" style={{ flex: 'none', ...style }} aria-hidden>
      <circle cx="12" cy="12" r="11" fill={color} className="cd-circle" style={d} />
      <path d="M7 12.5l3.2 3.2L17 9" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" className="cd-path" style={d2} />
    </svg>
  );
}

/** Индикатор «идёт работа» — вращающееся кольцо. */
export function Spinner({ size = 22 }: { size?: number }) {
  return <span className="spin" style={{ width: size, height: size }} aria-hidden />;
}
