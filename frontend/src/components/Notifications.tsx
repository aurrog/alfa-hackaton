import { ActionIcon, Button, Divider, Group, Indicator, Popover, ScrollArea, Stack, Text, UnstyledButton } from '@mantine/core';
import { IconBell } from '@tabler/icons-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { NotificationItem } from '../api/types';
import { fromNow } from '../lib/format';

const KIND_TONE: Record<string, string> = { action: 'warn', info: 'info', success: 'ok', warning: 'bad' };

export function Notifications() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const q = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.get<{ items: NotificationItem[]; unread: number }>('/api/v1/notifications', { limit: 30 }),
    refetchInterval: 8000,
  });
  const readAll = useMutation({
    mutationFn: () => api.post('/api/v1/notifications/read-all'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  });
  const openItem = async (n: NotificationItem) => {
    if (!n.read) await api.post(`/api/v1/notifications/${n.id}/read`).catch(() => undefined);
    void qc.invalidateQueries({ queryKey: ['notifications'] });
    setOpen(false);
    if (n.link) nav(n.link);
  };
  const unread = q.data?.unread ?? 0;
  // новое уведомление — колокольчик покачивается
  const prev = useRef<number | null>(null);
  const [ring, setRing] = useState(false);
  useEffect(() => {
    if (prev.current !== null && unread > prev.current) {
      setRing(true);
      const t = window.setTimeout(() => setRing(false), 1200);
      prev.current = unread;
      return () => window.clearTimeout(t);
    }
    prev.current = unread;
  }, [unread]);
  return (
    <Popover opened={open} onChange={setOpen} width={380} position="bottom-end" shadow="lg">
      <Popover.Target>
        <Indicator label={unread} size={16} disabled={!unread} color="brand" offset={5}>
          <ActionIcon variant="subtle" color="ink" size={38} aria-label="Уведомления" onClick={() => setOpen((o) => !o)} className={ring ? 'ring-bell' : undefined}>
            <IconBell size={21} stroke={1.7} />
          </ActionIcon>
        </Indicator>
      </Popover.Target>
      <Popover.Dropdown p={0}>
        <Group justify="space-between" px="md" py="sm">
          <Text fw={700} className="display">
            Уведомления
          </Text>
          {unread > 0 && (
            <Button size="compact-xs" variant="subtle" onClick={() => readAll.mutate()}>
              Прочитать все
            </Button>
          )}
        </Group>
        <Divider />
        <ScrollArea.Autosize mah={420}>
          {!q.data?.items.length && (
            <Text c="dimmed" size="sm" p="md">
              Пока уведомлений нет. Здесь появятся задачи и решения по заявкам — без писем и SMS.
            </Text>
          )}
          <Stack gap={0}>
            {q.data?.items.map((n) => (
              <UnstyledButton key={n.id} onClick={() => openItem(n)} px="md" py="sm" style={{ borderBottom: '1px solid var(--line)', background: n.read ? undefined : 'var(--plate)' }}>
                <Group gap={10} wrap="nowrap" align="flex-start">
                  <span className={`status ${KIND_TONE[n.kind] ?? ''}`} style={{ marginTop: 6 }}>
                    <span className="dot" />
                  </span>
                  <div style={{ minWidth: 0 }}>
                    <Text size="sm" fw={n.read ? 500 : 700}>
                      {n.title}
                    </Text>
                    {n.body && (
                      <Text size="xs" c="dimmed" lineClamp={2}>
                        {n.body}
                      </Text>
                    )}
                    <Text size="xs" c="dimmed" mt={2}>
                      {fromNow(n.created_at)}
                    </Text>
                  </div>
                </Group>
              </UnstyledButton>
            ))}
          </Stack>
        </ScrollArea.Autosize>
      </Popover.Dropdown>
    </Popover>
  );
}
