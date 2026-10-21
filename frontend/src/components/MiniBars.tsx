import { Box, Group, Text, Tooltip } from '@mantine/core';
import { millions } from '../lib/format';

/** Лёгкая столбчатая диаграмма (без библиотеки) для помесячных оборотов. */
export function BarChart({ data, height = 70, color = 'var(--mantine-color-route-5)' }: { data: { label: string; value: number }[]; height?: number; color?: string }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <Box>
      <Group gap={3} align="flex-end" h={height} wrap="nowrap">
        {data.map((d, i) => (
          <Tooltip key={i} label={`${d.label}: ${millions(d.value)}`}>
            <Box style={{ flex: 1, height: `${Math.max((d.value / max) * 100, 2)}%`, background: color, borderRadius: '4px 4px 1px 1px', minWidth: 4 }} />
          </Tooltip>
        ))}
      </Group>
      <Group gap={3} wrap="nowrap" mt={2}>
        {data.map((d, i) => (
          <Text key={i} size="10px" c="dimmed" ta="center" style={{ flex: 1 }}>
            {d.label}
          </Text>
        ))}
      </Group>
    </Box>
  );
}
