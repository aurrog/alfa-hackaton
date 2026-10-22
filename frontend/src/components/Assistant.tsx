import { ActionIcon, Affix, Box, Drawer, Group, ScrollArea, Stack, Text, Textarea, Tooltip, UnstyledButton } from '@mantine/core';
import { IconArrowUp, IconMessageCircle } from '@tabler/icons-react';
import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { api, errorText } from '../api/client';

interface Msg {
  role: 'user' | 'bot';
  text: string;
  sources?: { id: string; title: string }[];
  provider?: string;
}

const SUGGESTIONS = ['Почему одобрили меньшую сумму?', 'Что такое DSCR?', 'Зачем нужна выписка?', 'Как движется заявка?', 'Что делать после отказа?'];

/** Кнопка помощника в углу экрана (на компьютере; на телефоне помощник — в нижнем меню). */
export function AssistantButton({ onClick }: { onClick: () => void }) {
  return (
    <Affix position={{ bottom: 24, right: 24 }} visibleFrom="md">
      <Tooltip label="Помощник" position="left">
        <ActionIcon size={52} radius="xl" variant="filled" color="ink" onClick={onClick} aria-label="Помощник" style={{ boxShadow: '0 6px 20px rgba(14,15,17,.22)' }}>
          <IconMessageCircle size={24} />
        </ActionIcon>
      </Tooltip>
    </Affix>
  );
}

/** Помощник: отвечает по базе знаний и данным открытой заявки (без выдумывания фактов). */
export function AssistantDrawer({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: 'bot', text: 'Здравствуйте! Помогу разобраться в условиях, терминах и статусе заявки. Спросите своими словами.' },
  ]);
  const loc = useLocation();
  const appId = /^\/applications\/([0-9a-f-]{36})/.exec(loc.pathname)?.[1];
  const viewport = useRef<HTMLDivElement>(null);

  useEffect(() => {
    viewport.current?.scrollTo({ top: viewport.current.scrollHeight, behavior: 'smooth' });
  }, [msgs]);

  const ask = async (text: string) => {
    const question = text.trim();
    if (question.length < 2) return;
    setMsgs((m) => [...m, { role: 'user', text: question }]);
    setQ('');
    setBusy(true);
    try {
      const r = await api.post<{ answer: string; sources: Msg['sources']; provider: string }>('/api/v1/assistant', { question, application_id: appId });
      setMsgs((m) => [...m, { role: 'bot', text: r.answer, sources: r.sources, provider: r.provider }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: 'bot', text: errorText(e) }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer opened={opened} onClose={onClose} position="right" size="md" title={<Text fw={700} className="display" fz={18}>Помощник</Text>} styles={{ body: { paddingBottom: 12 } }}>
      <Stack h="calc(100dvh - 86px)" gap="sm">
        {appId && (
          <Text size="xs" c="dimmed">
            Учитываю данные открытой заявки
          </Text>
        )}
        <ScrollArea style={{ flex: 1 }} viewportRef={viewport}>
          <Stack gap={10} pr="xs">
            {msgs.map((m, i) => (
              <Box
                key={i}
                px={14}
                py={10}
                ml={m.role === 'user' ? 48 : 0}
                mr={m.role === 'bot' ? 24 : 0}
                style={{
                  borderRadius: m.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                  background: m.role === 'user' ? 'var(--ink)' : 'var(--plate)',
                  color: m.role === 'user' ? '#fff' : undefined,
                }}
              >
                <Text size="sm" style={{ whiteSpace: 'pre-wrap' }} lh={1.5}>
                  {m.text}
                </Text>
                {m.sources && m.sources.length > 0 && (
                  <Text size="xs" c="dimmed" mt={6}>
                    Источник: {m.sources.map((s) => s.title).join(', ')}
                  </Text>
                )}
              </Box>
            ))}
            {busy && (
              <Text size="sm" c="dimmed" className="pulse">
                Ищу ответ…
              </Text>
            )}
          </Stack>
        </ScrollArea>
        <Group gap={6}>
          {SUGGESTIONS.map((s) => (
            <UnstyledButton key={s} className="tag" onClick={() => ask(s)} disabled={busy} style={{ cursor: 'pointer' }}>
              {s}
            </UnstyledButton>
          ))}
        </Group>
        <Group align="flex-end" gap="xs" wrap="nowrap">
          <Textarea
            style={{ flex: 1 }}
            autosize
            minRows={1}
            maxRows={4}
            placeholder="Ваш вопрос"
            value={q}
            onChange={(e) => setQ(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                void ask(q);
              }
            }}
          />
          <ActionIcon size={38} variant="filled" color="ink" onClick={() => ask(q)} loading={busy} aria-label="Отправить" disabled={q.trim().length < 2}>
            <IconArrowUp size={18} />
          </ActionIcon>
        </Group>
        <Text size="xs" c="dimmed">
          Ответы — по базе знаний и данным вашей заявки. Помощник не принимает решений по кредиту.
        </Text>
      </Stack>
    </Drawer>
  );
}
