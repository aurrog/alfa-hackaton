import { ActionIcon, Affix, Badge, Button, Drawer, Group, Paper, ScrollArea, Stack, Text, Textarea, Tooltip } from '@mantine/core';
import { IconMessageCircleQuestion, IconSend } from '@tabler/icons-react';
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

/** Помощник: отвечает по базе знаний и данным открытой заявки (без выдумывания фактов). */
export function Assistant() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: 'bot', text: 'Здравствуйте! Я помогу разобраться в терминах, условиях и статусе заявки. Спросите своими словами.' },
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
      const r = await api.post<{ answer: string; sources: Msg['sources']; provider: string }>('/api/v1/assistant', {
        question,
        application_id: appId,
      });
      setMsgs((m) => [...m, { role: 'bot', text: r.answer, sources: r.sources, provider: r.provider }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: 'bot', text: errorText(e) }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Affix position={{ bottom: 20, right: 20 }}>
        <Tooltip label="Помощник">
          <ActionIcon size={54} radius="xl" variant="filled" color="ink.9" onClick={() => setOpen(true)} aria-label="Помощник" style={{ boxShadow: '0 8px 28px rgba(20,22,31,.25)' }}>
            <IconMessageCircleQuestion size={26} />
          </ActionIcon>
        </Tooltip>
      </Affix>
      <Drawer opened={open} onClose={() => setOpen(false)} position="right" size="md" title={<Text fw={700}>Помощник</Text>}>
        <Stack h="calc(100vh - 90px)" gap="sm">
          {appId && (
            <Badge variant="light" color="route">
              учитываю открытую заявку
            </Badge>
          )}
          <ScrollArea style={{ flex: 1 }} viewportRef={viewport}>
            <Stack gap="sm" pr="xs">
              {msgs.map((m, i) => (
                <Paper key={i} p="sm" radius="md" withBorder={m.role === 'bot'} bg={m.role === 'user' ? 'route.0' : undefined} ml={m.role === 'user' ? 40 : 0} mr={m.role === 'bot' ? 20 : 0}>
                  <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                    {m.text}
                  </Text>
                  {m.sources && m.sources.length > 0 && (
                    <Group gap={4} mt={6}>
                      {m.sources.map((s) => (
                        <Badge key={s.id} size="xs" variant="outline" color="gray">
                          {s.title}
                        </Badge>
                      ))}
                    </Group>
                  )}
                </Paper>
              ))}
            </Stack>
          </ScrollArea>
          <Group gap={6}>
            {SUGGESTIONS.map((s) => (
              <Button key={s} size="compact-xs" variant="light" color="gray" onClick={() => ask(s)} disabled={busy}>
                {s}
              </Button>
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
            <ActionIcon size={36} onClick={() => ask(q)} loading={busy} aria-label="Отправить">
              <IconSend size={18} />
            </ActionIcon>
          </Group>
          <Text size="xs" c="dimmed">
            Ответы строятся по базе знаний и данным вашей заявки. Помощник не принимает решений по кредиту.
          </Text>
        </Stack>
      </Drawer>
    </>
  );
}
