import { Accordion, Box, Button, Group, SimpleGrid, Stack, Text, TextInput, Title } from '@mantine/core';
import { IconPlus, IconSearch } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, errorText } from '../../api/client';
import type { ApplicationSummary, Company, Loan } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { RouteMap } from '../../components/RouteMap';
import { Schedule } from '../../components/Schedule';
import { Empty, Loading, Money, PageTitle, Plate, StatusBadge } from '../../components/ui';
import { date, money, months, pct, shortDate } from '../../lib/format';
import { appLink, miniStages } from './HomePage';

export function ApplicationsPage() {
  const { company } = useAuth();
  const q = useQuery({
    queryKey: ['applications', company?.id],
    queryFn: () => api.get<{ items: ApplicationSummary[] }>('/api/v1/applications', { company_id: company?.id }),
    enabled: !!company,
    refetchInterval: 6000,
  });
  const items = q.data?.items ?? [];
  const active = items.filter((a) => !a.terminal);
  const done = items.filter((a) => a.terminal);
  return (
    <Box>
      <PageTitle
        title="Заявки"
        sub={company?.short_name}
        right={
          <Button component={Link} to="/products" leftSection={<IconPlus size={16} />} visibleFrom="sm">
            Новая заявка
          </Button>
        }
      />
      {q.isLoading && <Loading />}
      {q.data && !items.length && (
        <Empty
          title="Заявок пока нет"
          text="Рассчитайте сумму и платёж под задачу бизнеса — заявка заполнится данными, которые уже известны банку."
          action={
            <Button component={Link} to="/products" color="brand">
              Рассчитать
            </Button>
          }
        />
      )}
      {active.length > 0 && (
        <Stack gap={10}>
          {active.map((a) => (
            <Link key={a.id} to={appLink(a)} className={`plate link${a.waiting === 'client' ? ' warn' : ''}`}>
              <Group justify="space-between" wrap="nowrap" align="flex-start" gap="md">
                <Box style={{ minWidth: 0 }}>
                  <Text fw={600}>{a.product_name}</Text>
                  <Text size="sm" c="dimmed" className="num">
                    {a.number} · {months(a.term_months)} · создана {shortDate(a.created_at)}
                  </Text>
                </Box>
                <Money value={a.offer?.amount ?? a.amount} size={22} />
              </Group>
              <Box mt={16} maw={560}>
                <RouteMap stages={miniStages(a.status)} waiting={a.waiting} compact />
              </Box>
              <Group justify="space-between" mt={12} gap="xs" wrap="wrap">
                <StatusBadge label={a.status_label} tone={a.status_tone} size="sm" pulse={a.waiting === 'system'} />
                {a.next_action && (
                  <Text size="sm" fw={a.waiting === 'client' ? 600 : 500} c={a.waiting === 'client' ? 'var(--warn-ink)' : 'dimmed'}>
                    {a.next_action}
                  </Text>
                )}
              </Group>
              {a.offer && (
                <Text size="sm" mt={8} className="num" c="var(--ink-2)">
                  Предложение: {money(a.offer.amount)} · {pct(a.offer.rate)} · {money(a.offer.monthly_payment)} в месяц{a.offer.is_counter ? ' · изменённые условия' : ''}
                </Text>
              )}
            </Link>
          ))}
        </Stack>
      )}
      {done.length > 0 && (
        <Box mt={40}>
          <Title order={3} mb={4}>
            Завершённые
          </Title>
          <div className="rows">
            {done.map((a) => (
              <Link key={a.id} to={appLink(a)} className="row">
                <Box style={{ flex: 1, minWidth: 0 }}>
                  <Text size="sm" fw={500} className="row-title" truncate>
                    {a.product_name}
                  </Text>
                  <Text size="xs" c="dimmed" className="num">
                    {a.number} · {shortDate(a.created_at)}
                  </Text>
                </Box>
                <Text size="sm" className="num" fw={500}>
                  {money(a.offer?.amount ?? a.amount)}
                </Text>
                <Box w={170} ta="right" visibleFrom="xs">
                  <StatusBadge label={a.status_label} tone={a.status_tone} size="sm" />
                </Box>
              </Link>
            ))}
          </div>
        </Box>
      )}
    </Box>
  );
}

export function LoansPage() {
  const { company } = useAuth();
  const q = useQuery({ queryKey: ['loans', company?.id], queryFn: () => api.get<{ items: Loan[] }>('/api/v1/loans', { company_id: company?.id }), enabled: !!company });
  return (
    <Box>
      <PageTitle title="Кредиты" sub="Действующие кредиты, ближайшие платежи и графики" />
      {q.isLoading && <Loading />}
      {q.data && !q.data.items.length && <Empty title="Действующих кредитов нет" text="Когда кредит будет выдан, здесь появятся ближайший платёж и график." />}
      {/* key: defaultValue применяется только при монтировании — монтируем после загрузки, чтобы первый кредит был раскрыт */}
      <Accordion key={q.data?.items[0]?.id ?? 'loading'} variant="separated" defaultValue={q.data?.items[0]?.id} chevronPosition="right">
        {q.data?.items.map((l) => (
          <Accordion.Item key={l.id} value={l.id}>
            <Accordion.Control py={10}>
              <Group justify="space-between" pr="md" wrap="wrap" gap="md">
                <Box>
                  <Text fw={600}>{l.product_name}</Text>
                  <Text size="sm" c="dimmed">
                    Договор {l.contract_number} от {date(l.issued_at)}
                  </Text>
                </Box>
                {l.next_payment && (
                  <Box ta="right">
                    <Text size="xs" c="dimmed">
                      Ближайший платёж {date(l.next_payment.date)}
                    </Text>
                    <Money value={l.next_payment.payment} size={22} />
                  </Box>
                )}
              </Group>
            </Accordion.Control>
            <Accordion.Panel>
              <SimpleGrid cols={{ base: 2, sm: 5 }} mb="lg" spacing="md">
                {[
                  ['Сумма', money(l.amount)],
                  ['Ставка', pct(l.rate, 2)],
                  ['Срок', months(l.term_months)],
                  ['Платёж', money(l.monthly_payment)],
                  ['Ссудный счёт', l.loan_account],
                ].map(([k, v]) => (
                  <Box key={k}>
                    <Text size="xs" c="dimmed">
                      {k}
                    </Text>
                    <Text size="sm" fw={600} className="num" truncate>
                      {v}
                    </Text>
                  </Box>
                ))}
              </SimpleGrid>
              <Box bg="#fff" p={{ base: 12, sm: 20 }} style={{ borderRadius: 16 }}>
                <Schedule rows={l.schedule} initial={12} />
              </Box>
              <Text size="xs" c="dimmed" mt="sm">
                Сопровождение кредита (платежи, досрочное погашение) — за пределами прототипа.
              </Text>
            </Accordion.Panel>
          </Accordion.Item>
        ))}
      </Accordion>
    </Box>
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
    <Box maw={640} mx="auto" mt={{ base: 0, sm: 24 }}>
      <Title order={1} fz={{ base: 28, sm: 36 }}>
        {companies.length ? 'Подключить ещё одну компанию' : 'Подключите компанию'}
      </Title>
      <Text c="dimmed" mt={10} fz={16}>
        Введите ИНН — реквизиты, адрес, ОКВЭД и руководителя подставим из ЕГРЮЛ/ЕГРИП. Вводить их вручную не придётся.
      </Text>
      <Group mt={28} align="flex-start" wrap="nowrap">
        <TextInput
          style={{ flex: 1 }}
          placeholder="10 цифр для ООО, 12 — для ИП"
          value={inn}
          onChange={(e) => setInn(e.currentTarget.value.replace(/\D/g, '').slice(0, 12))}
          onKeyDown={(e) => e.key === 'Enter' && connect()}
          leftSection={<IconSearch size={17} />}
          size="lg"
          error={error}
          aria-label="ИНН"
        />
        <Button size="lg" onClick={connect} loading={busy} disabled={![10, 12].includes(inn.length)}>
          Подключить
        </Button>
      </Group>
      <Plate size="sm" style={{ marginTop: 28 }}>
        <Text size="sm" fw={600}>
          Демо-стенд
        </Text>
        <Text size="sm" c="var(--ink-2)" mt={4}>
          Подойдёт любой корректный ИНН — симулятор реестров сгенерирует профиль компании. ИНН с префиксом 99 — пример «не найдено». В промышленной версии полномочия подтверждаются через Госуслуги или машиночитаемую доверенность.
        </Text>
      </Plate>
    </Box>
  );
}

export function NotFoundPage() {
  return (
    <Empty
      title="Страница не найдена"
      action={
        <Button component={Link} to="/">
          На главную
        </Button>
      }
    />
  );
}
