import { ActionIcon, Box, Button, Chip, Group, Modal, Stack, Text, Title, Tooltip } from '@mantine/core';
import { IconAdjustmentsHorizontal, IconEyeOff, IconThumbUp } from '@tabler/icons-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Feed as FeedT, FeedCard } from '../api/types';
import { date } from '../lib/format';
import { Loading } from './ui';

function Why({ c }: { c: FeedCard }) {
  return (
    <Text className="why">
      Почему вы это видите:{' '}
      {c.why.map((w, i) => (
        <span key={i}>
          {i > 0 && ' · '}
          <b>{w}</b>
        </span>
      ))}
    </Text>
  );
}

function Card1({ c, companyId, onOpen }: { c: FeedCard; companyId: string; onOpen: (c: FeedCard) => void }) {
  const qc = useQueryClient();
  const [liked, setLiked] = useState(!!c.liked);
  const act = useMutation({ mutationFn: (action: string) => api.post(`/api/v1/feed/actions?company_id=${companyId}`, { news_id: c.id, action }) });
  const hide = async () => {
    await act.mutateAsync('hide');
    void qc.invalidateQueries({ queryKey: ['feed', companyId] });
  };
  const like = async () => {
    setLiked(true);
    await act.mutateAsync('like');
  };
  const open = () => {
    if (c.type === 'news') act.mutate('open');
    onOpen(c);
  };
  return (
    <article className="feed-card">
      <Group justify="space-between" wrap="nowrap" gap={6}>
        <Text size="xs" c="dimmed" truncate>
          {c.type === 'insight' ? 'Для вас' : c.category_title}
          {c.published_at ? ` · ${date(c.published_at)}` : ''}
        </Text>
        <Group gap={0} wrap="nowrap" className="acts">
          {c.type === 'news' && (
            <Tooltip label={liked ? 'Покажем больше похожего' : 'Полезно'}>
              <ActionIcon size="sm" color={liked ? 'ok' : 'ink'} variant="subtle" onClick={like} aria-label="Полезно">
                <IconThumbUp size={15} />
              </ActionIcon>
            </Tooltip>
          )}
          <Tooltip label="Скрыть и показывать меньше такого">
            <ActionIcon size="sm" variant="subtle" onClick={hide} aria-label="Скрыть">
              <IconEyeOff size={15} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>
      <Text fw={600} fz={15.5} lh={1.3} style={{ cursor: 'pointer' }} onClick={open}>
        {c.title}
      </Text>
      <Text size="sm" c="var(--ink-2)" lineClamp={3} lh={1.45}>
        {c.summary}
      </Text>
      <Group gap={14} mt="auto" pt={6}>
        {c.body && (
          <button type="button" className="link-btn" onClick={open} style={{ fontSize: 13.5 }}>
            Читать
          </button>
        )}
        {c.cta && (
          <Link to={c.cta.link} className="link-btn" style={{ fontSize: 13.5, fontWeight: 600 }}>
            {c.cta.label}
          </Link>
        )}
      </Group>
    </article>
  );
}

export function Feed({ companyId, limit }: { companyId: string; limit?: number }) {
  const qc = useQueryClient();
  const [settings, setSettings] = useState(false);
  const [all, setAll] = useState(false);
  const [opened, setOpened] = useState<FeedCard | null>(null);
  const q = useQuery({ queryKey: ['feed', companyId], queryFn: () => api.get<FeedT>('/api/v1/feed', { company_id: companyId }) });
  const [topics, setTopics] = useState<string[]>([]);
  useEffect(() => {
    if (q.data) setTopics(q.data.selected_topics);
  }, [q.data]);
  const save = useMutation({
    mutationFn: () => api.put('/api/v1/feed/topics', { topics }),
    onSuccess: () => {
      setSettings(false);
      void qc.invalidateQueries({ queryKey: ['feed', companyId] });
    },
  });
  if (q.isLoading) return <Loading text="Собираем подборку под ваш бизнес…" />;
  if (!q.data) return null;
  const p = q.data.profile;
  const cards = limit && !all ? q.data.cards.slice(0, limit) : q.data.cards;
  return (
    <Box>
      <Group justify="space-between" align="flex-end" mb={12} wrap="nowrap">
        <Box>
          <Title order={3}>Полезное для вашего бизнеса</Title>
          <Text size="sm" c="dimmed" mt={4}>
            Подборка под профиль: {p.sector.toLowerCase()} · {p.region} · {p.legal_form}
            {p.bank_client ? ' · клиент банка' : ''}
          </Text>
        </Box>
        <Button variant="default" size="xs" leftSection={<IconAdjustmentsHorizontal size={15} />} onClick={() => setSettings(true)}>
          Темы
        </Button>
      </Group>
      <div className="feed-grid">
        {cards.map((c) => (
          <Card1 key={c.id} c={c} companyId={companyId} onOpen={setOpened} />
        ))}
      </div>
      <Group justify="space-between" mt={12}>
        <Text size="xs" c="dimmed">
          Материалы демонстрационные: показывают механику персонализации. Лента учится на реакциях «Полезно» и «Скрыть».
        </Text>
        {limit && q.data.cards.length > limit && (
          <button type="button" className="link-btn" onClick={() => setAll((a) => !a)} style={{ fontSize: 14 }}>
            {all ? 'Свернуть' : `Показать все (${q.data.cards.length})`}
          </button>
        )}
      </Group>

      <Modal opened={!!opened} onClose={() => setOpened(null)} size="lg" title={opened?.type === 'insight' ? 'Для вас' : opened?.category_title}>
        {opened && (
          <Stack gap="sm">
            <Title order={3}>{opened.title}</Title>
            <Text size="sm" c="var(--ink-2)">
              {opened.summary}
            </Text>
            {opened.body && (
              <Text size="sm" lh={1.6}>
                {opened.body}
              </Text>
            )}
            {opened.source && (
              <Text size="xs" c="dimmed">
                Источник: {opened.source}
              </Text>
            )}
            <Why c={opened} />
            {opened.cta && (
              <Group mt="sm">
                <Button component={Link} to={opened.cta.link} onClick={() => setOpened(null)}>
                  {opened.cta.label}
                </Button>
              </Group>
            )}
          </Stack>
        )}
      </Modal>

      <Modal opened={settings} onClose={() => setSettings(false)} title="Темы подборки">
        <Text size="sm" c="dimmed" mb="md">
          Отметьте интересные темы — они получат приоритет.
        </Text>
        <Chip.Group multiple value={topics} onChange={setTopics}>
          <Group gap={6}>
            {q.data.topics.map((t) => (
              <Chip key={t.code} value={t.code} size="sm" variant="light">
                {t.title}
              </Chip>
            ))}
          </Group>
        </Chip.Group>
        <Group justify="flex-end" mt="xl">
          <Button onClick={() => save.mutate()} loading={save.isPending}>
            Сохранить
          </Button>
        </Group>
      </Modal>
    </Box>
  );
}
