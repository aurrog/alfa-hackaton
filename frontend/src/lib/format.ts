import dayjs from 'dayjs';
import 'dayjs/locale/ru';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(relativeTime);
dayjs.locale('ru');

const nbsp = ' ';

export function money(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined || Number.isNaN(x)) return '—';
  return (
    new Intl.NumberFormat('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(x) + `${nbsp}₽`
  );
}

export function num(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined) return '—';
  return new Intl.NumberFormat('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(x);
}

/** 21.5 → «21,5%» */
export function pct(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined) return '—';
  const s = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: digits }).format(x);
  return `${s}%`;
}

/** 0.0723 → «7,2%» */
export const share = (x: number | null | undefined, digits = 1) => (x === null || x === undefined ? '—' : pct(x * 100, digits));

export function millions(x: number): string {
  if (Math.abs(x) >= 1_000_000) return `${num(x / 1_000_000, x % 1_000_000 === 0 ? 0 : 1)}${nbsp}млн${nbsp}₽`;
  if (Math.abs(x) >= 1_000) return `${num(x / 1_000, 0)}${nbsp}тыс.${nbsp}₽`;
  return money(x);
}

export const date = (d?: string | null) => (d ? dayjs(d).format('D MMMM YYYY') : '—');
export const shortDate = (d?: string | null) => (d ? dayjs(d).format('DD.MM.YYYY') : '—');
export const dateTime = (d?: string | null) => (d ? dayjs(d).format('D MMM, HH:mm') : '—');
export const fromNow = (d?: string | null) => (d ? dayjs(d).fromNow() : '—');

export function plural(n: number, one: string, few: string, many: string): string {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
}

export const months = (n: number) => `${n}${nbsp}${plural(n, 'месяц', 'месяца', 'месяцев')}`;

/** Сколько осталось до срока (норматив SLA): «через 2 ч», «просрочено на 15 мин». */
export function slaLeft(due?: string | null): { text: string; overdue: boolean } | null {
  if (!due) return null;
  const diff = dayjs(due).diff(dayjs(), 'minute');
  const abs = Math.abs(diff);
  const t = abs >= 1440 ? `${Math.round(abs / 1440)} дн.` : abs >= 60 ? `${Math.round(abs / 60)} ч` : `${abs} мин`;
  return diff >= 0 ? { text: `осталось ${t}`, overdue: false } : { text: `просрочено на ${t}`, overdue: true };
}

export function fileSize(b: number): string {
  if (b < 1024) return `${b} Б`;
  if (b < 1024 * 1024) return `${num(b / 1024, 0)} КБ`;
  return `${num(b / 1024 / 1024, 1)} МБ`;
}

export function annuity(amount: number, rate: number, months: number): number {
  const r = rate / 1200;
  if (!r) return amount / months;
  return (amount * r) / (1 - (1 + r) ** -months);
}
