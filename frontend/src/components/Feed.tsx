import { ActionIcon, Anchor, Badge, Button, Card, Chip, Collapse, Group, Modal, Stack, Text, Title, Tooltip } from '@mantine/core';
import { IconAdjustmentsHorizontal, IconEyeOff, IconSparkles, IconThumbUp } from '@tabler/icons-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Feed as FeedT, FeedCard } from '../api/types';
import { date } from '../lib/format';
import { Loading } from './ui';

const CAT_COLOR: Record<string, string> = {
  insight: 'route', support: 'lime', taxes: 'amber', market: 'violet', product: 'route', education: 'teal', regulation: 'orange', industry: 'grape',
};

function Card1({ c, companyId }: { c: FeedCard; companyId: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [why, setWhy] = useState(false);
  const [liked, setLiked] = useState(!!c.liked);
  const act = useMutation({
    mutationFn: (action: string) => api.post(`/api/v1/feed/actions?company_id=${companyId}`, { news_id: c.id, action }),
  });
  const toggle = () => {
    if (!open && c.type === 'news') act.mutate('open');
    setOpen((o) => !o);
  };
  const hide = async () => {
    await act.mutateAsync('hide');
    void qc.invalidateQueries({ queryKey: ['feed', companyId] });
  };
  const like = async () => {
    setLiked(true);
    await act.mutateAsync('like');
  };
  return (
    <Card className="feed-card" padding="md" style={c.type === 'insight' ? { borderColor: 'var(--mantine-color-route-3)' } : undefined}>
      <Group justify="space-between" wrap="nowrap" align="flex-start" gap="xs">
        <Group gap={6}>
          <Badge color={CAT_COLOR[c.category] ?? 'gray'} leftSection={c.type === 'insight' ? <IconSparkles size={11} /> : undefined}>
            {c.category_title}
          </Badge>
          {c.published_at && (
            <Text size="xs" c="dimmed">
              {date(c.published_at)}
            </Text>
          )}
        </Group>
        <Group gap={2} wrap="nowrap">
          {c.type === 'news' && (
            <Tooltip label={liked ? 'Покажем больше похожего' : 'Полезно — показывать больше похожего'}>
              <ActionIcon variant={liked ? 'light' : 'subtle'} color={liked ? 'lime' : 'gray'} size="sm" onClick={like} aria-label="Полезно">
                <IconThumbUp size={15} />
              </ActionIcon>
            </Tooltip>
          )}
          <Tooltip label="Скрыть и показывать меньше такого">
            <ActionIcon variant="subtle" color="gray" size="sm" onClick={hide} aria-label="Скрыть">
              <IconEyeOff size={15} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>
      <Text fw={700} mt={8} style={{ cursor: c.body ? 'pointer' : undefined }} onClick={c.body ? toggle : undefined}>
        {c.title}
      </Text>
      <Text size="sm" c="dimmed" mt={4}>
        {c.summary}
      </Text>
      {c.body && (
        <Collapse in={open}>
          <Text size="sm" mt="xs">
            {c.body}
          </Text>
          {c.source && (
            <Text size="xs" c="dimmed" mt={4}>
              Источник: {c.source}
            </Text>
          )}
        </Collapse>
      )}
      <Group justify="space-between" mt="sm" gap="xs">
        <Anchor component="button" size="xs" c="dimmed" onClick={() => setWhy((w) => !w)}>
          Почему вы это видите
        </Anchor>
        <Group gap="xs">
          {c.body && (
            <Button size="compact-xs" variant="subtle" onClick={toggle}>
              {open ? 'Свернуть' : 'Читать'}
            </Button>
          )}
          {c.cta && (
            <Button size="compact-xs" variant="light" component={Link} to={c.cta.link}>
              {c.cta.label}
            </Button>
          )}
        </Group>
      </Group>
      <Collapse in={why}>
        <Text className="why" mt={6}>
          {c.why.map((w, i) => (
            <span key={i}>
              {i > 0 && ' · '}
              <b>{w}</b>
            </span>
          ))}
          {c.type === 'news' && ` · релевантность ${c.relevance.toFixed(1).replace('.', ',')}`}
        </Text>
      </Collapse>
    </Card>
  );
}

export function Feed({ companyId, limit }: { companyId: string; limit?: number }) {
  const qc = useQueryClient();
  const [settings, setSettings] = useState(false);
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
  if (q.isLoading) return <Loading text="Собираем ленту под ваш бизнес…" />;
  if (!q.data) return null;
  const p = q.data.profile;
  const cards = limit ? q.data.cards.slice(0, limit) : q.data.cards;
  return (
    <Stack gap="sm">
      <Group justify="space-between" align="flex-end">
        <div>
          <Title order={3}>Лента для вашего бизнеса</Title>
          <Text size="xs" c="dimmed" mt={4}>
            {p.sector} · {p.region} · {p.legal_form}
            {p.bank_client ? ' · клиент банка' : ''}
          </Text>
        </div>
        <Tooltip label="Выбрать темы">
          <ActionIcon variant="light" onClick={() => setSettings(true)} aria-label="Настроить ленту">
            <IconAdjustmentsHorizontal size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>
      {cards.map((c) => (
        <Card1 key={c.id} c={c} companyId={companyId} />
      ))}
      <Text size="xs" c="dimmed">
        Демонстрационная лента: материалы синтетические и показывают механику персонализации.
      </Text>
      <Modal opened={settings} onClose={() => setSettings(false)} title={<Text fw={700}>Темы ленты</Text>} centered>
        <Text size="sm" c="dimmed" mb="sm">
          Отметьте интересные темы — они получат приоритет. Лента также учится на ваших реакциях «Полезно» и «Скрыть».
        </Text>
        <Chip.Group multiple value={topics} onChange={setTopics}>
          <Group gap={6}>
            {q.data.topics.map((t) => (
              <Chip key={t.code} value={t.code} size="sm">
                {t.title}
              </Chip>
            ))}
          </Group>
        </Chip.Group>
        <Group justify="flex-end" mt="lg">
          <Button onClick={() => save.mutate()} loading={save.isPending}>
            Сохранить
          </Button>
        </Group>
      </Modal>
    </Stack>
  );
}
