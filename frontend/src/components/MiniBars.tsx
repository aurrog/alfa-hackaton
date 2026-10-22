import { Box, Group, Text, Tooltip } from '@mantine/core';
import { millions } from '../lib/format';

/** Лёгкая столбчатая диаграмма (без библиотеки) для помесячных оборотов. */
export function BarChart({ data, height = 72, color = 'var(--ink)' }: { data: { label: string; value: number }[]; height?: number; color?: string }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <Box>
      <Group gap={4} align="flex-end" h={height} wrap="nowrap">
        {data.map((d, i) => (
          <Tooltip key={i} label={`${d.label}: ${millions(d.value)}`}>
            <Box style={{ flex: 1, height: `${Math.max((d.value / max) * 100, 3)}%`, background: color, opacity: 0.85, borderRadius: 4, minWidth: 4 }} />
          </Tooltip>
        ))}
      </Group>
      <Group gap={4} wrap="nowrap" mt={4}>
        {data.map((d, i) => (
          <Text key={i} size="10px" c="dimmed" ta="center" style={{ flex: 1 }}>
            {d.label}
          </Text>
        ))}
      </Group>
    </Box>
  );
}
