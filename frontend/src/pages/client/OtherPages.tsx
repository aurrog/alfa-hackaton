import { Accordion, Alert, Badge, Box, Button, Card, Group, SimpleGrid, Stack, Text, TextInput, ThemeIcon, Title } from '@mantine/core';
import { IconBuildingStore, IconSearch } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, errorText } from '../../api/client';
import type { ApplicationSummary, Company, Loan } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { Schedule } from '../../components/Schedule';
import { Empty, Loading, PageHeader, StatusBadge, WaitingChip } from '../../components/ui';
import { date, money, months, pct, shortDate } from '../../lib/format';

export function ApplicationsPage() {
  const { company } = useAuth();
  const q = useQuery({
    queryKey: ['applications', company?.id],
    queryFn: () => api.get<{ items: ApplicationSummary[] }>('/api/v1/applications', { company_id: company?.id }),
    enabled: !!company,
    refetchInterval: 6000,
  });
  return (
    <Stack>
      <PageHeader title="Заявки" subtitle={company?.short_name} right={<Button component={Link} to="/products">Новая заявка</Button>} />
      {q.isLoading && <Loading />}
      {q.data && !q.data.items.length && <Empty title="Заявок пока нет" text="Подберите финансирование под задачу бизнеса — заявка заполнится автоматически." action={<Button component={Link} to="/products">Подобрать</Button>} />}
      <Stack gap="sm">
        {q.data?.items.map((a) => (
          <Card key={a.id} padding="md" component={Link} to={a.status === 'draft' || a.status === 'pending_signature' ? `/applications/${a.id}/edit` : `/applications/${a.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
            <Group justify="space-between" wrap="wrap">
              <Box>
                <Group gap={8}>
                  <Text fw={700}>{a.product_name}</Text>
                  <StatusBadge label={a.status_label} tone={a.status_tone} size="sm" />
                </Group>
                <Text size="sm" c="dimmed" className="num">
                  {a.number} · {money(a.amount)} · {months(a.term_months)} · создана {shortDate(a.created_at)}
                </Text>
                {a.offer && (
                  <Text size="sm" mt={4} className="num">
                    Предложение: {money(a.offer.amount)} · {pct(a.offer.rate)} · {money(a.offer.monthly_payment)}/мес{a.offer.is_counter ? ' · изменённые условия' : ''}
                  </Text>
                )}
              </Box>
              <Stack gap={4} align="flex-end">
                <WaitingChip waiting={a.waiting} due={a.sla_due_at} />
                {a.next_action && (
                  <Text size="sm" fw={600} c={a.waiting === 'client' ? 'amber.8' : undefined}>
                    {a.next_action}
                  </Text>
                )}
              </Stack>
            </Group>
          </Card>
        ))}
      </Stack>
    </Stack>
  );
}

export function LoansPage() {
  const { company } = useAuth();
  const q = useQuery({ queryKey: ['loans', company?.id], queryFn: () => api.get<{ items: Loan[] }>('/api/v1/loans', { company_id: company?.id }), enabled: !!company });
  return (
    <Stack>
      <PageHeader title="Кредиты" subtitle="Действующие кредиты и графики платежей" />
      {q.isLoading && <Loading />}
      {q.data && !q.data.items.length && <Empty title="Действующих кредитов нет" text="Когда кредит будет выдан, здесь появится график платежей." />}
      <Accordion variant="separated" radius="lg" defaultValue={q.data?.items[0]?.id}>
        {q.data?.items.map((l) => (
          <Accordion.Item key={l.id} value={l.id}>
            <Accordion.Control>
              <Group justify="space-between" pr="md" wrap="wrap">
                <Box>
                  <Text fw={700}>{l.product_name}</Text>
                  <Text size="sm" c="dimmed">
                    Договор {l.contract_number} от {date(l.issued_at)} · ссудный счёт {l.loan_account}
                  </Text>
                </Box>
                <Group gap="lg">
                  <Box ta="right">
                    <Text size="xs" c="dimmed">Сумма</Text>
                    <Text fw={700} className="num">{money(l.amount)}</Text>
                  </Box>
                  <Box ta="right">
                    <Text size="xs" c="dimmed">Платёж</Text>
                    <Text fw={700} className="num">{money(l.monthly_payment)}</Text>
                  </Box>
                  {l.next_payment && <Badge color="amber">ближайший {shortDate(l.next_payment.date)}</Badge>}
                </Group>
              </Group>
            </Accordion.Control>
            <Accordion.Panel>
              <SimpleGrid cols={{ base: 2, sm: 4 }} mb="md">
                <Box><Text size="xs" c="dimmed">Ставка</Text><Text fw={600}>{pct(l.rate, 2)}</Text></Box>
                <Box><Text size="xs" c="dimmed">Срок</Text><Text fw={600}>{months(l.term_months)}</Text></Box>
                <Box><Text size="xs" c="dimmed">Расчётный счёт</Text><Text fw={600}>{l.settlement_account ?? '—'}</Text></Box>
                <Box><Text size="xs" c="dimmed">Статус</Text><Text fw={600}>{l.status === 'active' ? 'Действует' : l.status}</Text></Box>
              </SimpleGrid>
              <Schedule rows={l.schedule} initial={12} />
              <Text size="xs" c="dimmed" mt="sm">
                Сопровождение кредита (платежи, досрочное погашение) — за пределами прототипа.
              </Text>
            </Accordion.Panel>
          </Accordion.Item>
        ))}
      </Accordion>
    </Stack>
  );
}

export function ConnectCompanyPage() {
  const { refresh, selectCompany, companies } = useAuth();
  const nav = useNavigate();
  const [inn, setInn] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const connect = async () => {
    setBusy(true);
    setError(null);
    try {
      const c = await api.post<Company>('/api/v1/companies', { inn: inn.trim() });
      await refresh();
      selectCompany(c.id);
      nav('/');
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Stack maw={640} mx="auto" mt="lg">
      <Card padding="xl">
        <ThemeIcon size={46} radius="md" variant="light">
          <IconBuildingStore size={26} />
        </ThemeIcon>
        <Title order={2} mt="md">
          {companies.length ? 'Подключить ещё одну компанию' : 'Подключите компанию'}
        </Title>
        <Text c="dimmed" mt={6}>
          Введите ИНН — реквизиты, адрес, ОКВЭД и руководителя подставим из ЕГРЮЛ/ЕГРИП. Вводить их вручную не придётся.
        </Text>
        <Group mt="lg" align="flex-start" wrap="nowrap">
          <TextInput
            style={{ flex: 1 }}
            placeholder="10 цифр для ООО, 12 — для ИП"
            value={inn}
            onChange={(e) => setInn(e.currentTarget.value.replace(/\D/g, '').slice(0, 12))}
            onKeyDown={(e) => e.key === 'Enter' && connect()}
            leftSection={<IconSearch size={16} />}
            size="md"
            error={error}
          />
          <Button size="md" onClick={connect} loading={busy} disabled={![10, 12].includes(inn.length)}>
            Подключить
          </Button>
        </Group>
        <Alert variant="light" color="gray" mt="lg" title="Демо-стенд">
          Подойдёт любой корректный ИНН — симулятор реестров сгенерирует профиль компании. ИНН с префиксом 99 — пример «не найдено».
          В промышленной версии полномочия подтверждаются через Госуслуги или машиночитаемую доверенность.
        </Alert>
      </Card>
    </Stack>
  );
}

export function NotFoundPage() {
  return <Empty title="Страница не найдена" action={<Button component={Link} to="/">На главную</Button>} />;
}


