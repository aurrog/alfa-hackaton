import { createTheme, type MantineColorsTuple } from '@mantine/core';

/*
 * Палитра «цвет = чей ход»:
 *   amber  — действие за клиентом
 *   violet — заявка у банка (специалист, комитет)
 *   route  — работает система (автоматический конвейер), основной цвет интерфейса
 *   lime   — готово / одобрено / выдано
 *   signal — отказ, ошибка, нарушен норматив
 */
const route: MantineColorsTuple = ['#eaf1ff', '#d3e1ff', '#a6c1ff', '#759eff', '#4d81ff', '#3d7bff', '#2a62e6', '#1d50cc', '#1444a8', '#0b3484'];
const amber: MantineColorsTuple = ['#fff6e1', '#ffeccb', '#ffd795', '#ffc05c', '#ffad2f', '#ffa112', '#ff9a00', '#e38600', '#ca7600', '#af6500'];
const violet: MantineColorsTuple = ['#f3edff', '#e1d7fb', '#c0abf1', '#9d7ce8', '#8054e0', '#6d3bdc', '#6330da', '#5223c2', '#481dae', '#3c169a'];
const lime: MantineColorsTuple = ['#f6fde7', '#ecf8d4', '#d7efaa', '#c1e67c', '#aede55', '#a2d93c', '#9bd72e', '#86bd20', '#76a817', '#638f08'];
const signal: MantineColorsTuple = ['#ffe9ea', '#ffd1d3', '#fba1a4', '#f76e73', '#f34349', '#f1282f', '#f11921', '#d60b14', '#bf0010', '#a7000b'];
const ink: MantineColorsTuple = ['#f4f5f8', '#e6e8ee', '#cbcfdb', '#adb3c6', '#939bb4', '#838ca9', '#7a84a4', '#68718f', '#5c6481', '#14161f'];

export const theme = createTheme({
  primaryColor: 'route',
  primaryShade: { light: 6, dark: 5 },
  colors: { route, amber, violet, lime, signal, ink },
  fontFamily: "Onest, -apple-system, 'Segoe UI', Roboto, sans-serif",
  headings: {
    fontFamily: "Unbounded, Onest, -apple-system, 'Segoe UI', sans-serif",
    fontWeight: '600',
    sizes: { h1: { fontSize: '1.9rem', lineHeight: '1.2' }, h2: { fontSize: '1.45rem' }, h3: { fontSize: '1.15rem' }, h4: { fontSize: '1rem' } },
  },
  defaultRadius: 'md',
  radius: { md: '10px', lg: '16px' },
  cursorType: 'pointer',
  components: {
    Card: { defaultProps: { withBorder: true, radius: 'lg', padding: 'lg' } },
    Button: { defaultProps: { radius: 'md' } },
    Badge: { defaultProps: { radius: 'sm', variant: 'light' } },
    Paper: { defaultProps: { radius: 'lg' } },
    Tooltip: { defaultProps: { withArrow: true, multiline: true, maw: 320 } },
    NumberInput: { defaultProps: { thousandSeparator: ' ', decimalSeparator: ',' } },
  },
});

/** Цвет по тому, чей сейчас ход (поле waiting из API). */
export const WAITING_COLOR: Record<string, string> = { client: 'amber', bank: 'violet', system: 'route', none: 'gray' };
export const WAITING_TITLE: Record<string, string> = {
  client: 'Ход за вами',
  bank: 'Работает банк',
  system: 'Автоматическая обработка',
  none: 'Завершено',
};
