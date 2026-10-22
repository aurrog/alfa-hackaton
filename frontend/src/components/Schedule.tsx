import { ScrollArea, Table, Text } from '@mantine/core';
import { useState } from 'react';
import type { ScheduleRow } from '../api/types';
import { money, shortDate } from '../lib/format';

export function Schedule({ rows, initial = 6 }: { rows: ScheduleRow[]; initial?: number }) {
  const [all, setAll] = useState(false);
  if (!rows.length)
    return (
      <Text size="sm" c="dimmed">
        Для лимита график не формируется: проценты начисляются на фактическую задолженность.
      </Text>
    );
  const shown = all ? rows : rows.slice(0, initial);
  const total = rows.reduce((s, r) => s + r.payment, 0);
  const interest = rows.reduce((s, r) => s + r.interest, 0);
  return (
    <>
      <ScrollArea>
        <Table fz="sm" miw={560} verticalSpacing={8} horizontalSpacing={0}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>№</Table.Th>
              <Table.Th>Дата</Table.Th>
              <Table.Th ta="right">Платёж</Table.Th>
              <Table.Th ta="right">Основной долг</Table.Th>
              <Table.Th ta="right">Проценты</Table.Th>
              <Table.Th ta="right">Остаток</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {shown.map((r) => (
              <Table.Tr key={r.n}>
                <Table.Td c="dimmed">{r.n}</Table.Td>
                <Table.Td>{shortDate(r.date)}</Table.Td>
                <Table.Td ta="right" className="num" fw={600}>
                  {money(r.payment, 2)}
                </Table.Td>
                <Table.Td ta="right" className="num">
                  {money(r.principal, 2)}
                </Table.Td>
                <Table.Td ta="right" className="num">
                  {money(r.interest, 2)}
                </Table.Td>
                <Table.Td ta="right" className="num" c="dimmed">
                  {money(r.balance, 2)}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
          {all && (
            <Table.Tfoot>
              <Table.Tr>
                <Table.Th colSpan={2}>Итого</Table.Th>
                <Table.Th ta="right" className="num">
                  {money(total, 2)}
                </Table.Th>
                <Table.Th />
                <Table.Th ta="right" className="num">
                  {money(interest, 2)}
                </Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Tfoot>
          )}
        </Table>
      </ScrollArea>
      {rows.length > initial && (
        <button type="button" className="link-btn" style={{ fontSize: 13.5, marginTop: 10 }} onClick={() => setAll((v) => !v)}>
          {all ? 'Свернуть график' : `Показать все ${rows.length} платежей`}
        </button>
      )}
    </>
  );
}
