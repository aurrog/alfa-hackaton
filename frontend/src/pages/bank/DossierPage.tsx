import { Accordion, Alert, Badge, Box, Button, Card, Code, Grid, Group, List, Modal, MultiSelect, NumberInput, Progress, ScrollArea, SimpleGrid, Stack, Table, Tabs, Text, Textarea, Title, Tooltip } from '@mantine/core';
import { IconAlertTriangle, IconArrowBackUp, IconCheck, IconFileDescription, IconGavel, IconQuestionMark, IconRefresh, IconUserCheck, IconX } from '@tabler/icons-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, errorText } from '../../api/client';
import type { Dossier, Factor } from '../../api/types';
import { DocumentsList, StatementCard } from '../../components/Documents';
import { Timeline } from '../../components/Timeline';
import { ErrorAlert, KV, Loading, PageHeader, Section, Stat, StatusBadge } from '../../components/ui';
import { date, dateTime, money, months, pct, share, slaLeft } from '../../lib/format';
import { CHECK_RESULT, COLLATERAL, GRADE_COLOR, LEVELS, OUTCOME, PURPOSES, SOURCE_STATUS } from '../../lib/labels';

type Action = 'approve' | 'decline' | 'request_info' | 'escalate' | 'rerun' | 'return';
const ACTION_META: Record<Action, { label: string; color: string; icon: JSX.Element }> = {
  approve: { label: 'Одобрить', color: 'lime', icon: <IconCheck size={16} /> },
  decline: { label: 'Отказать', color: 'signal', icon: <IconX size={16} /> },
  request_info: { label: 'Запросить информацию', color: 'amber', icon: <IconQuestionMark size={16} /> },
  escalate: { label: 'Вынести на кредитный комитет', color: 'violet', icon: <IconGavel size={16} /> },
  rerun: { label: 'Перезапросить источники', color: 'route', icon: <IconRefresh size={16} /> },
  return: { label: 'Вернуть аналитику', color: 'gray', icon: <IconArrowBackUp size={16} /> },
};
const CAP_TITLE: Record<string, string> = {
  product_max: 'Максимум продукта', dscr: 'Посильность (DSCR)', turnover: 'Обороты × мультипликатор', collateral: 'Залог × дисконт', unsecured_limit: 'Лимит без залога',
};

function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      {text.split('\n').map((l, i) =>
        l.startsWith('# ') ? <h1 key={i}>{l.slice(2)}</h1> : l.startsWith('## ') ? <h2 key={i}>{l.slice(3)}</h2> : l.startsWith('- ') ? <li key={i}>{l.slice(2)}</li> : l.trim() ? <p key={i}>{l}</p> : null,
      )}
    </div>
  );
}

function DecisionModal({ d, action, onClose }: { d: Dossier; action: Action | null; onClose: () => void }) {
  const qc = useQueryClient();
  const app = d.application;
  const rec = d.recommendation ?? {};
  const [amount, setAmount] = useState<number | string>(rec.amount ?? app.amount);
  const [term, setTerm] = useState<number | string>(rec.term_months ?? app.term_months);
  const [rate, setRate] = useState<number | string>(rec.rate ?? '');
  const [conditions, setConditions] = useState<string>((rec.conditions ?? []).join('\n'));
  const [reasons, setReasons] = useState<string[]>((rec.reason_codes ?? []).map((r: { code: string }) => r.code));
  const [docs, setDocs] = useState<string[]>([]);
  const [question, setQuestion] = useState('');
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post<Dossier>(`/api/v1/bank/applications/${app.id}/decision`, { ...body, version: app.version }),
    onSuccess: (nd) => {
      qc.setQueryData(['dossier', app.id], nd);
      void qc.invalidateQueries({ queryKey: ['queue'] });
      void qc.invalidateQueries({ queryKey: ['bank-counts'] });
      onClose();
    },
    onError: (e) => setError(errorText(e)),
  });
  if (!action) return null;
  const override = (action === 'approve' && rec.outcome === 'decline') || (action === 'decline' && rec.outcome && rec.outcome !== 'decline');
  const submit = () => {
    setError(null);
    const body: Record<string, unknown> = { action, comment: comment || undefined };
    if (action === 'approve') Object.assign(body, { amount: Number(amount), term_months: Number(term), rate: rate === '' ? undefined : Number(rate), conditions: conditions.split('\n').map((s) => s.trim()).filter(Boolean) });
    if (action === 'decline') body.reason_codes = reasons;
    if (action === 'request_info') {
      body.info_requests = [...docs.map((dt) => ({ kind: 'document', doc_type: dt })), ...(question.trim() ? [{ kind: 'question', title: question.trim() }] : [])];
    }
    if (action === 'escalate') Object.assign(body, { amount: Number(amount), term_months: Number(term), rate: rate === '' ? undefined : Number(rate) });
    m.mutate(body);
  };
  return (
    <Modal opened onClose={onClose} title={<Text fw={700}>{ACTION_META[action].label}</Text>} size="lg" centered>
      <Stack>
        {(action === 'approve' || action === 'escalate') && (
          <>
            <SimpleGrid cols={3}>
              <NumberInput label="Сумма, ₽" value={amount} onChange={setAmount} max={app.amount} min={0} step={50_000} />
              <NumberInput label="Срок, мес." value={term} onChange={setTerm} min={1} max={120} />
              <NumberInput label="Ставка, %" value={rate} onChange={setRate} min={0} max={100} step={0.25} decimalScale={2} description="не ниже расчётной" />
            </SimpleGrid>
            {action === 'approve' && <Textarea label="Условия (по одному в строке)" value={conditions} onChange={(e) => setConditions(e.currentTarget.value)} autosize minRows={3} />}
          </>
        )}
        {action === 'decline' && (
          <MultiSelect label="Причины отказа (клиент увидит их формулировки)" data={d.reason_catalog.map((r: { code: string; text: string }) => ({ value: r.code, label: r.text }))} value={reasons} onChange={setReasons} searchable />
        )}
        {action === 'request_info' && (
          <>
            <MultiSelect label="Запросить документы" data={d.doc_types.map((t: { code: string; title: string }) => ({ value: t.code, label: t.title }))} value={docs} onChange={setDocs} />
            <Textarea label="Вопрос клиенту" placeholder="Например: поясните снижение поступлений в июле" value={question} onChange={(e) => setQuestion(e.currentTarget.value)} autosize minRows={2} />
            <Text size="xs" c="dimmed">
              Клиент получит задачи в кабинете; после ответа заявка автоматически пройдёт проверку заново.
            </Text>
          </>
        )}
        {override && (
          <Alert color="amber" variant="light" icon={<IconAlertTriangle size={18} />}>
            Решение расходится с рекомендацией движка — укажите обоснование (не короче 10 символов). Оно попадёт в журнал аудита.
          </Alert>
        )}
        <Textarea label={override ? 'Обоснование' : 'Комментарий'} value={comment} onChange={(e) => setComment(e.currentTarget.value)} autosize minRows={2} required={!!override} />
        {error && (
          <Alert color="signal" variant="light">
            {error}
          </Alert>
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Отмена
          </Button>
          <Button color={ACTION_META[action].color} leftSection={ACTION_META[action].icon} loading={m.isPending} onClick={submit}>
            {ACTION_META[action].label}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function FactorsTable({ factors }: { factors: Factor[] }) {
  return (
    <ScrollArea>
      <Table verticalSpacing={6} fz="sm" miw={640}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Фактор</Table.Th>
            <Table.Th>Значение</Table.Th>
            <Table.Th>Интервал</Table.Th>
            <Table.Th w={220}>Баллы</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {factors.map((f) => (
            <Table.Tr key={f.name}>
              <Table.Td>
                <Text size="sm" fw={600}>
                  {f.title}
                </Text>
                <Text size="xs" c="dimmed">
                  {f.source}
                </Text>
              </Table.Td>
              <Table.Td>{f.display_value}{f.missing && <Badge ml={6} size="xs" color="gray">нет данных</Badge>}</Table.Td>
              <Table.Td>{f.bin_label}</Table.Td>
              <Table.Td>
                <Group gap={8} wrap="nowrap">
                  <Progress value={Math.max((f.points / f.max_points) * 100, 0)} color={f.lost_points >= 30 ? 'signal' : f.lost_points >= 10 ? 'amber' : 'lime'} style={{ flex: 1 }} />
                  <Text size="xs" className="num" w={56} ta="right">
                    {f.points}/{f.max_points}
                  </Text>
                </Group>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </ScrollArea>
  );
}

function SourceFacts({ s }: { s: Dossier }) {
  const d = s.data ?? {};
  const facts: [string, string][] = [];
  if (s.source === 'egrul') facts.push(['Статус', d.status?.name], ['Руководитель', `${d.director?.full_name ?? '—'}${d.director?.since ? ` с ${date(d.director.since)}` : ''}`], ['ОКВЭД', `${d.okved_main?.code} ${d.okved_main?.name}`], ['Адрес', d.address?.full]);
  if (s.source === 'fns') facts.push(['Выручка за год', money(d.revenue)], ['Налоговая задолженность', money((d.tax_arrears?.amount ?? 0) + (d.tax_arrears?.penalties ?? 0))], ['Массовый адрес', d.mass_address ? 'да' : 'нет'], ['Блокировки счетов', d.blocked_accounts ? 'есть' : 'нет']);
  if (s.source === 'msp') facts.push(['В реестре МСП', d.in_registry ? 'да' : 'нет'], ['Категория', d.category ?? '—']);
  if (s.source === 'aml') facts.push(['Результат', d.result === 'hit' ? 'совпадение' : 'совпадений нет']);
  if (s.source.startsWith('bki')) facts.push(['Макс. просрочка за 24 мес.', `${d.max_overdue_days_24m ?? 0} дн.`], ['Запросов за 30 дней', String(d.inquiries_30d ?? 0)], ['Действующих кредитов', String(d.active_loans?.length ?? 0)], ['Платежи по кредитам', money((d.active_loans ?? []).reduce((a: number, l: { monthly_payment: number }) => a + (l.monthly_payment ?? 0), 0))]);
  if (s.source === 'abs_client' && d.turnover_by_month) facts.push(['Клиент с', date(d.client_since)], ['Средние поступления', money(d.turnover_by_month.reduce((a: number, m: { incoming: number }) => a + m.incoming, 0) / d.turnover_by_month.length)], ['Продукты банка', String(d.products?.length ?? 0)]);
  return facts.length ? <KV cols={2} items={facts} /> : null;
}

export function DossierPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const [action, setAction] = useState<Action | null>(null);
  const [tab, setTab] = useState<string | null>('decision');
  const q = useQuery({
    queryKey: ['dossier', id],
    queryFn: () => api.get<Dossier>(`/api/v1/bank/applications/${id}`),
    refetchInterval: (qq) => (['enrichment', 'scoring', 'data_check', 'submitted', 'disbursement'].includes(qq.state.data?.application?.status) ? 1500 : 10000),
  });
  const memo = useQuery({ queryKey: ['memo', id], queryFn: () => api.get<{ markdown: string; provider: string }>(`/api/v1/bank/applications/${id}/memo`), enabled: tab === 'memo' });
  const assign = useMutation({
    mutationFn: () => api.post<Dossier>(`/api/v1/bank/applications/${id}/assign`),
    onSuccess: (d) => qc.setQueryData(['dossier', id], d),
  });
  const review = useMutation({
    mutationFn: ({ docId, status }: { docId: string; status: string }) => api.post(`/api/v1/bank/documents/${docId}/review`, { status, comment: status === 'rejected' ? 'Документ нечитаем или не соответствует запросу' : undefined }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dossier', id] }),
  });
  if (q.isLoading) return <Loading text="Собираем досье…" />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const d = q.data!;
  const a = d.application;
  const c = d.company;
  const rec = d.recommendation;
  const sc = d.scoring;
  const aff = rec?.affordability;
  const sla = slaLeft(a.sla_due_at);
  const form = a.form ?? {};
  const actions: Action[] = (d.actions as string[]).filter((x) => x !== 'assign') as Action[];

  return (
    <Stack gap="lg">
      <PageHeader
        eyebrow={`Досье · ${a.number} · подана ${dateTime(a.submitted_at)}`}
        title={c.short_name}
        subtitle={`ИНН ${c.inn} · ${c.okved_code} ${c.okved_name} · ${c.is_bank_client ? `клиент банка с ${date(c.bank_client_since)}` : 'не клиент банка'}`}
        right={
          <Stack gap={4} align="flex-end">
            <StatusBadge label={a.status_label} tone={a.status_tone} size="lg" />
            {sla && <Text size="xs" c={sla.overdue ? 'signal' : 'dimmed'}>Норматив: {sla.text}</Text>}
            <Text size="xs" c="dimmed">Исполнитель: {a.assigned_name ?? 'не назначен'}</Text>
          </Stack>
        }
      />
      {(actions.length > 0 || d.actions.includes('assign')) && (
        <Card padding="md" style={{ position: 'sticky', top: 8, zIndex: 5 }}>
          <Group justify="space-between" wrap="wrap" gap="sm">
            <Text size="sm">
              Требуемый уровень: <b>{d.authority.required_level_title ?? '—'}</b> · ваши полномочия: <b>{d.authority.role_title}</b>
              {d.authority.limit ? ` до ${money(d.authority.limit)}` : ''}
            </Text>
            <Group gap="xs">
              {d.actions.includes('assign') && !a.assigned_to && (
                <Button variant="default" leftSection={<IconUserCheck size={16} />} onClick={() => assign.mutate()} loading={assign.isPending}>
                  Взять в работу
                </Button>
              )}
              {actions.map((x) => (
                <Button key={x} color={ACTION_META[x].color} variant={x === 'approve' ? 'filled' : 'light'} leftSection={ACTION_META[x].icon} onClick={() => setAction(x)} c={x === 'approve' ? 'ink.9' : undefined}>
                  {ACTION_META[x].label}
                </Button>
              ))}
            </Group>
          </Group>
        </Card>
      )}
      <SimpleGrid cols={{ base: 2, md: 4 }}>
        <Stat label="Запрос" value={money(a.amount)} hint={`${a.product.name}, ${months(a.term_months)} · ${PURPOSES[a.purpose]?.title ?? a.purpose}`} />
        <Stat label="Скоринг" value={sc ? `${sc.score} · ${sc.grade}` : '—'} hint={sc ? `PD ${share(sc.pd, 2)} · ${sc.model}` : 'ещё не рассчитан'} color={sc ? GRADE_COLOR[sc.grade] : undefined} />
        <Stat label="Рекомендация движка" value={rec ? (OUTCOME[rec.outcome]?.title ?? rec.outcome).split(' ')[0] : '—'} hint={rec && rec.outcome !== 'decline' ? `${money(rec.amount)} · ${months(rec.term_months)} · ${pct(rec.rate, 2)}` : rec ? 'см. причины' : ''} color={rec ? OUTCOME[rec.outcome]?.color : undefined} />
        <Stat label="Посильность (DSCR)" value={aff?.dscr_at_offer ? String(aff.dscr_at_offer).replace('.', ',') : '—'} hint={aff ? `минимум ${String(aff.min_dscr).replace('.', ',')} · ограничение: ${CAP_TITLE[aff.binding_cap] ?? aff.binding_cap}` : ''} />
      </SimpleGrid>
      {a.manual_reasons?.length > 0 && (
        <Alert color="violet" variant="light" title="Основания ручного рассмотрения">
          <List size="sm" spacing={2}>
            {a.manual_reasons.map((r: string) => (
              <List.Item key={r}>{r}</List.Item>
            ))}
          </List>
        </Alert>
      )}
      <Tabs value={tab} onChange={setTab} keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="decision">Рекомендация и расчёт</Tabs.Tab>
          <Tabs.Tab value="scoring">Скоринг</Tabs.Tab>
          <Tabs.Tab value="checks">Проверки</Tabs.Tab>
          <Tabs.Tab value="sources">Источники</Tabs.Tab>
          <Tabs.Tab value="form">Анкета и документы</Tabs.Tab>
          <Tabs.Tab value="log">Журнал</Tabs.Tab>
          <Tabs.Tab value="memo" leftSection={<IconFileDescription size={14} />}>
            Заключение
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="decision">
          {!rec ? (
            <Text c="dimmed">Рекомендация появится после скоринга.</Text>
          ) : (
            <Grid gutter="lg">
              <Grid.Col span={{ base: 12, md: 6 }}>
                <Section title="Рекомендация">
                  <Group gap={8}>
                    <Badge size="lg" color={OUTCOME[rec.outcome]?.color}>{OUTCOME[rec.outcome]?.title}</Badge>
                    <Badge size="lg" variant="outline" color="violet">{rec.level_title}</Badge>
                  </Group>
                  {rec.outcome !== 'decline' && (
                    <KV cols={2} items={[['Сумма', money(rec.amount)], ['Срок', months(rec.term_months)], ['Ставка', pct(rec.rate, 2)], ['Платёж', money(rec.monthly_payment)]]} />
                  )}
                  {rec.counter_changes?.length > 0 && (
                    <Alert color="amber" variant="light" mt="md" title="Контрпредложение">
                      <Stack gap={2}>{rec.counter_changes.map((x: string) => <Text key={x} size="sm">• {x}</Text>)}</Stack>
                    </Alert>
                  )}
                  {rec.reason_codes?.length > 0 && (
                    <Alert color="signal" variant="light" mt="md" title="Причины отказа">
                      <Stack gap={2}>{rec.reason_codes.map((r: { code: string; client_text: string; details: string }) => <Text key={r.code} size="sm">• <b>{r.code}</b>: {r.details}</Text>)}</Stack>
                    </Alert>
                  )}
                  {rec.conditions?.length > 0 && (
                    <Box mt="md">
                      <Text size="sm" fw={600}>Условия</Text>
                      <List size="sm">{rec.conditions.map((x: string) => <List.Item key={x}>{x}</List.Item>)}</List>
                    </Box>
                  )}
                  <Text size="xs" c="dimmed" mt="md">
                    Политика v{rec.policy_version} · модель {rec.model_version} · {dateTime(rec.created_at)}
                  </Text>
                </Section>
              </Grid.Col>
              <Grid.Col span={{ base: 12, md: 6 }}>
                {aff && (
                  <Section title="Расчёт посильной суммы">
                    <Table fz="sm" verticalSpacing={4}>
                      <Table.Tbody>
                        <Table.Tr><Table.Td>Подтверждённая выручка в месяц</Table.Td><Table.Td ta="right" className="num">{money(aff.monthly_revenue)}</Table.Td></Table.Tr>
                        <Table.Tr><Table.Td c="dimmed">источник</Table.Td><Table.Td ta="right">{aff.revenue_source}</Table.Td></Table.Tr>
                        <Table.Tr><Table.Td>× отраслевая маржинальность</Table.Td><Table.Td ta="right">{share(aff.sector_margin, 0)}</Table.Td></Table.Tr>
                        <Table.Tr><Table.Td>= операционный денежный поток</Table.Td><Table.Td ta="right" className="num">{money(aff.operating_cash_flow)}</Table.Td></Table.Tr>
                        <Table.Tr><Table.Td>÷ минимальный DSCR</Table.Td><Table.Td ta="right">{String(aff.min_dscr).replace('.', ',')}</Table.Td></Table.Tr>
                        <Table.Tr><Table.Td>− текущие платежи по кредитам</Table.Td><Table.Td ta="right" className="num">{money(aff.existing_payments)}</Table.Td></Table.Tr>
                        <Table.Tr><Table.Td fw={700}>= посильный новый платёж</Table.Td><Table.Td ta="right" fw={700} className="num">{money(aff.max_new_payment)}</Table.Td></Table.Tr>
                      </Table.Tbody>
                    </Table>
                    <Text size="sm" fw={600} mt="md" mb={4}>Ограничения суммы</Text>
                    {Object.entries(aff.caps as Record<string, number>).map(([k, v]) => (
                      <Group key={k} justify="space-between">
                        <Text size="sm" fw={k === aff.binding_cap ? 700 : 400}>{CAP_TITLE[k] ?? k}{k === aff.binding_cap ? ' — ограничивает' : ''}</Text>
                        <Text size="sm" className="num" fw={k === aff.binding_cap ? 700 : 400}>{money(v)}</Text>
                      </Group>
                    ))}
                    <Group justify="space-between" mt={6}>
                      <Text size="sm" fw={700}>Максимум к одобрению</Text>
                      <Text size="sm" fw={700} className="num">{money(aff.approved_max)}</Text>
                    </Group>
                  </Section>
                )}
                {rec.explanation && (
                  <Section title="Объяснение оценки" mt="lg">
                    <SimpleGrid cols={2}>
                      <Box>
                        <Text size="sm" fw={600} c="lime.8">Повышают</Text>
                        {rec.explanation.positives.map((p: { title: string; value: string }) => <Text key={p.title} size="sm">• {p.title}: {p.value}</Text>)}
                      </Box>
                      <Box>
                        <Text size="sm" fw={600} c="signal">Снижают</Text>
                        {rec.explanation.negatives.map((p: { title: string; value: string; lost_points: number }) => <Text key={p.title} size="sm">• {p.title}: {p.value} (−{p.lost_points})</Text>)}
                      </Box>
                    </SimpleGrid>
                  </Section>
                )}
              </Grid.Col>
            </Grid>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="scoring">
          {sc ? (
            <Section title={`Скоринговая карта: ${sc.score} баллов, грейд ${sc.grade}, PD ${share(sc.pd, 2)}`} right={<Badge variant="outline">{sc.model}</Badge>}>
              <FactorsTable factors={sc.factors} />
              <Text size="xs" c="dimmed" mt="sm">
                Баллы по 10 факторам (WOE-интервалы). «Потерянные» баллы относительно лучшего интервала объясняют грейд клиенту и аналитику.
              </Text>
            </Section>
          ) : (
            <Text c="dimmed">Скоринг ещё не выполнен.</Text>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="checks">
          <Section title="Проверки">
            <Table fz="sm" verticalSpacing={6}>
              <Table.Thead><Table.Tr><Table.Th>Проверка</Table.Th><Table.Th>Результат</Table.Th><Table.Th>Детали</Table.Th><Table.Th>Источник</Table.Th></Table.Tr></Table.Thead>
              <Table.Tbody>
                {d.checks.map((ch: Dossier, i: number) => (
                  <Table.Tr key={i}>
                    <Table.Td><Text size="sm" fw={600}>{ch.title}</Text><Text size="xs" c="dimmed">{ch.stage === 'validation' ? 'полнота данных' : 'кредитная политика'}</Text></Table.Td>
                    <Table.Td><Badge color={CHECK_RESULT[ch.result]?.color}>{CHECK_RESULT[ch.result]?.title ?? ch.result}</Badge>{ch.effect && <Badge ml={4} variant="outline" color={ch.effect === 'stop' ? 'signal' : 'violet'}>{ch.effect === 'stop' ? 'стоп-фактор' : 'ручная проверка'}</Badge>}</Table.Td>
                    <Table.Td>{ch.details}</Table.Td>
                    <Table.Td>{ch.source}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Section>
        </Tabs.Panel>

        <Tabs.Panel value="sources">
          <Stack>
            <Accordion variant="separated" radius="lg" multiple>
              {d.sources.map((s: Dossier) => (
                <Accordion.Item key={s.source} value={s.source}>
                  <Accordion.Control>
                    <Group justify="space-between" pr="md">
                      <Text fw={600}>{s.title}</Text>
                      <Group gap={6}>
                        {s.at && <Text size="xs" c="dimmed">{dateTime(s.at)}</Text>}
                        <Badge color={SOURCE_STATUS[s.status]?.color}>{SOURCE_STATUS[s.status]?.title ?? s.status}</Badge>
                      </Group>
                    </Group>
                  </Accordion.Control>
                  <Accordion.Panel>
                    {s.error && <Alert color="signal" variant="light" mb="sm">{s.error}</Alert>}
                    <SourceFacts s={s} />
                    {s.data && (
                      <Code block mt="sm" mah={260} style={{ overflow: 'auto' }}>
                        {JSON.stringify(s.data, null, 2)}
                      </Code>
                    )}
                  </Accordion.Panel>
                </Accordion.Item>
              ))}
            </Accordion>
            <Section title="Журнал вызовов источников">
              <ScrollArea>
                <Table fz="xs" verticalSpacing={4} miw={700}>
                  <Table.Thead><Table.Tr><Table.Th>Время</Table.Th><Table.Th>Источник</Table.Th><Table.Th>Результат</Table.Th><Table.Th>Попытка</Table.Th><Table.Th>HTTP</Table.Th><Table.Th>мс</Table.Th><Table.Th>Ошибка</Table.Th></Table.Tr></Table.Thead>
                  <Table.Tbody>
                    {d.integration_calls.map((ic: Dossier) => (
                      <Table.Tr key={ic.id}>
                        <Table.Td>{dateTime(ic.created_at)}</Table.Td>
                        <Table.Td>{ic.title}</Table.Td>
                        <Table.Td><Badge size="xs" color={SOURCE_STATUS[ic.status]?.color}>{SOURCE_STATUS[ic.status]?.title ?? ic.status}</Badge></Table.Td>
                        <Table.Td>{ic.attempt}</Table.Td>
                        <Table.Td>{ic.http_status ?? '—'}</Table.Td>
                        <Table.Td className="num">{ic.duration_ms}</Table.Td>
                        <Table.Td><Tooltip label={ic.error ?? ''} disabled={!ic.error}><Text size="xs" truncate maw={220}>{ic.error ?? ''}</Text></Tooltip></Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </ScrollArea>
            </Section>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="form">
          <Grid gutter="lg">
            <Grid.Col span={{ base: 12, md: 6 }}>
              <Section title="Анкета">
                <Stack gap="md">
                  <KV items={[['Контакт', `${form.contact?.name ?? '—'}, ${form.contact?.phone ?? ''}`], ['Руководитель (анкета)', form.company?.director_name], ['Руководитель (ЕГРЮЛ)', c.director_name], ['Сотрудников', form.company?.employees]]} />
                  <KV items={[['Выручка в месяц (заявлено)', money(form.financials?.monthly_revenue)], ['Выручка за год', money(form.financials?.revenue_last_year)], ['Платежи по кредитам', money(form.financials?.existing_loans_monthly_payment)], ['Цель', a.purpose_text ?? PURPOSES[a.purpose]?.title]]} />
                  <KV items={[['Залог', COLLATERAL[form.collateral?.type ?? 'none']], ['Стоимость залога', money(form.collateral?.value)], ['Поручитель', form.guarantor?.full_name ?? '—'], ['ИНН поручителя', form.guarantor?.inn ?? '—']]} />
                </Stack>
              </Section>
              {a.statement && (
                <Section title="Выписка" mt="lg">
                  <StatementCard st={a.statement} />
                </Section>
              )}
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <Section title="Документы">
                <DocumentsList appId={a.id} docs={d.documents} bank />
                {d.documents.filter((x: Dossier) => x.status === 'uploaded').length > 0 && actions.length > 0 && (
                  <Stack gap={4} mt="sm">
                    {d.documents.filter((x: Dossier) => x.status === 'uploaded').map((x: Dossier) => (
                      <Group key={x.id} justify="space-between">
                        <Text size="xs">{x.file_name}</Text>
                        <Group gap={4}>
                          <Button size="compact-xs" color="lime" variant="light" onClick={() => review.mutate({ docId: x.id, status: 'accepted' })}>Принять</Button>
                          <Button size="compact-xs" color="signal" variant="light" onClick={() => review.mutate({ docId: x.id, status: 'rejected' })}>Отклонить</Button>
                        </Group>
                      </Group>
                    ))}
                  </Stack>
                )}
              </Section>
              {d.tasks.length > 0 && (
                <Section title="Запросы клиенту" mt="lg">
                  <Stack gap={6}>
                    {d.tasks.map((t: Dossier) => (
                      <Box key={t.id}>
                        <Group gap={6}><Text size="sm" fw={600}>{t.title}</Text><Badge size="xs" color={t.status === 'open' ? 'amber' : 'lime'}>{t.status === 'open' ? 'ожидает' : t.status === 'answered' ? 'выполнено' : t.status}</Badge></Group>
                        {t.answer_text && <Text size="xs" c="dimmed">Ответ: {t.answer_text}</Text>}
                      </Box>
                    ))}
                  </Stack>
                </Section>
              )}
            </Grid.Col>
          </Grid>
        </Tabs.Panel>

        <Tabs.Panel value="log">
          <Grid gutter="lg">
            <Grid.Col span={{ base: 12, md: 7 }}>
              <Section title="События заявки">
                <Timeline events={d.events} />
              </Section>
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 5 }}>
              <Section title="Решения">
                <Stack gap="sm">
                  {d.decisions.map((x: Dossier) => (
                    <Box key={x.id}>
                      <Group gap={6}>
                        <Badge color={OUTCOME[x.outcome]?.color}>{x.kind === 'recommendation' ? 'рекомендация' : 'решение'}: {OUTCOME[x.outcome]?.title ?? x.outcome}</Badge>
                        <Text size="xs" c="dimmed">{LEVELS[x.level] ?? x.level}</Text>
                      </Group>
                      <Text size="xs" c="dimmed">{x.decided_by_name ?? '—'} · {dateTime(x.created_at)} · политика v{x.policy_version}</Text>
                      {x.comment && <Text size="xs">{x.comment}</Text>}
                    </Box>
                  ))}
                </Stack>
              </Section>
              {d.signatures.length > 0 && (
                <Section title="Подписи (ПЭП)" mt="lg">
                  {d.signatures.map((s: Dossier) => (
                    <Box key={s.document_hash + s.document_kind} mb={6}>
                      <Text size="sm" fw={600}>{s.document_title}</Text>
                      <Text size="xs" c="dimmed">{s.signer_name} · {dateTime(s.signed_at)} · IP {s.ip ?? '—'}</Text>
                    </Box>
                  ))}
                </Section>
              )}
            </Grid.Col>
          </Grid>
        </Tabs.Panel>

        <Tabs.Panel value="memo">
          <Section title="Черновик кредитного заключения" right={memo.data && <Badge variant="outline">{memo.data.provider === 'llm' ? 'LLM (открытые веса)' : 'шаблон по данным досье'}</Badge>}>
            {memo.isLoading ? <Loading text="Готовим заключение…" /> : memo.data ? <Markdown text={memo.data.markdown} /> : null}
            <Text size="xs" c="dimmed" mt="md">
              Все цифры берутся из досье. Заключение — черновик: решение принимает специалист.
            </Text>
          </Section>
        </Tabs.Panel>
      </Tabs>
      <DecisionModal key={action ?? 'none'} d={d} action={action} onClose={() => setAction(null)} />
      <Title order={4} c="dimmed" fw={400} fz="xs">
        Просмотр досье фиксируется в журнале аудита.
      </Title>
    </Stack>
  );
}
