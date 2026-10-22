import { createTheme, type MantineColorsTuple } from '@mantine/core';

/*
 * Визуальный язык: белый фон, серые плашки без рамок и теней, чёрный текст, крупные цифры.
 * Красный (brand) — только главное действие экрана и фирменные акценты.
 * Цвета состояний:
 *   warn — ход за клиентом, info — работает банк или система, ok — готово, bad — отказ и ошибки.
 * У всех палитр «основной» оттенок — шестой (primaryShade), поэтому ink[6] — почти чёрный.
 */
const brand: MantineColorsTuple = ['#fff0ee', '#ffdcd8', '#ffb7af', '#ff8f83', '#fb6a5c', '#f54b3c', '#ef3124', '#d42a1e', '#b82216', '#9b1a10'];
const ink: MantineColorsTuple = ['#f3f4f6', '#e9ebee', '#d9dce1', '#b9bdc6', '#8f949e', '#5f646e', '#0e0f11', '#2a2c31', '#060708', '#000000'];
const ok: MantineColorsTuple = ['#e9f8ef', '#d3f0de', '#a6e1bd', '#75d09a', '#4cc27c', '#32b96a', '#149c55', '#108749', '#0b733d', '#065e31'];
const warn: MantineColorsTuple = ['#fff4e5', '#ffe8cc', '#ffd099', '#ffb661', '#ffa033', '#ff9419', '#f08a00', '#d17800', '#b36600', '#945400'];
const info: MantineColorsTuple = ['#eef3ff', '#dbe6ff', '#b5ccff', '#8bb0ff', '#6697fc', '#4d86f7', '#2f6fed', '#2259cf', '#1a4ab0', '#123a91'];
const bad: MantineColorsTuple = ['#fdecea', '#fad6d2', '#f3aca5', '#ec7f75', '#e5584c', '#e03f32', '#d92d20', '#bd2318', '#a01b12', '#83130b'];

const filled = { defaultProps: { variant: 'filled', radius: 'md' } };

export const theme = createTheme({
  primaryColor: 'ink',
  primaryShade: 6,
  colors: { brand, ink, ok, warn, info, bad },
  black: '#0e0f11',
  fontFamily: "'Wix Madefor Text', -apple-system, 'Segoe UI', Roboto, Arial, sans-serif",
  fontFamilyMonospace: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
  headings: {
    fontFamily: "'Wix Madefor Display', 'Wix Madefor Text', -apple-system, 'Segoe UI', sans-serif",
    fontWeight: '700',
    sizes: {
      h1: { fontSize: '2.25rem', lineHeight: '1.1' },
      h2: { fontSize: '1.625rem', lineHeight: '1.15' },
      h3: { fontSize: '1.25rem', lineHeight: '1.25' },
      h4: { fontSize: '1.0625rem', lineHeight: '1.3' },
    },
  },
  fontSizes: { xs: '12px', sm: '14px', md: '15px', lg: '17px', xl: '20px' },
  defaultRadius: 'md',
  radius: { xs: '6px', sm: '8px', md: '12px', lg: '20px', xl: '28px' },
  cursorType: 'pointer',
  components: {
    Button: { defaultProps: { radius: 'md' } },
    ActionIcon: { defaultProps: { radius: 'md', variant: 'subtle', color: 'ink' } },
    TextInput: filled,
    PasswordInput: filled,
    Textarea: filled,
    Select: filled,
    MultiSelect: filled,
    NumberInput: { defaultProps: { variant: 'filled', radius: 'md', thousandSeparator: ' ', decimalSeparator: ',' } },
    Card: { defaultProps: { radius: 'lg', padding: 'lg', withBorder: false } },
    Paper: { defaultProps: { radius: 'lg' } },
    Badge: { defaultProps: { radius: 'sm', variant: 'light' } },
    Modal: { defaultProps: { radius: 'lg', centered: true, padding: 'xl', overlayProps: { backgroundOpacity: 0.4 } } },
    Drawer: { defaultProps: { overlayProps: { backgroundOpacity: 0.3 } } },
    Tooltip: { defaultProps: { withArrow: true, multiline: true, maw: 320, color: 'ink' } },
    Popover: { defaultProps: { radius: 'md', shadow: 'md' } },
    Menu: { defaultProps: { radius: 'md', shadow: 'md' } },
    SegmentedControl: { defaultProps: { radius: 'md' } },
    Tabs: { defaultProps: { color: 'ink' } },
    Slider: { defaultProps: { color: 'brand', size: 'sm' } },
    Checkbox: { defaultProps: { color: 'ink', radius: 'sm' } },
    Switch: { defaultProps: { color: 'ink' } },
    Chip: { defaultProps: { color: 'ink', radius: 'md' } },
    Progress: { defaultProps: { radius: 'xl' } },
    Accordion: { defaultProps: { radius: 'lg' } },
    Alert: { defaultProps: { radius: 'md', variant: 'light' } },
    Table: { defaultProps: { verticalSpacing: 'sm', horizontalSpacing: 'md' } },
  },
});

/** Цвет и подпись по тому, чей сейчас ход (поле waiting из API). */
export const WAITING_COLOR: Record<string, string> = { client: 'warn', bank: 'info', system: 'info', none: 'ink' };
export const WAITING_TITLE: Record<string, string> = {
  client: 'Ход за вами',
  bank: 'Работает банк',
  system: 'Автоматическая проверка',
  none: 'Завершено',
};
