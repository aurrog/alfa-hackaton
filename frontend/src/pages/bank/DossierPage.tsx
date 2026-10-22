import { Accordion, Alert, Box, Button, Code, Grid, Group, List, Modal, MultiSelect, NumberInput, Progress, ScrollArea, SimpleGrid, Stack, Table, Tabs, Text, Textarea, Title, Tooltip } from '@mantine/core';
import { IconAlertTriangle, IconArrowBackUp, IconCheck, IconFileDescription, IconGavel, IconQuestionMark, IconRefresh, IconUserCheck, IconX } from '@tabler/icons-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, errorText } from '../../api/client';
import type { Dossier, Factor } from '../../api/types';
import { DocumentsList, StatementCard } from '../../components/Documents';
import { Timeline } from '../../components/Timeline';
import { BackLink, ErrorAlert, GradeChip, InlineLoading, KV, Loading, Money, Plate, Section, Stat, Status, StatusBadge, Tag } from '../../components/ui';
import { date, dateTime, money, months, pct, share, slaLeft } from '../../lib/format';
import { CHECK_RESULT, COLLATERAL, LEVELS, OUTCOME, PURPOSES, SOURCE_STATUS } from '../../lib/labels';

type Action = 'approve' | 'decline' | 'request_info' | 'escalate' | 'rerun' | 'return';
const ACTION_META: Record<Action, { label: string; color: string; variant: string; icon: JSX.Element }> = {
  approve: { label: 'Одобрить', color: 'ok', variant: 'filled', icon: <IconCheck size={16} /> },
  decline: { label: 'Отказать', color: 'bad', variant: 'light', icon: <IconX size={16} /> },
  request_info: { label: 'Запросить информацию', color: 'ink', variant: 'default', icon: <IconQuestionMark size={16} /> },
  escalate: { label: 'На кредитный комитет', color: 'ink', variant: 'default', icon: <IconGavel size={16} /> },
  rerun: { label: 'Перезапросить источники', color: 'ink', variant: 'default', icon: <IconRefresh size={16} /> },
  return: { label: 'Вернуть аналитику', color: 'ink', variant: 'default', icon: <IconArrowBackUp size={16} /> },
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
  const meta = ACTION_META[action];
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
    <Modal opened onClose={onClose} title={meta.label} size="lg">
      <Stack>
        {(action === 'approve' || action === 'escalate') && (
          <>
            <SimpleGrid cols={{ base: 1, sm: 3 }}>
              <NumberInput label="Сумма, ₽" value={amount} onChange={setAmount} max={app.amount} min={0} step={50_000} />
              <NumberInput label="Срок, мес." value={term} onChange={setTerm} min={1} max={120} />
              <NumberInput label="Ставка, %" value={rate} onChange={setRate} min={0} max={100} step={0.25} decimalScale={2} description="не ниже расчётной" />
            </SimpleGrid>
            {action === 'approve' && <Textarea label="Условия — по одному в строке" value={conditions} onChange={(e) => setConditions(e.currentTarget.value)} autosize minRows={3} />}
          </>
        )}
        {action === 'decline' && (
          <MultiSelect label="Причины отказа — клиент увидит их формулировки" data={d.reason_catalog.map((r: { code: string; text: string }) => ({ value: r.code, label: r.text }))} value={reasons} onChange={setReasons} searchable />
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
          <Alert color="warn" icon={<IconAlertTriangle size={18} />}>
            Решение расходится с рекомендацией движка — укажите обоснование (не короче 10 символов). Оно попадёт в журнал аудита.
          </Alert>
        )}
        <Textarea label={override ? 'Обоснование' : 'Комментарий'} value={comment} onChange={(e) => setComment(e.currentTarget.value)} autosize minRows={2} required={!!override} />
        {error && <Alert color="bad">{error}</Alert>}
        <Group justify="flex-end" gap="sm">
          <Button variant="default" onClick={onClose}>
            Отмена
          </Button>
          <Button color={meta.color === 'ink' ? 'ink' : meta.color} leftSection={meta.icon} loading={m.isPending} onClick={submit}>
            {meta.label}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function FactorsTable({ factors }: { factors: Factor[] }) {
  return (
    <ScrollArea>
      <Table miw={680} verticalSpacing={10}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Фактор</Table.Th>
            <Table.Th>Значение</Table.Th>
            <Table.Th>Интервал</Table.Th>
            <Table.Th w={240}>Баллы</Table.Th>
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
              <Table.Td>
                <Group gap={6} wrap="nowrap">
                  <Text size="sm">{f.display_value}</Text>
                  {f.missing && <Tag>нет данных</Tag>}
                </Group>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{f.bin_label}</Text>
              </Table.Td>
              <Table.Td>
                <Group gap={10} wrap="nowrap">
                  <Progress value={Math.max((f.points / f.max_points) * 100, 0)} color={f.lost_points >= 30 ? 'bad' : f.lost_points >= 10 ? 'warn' : 'ok'} style={{ flex: 1 }} size="md" />
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

function Row({ k, v, strong, muted }: { k: string; v: string; strong?: boolean; muted?: boolean }) {
  return (
    <Group justify="space-between" py={7} wrap="nowrap" gap="md">
      <Text size="sm" fw={strong ? 700 : 400} c={muted ? 'dimmed' : undefined}>
        {k}
      </Text>
      <Text size="sm" fw={strong ? 700 : 500} className="num" ta="right">
        {v}
      </Text>
    </Group>
  );
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
  const outcome = rec ? OUTCOME[rec.outcome] : null;

  return (
    <Box>
      <BackLink to="/bank">Очередь</BackLink>
      <Group justify="space-between" align="flex-end" mt={10} mb={24} wrap="wrap" gap="md">
        <Box style={{ minWidth: 0 }}>
          <Text size="sm" c="dimmed">
            Досье · {a.number} · подана {dateTime(a.submitted_at)}
          </Text>
          <Title order={1} fz={{ base: 26, sm: 34 }} mt={4}>
            {c.short_name}
          </Title>
          <Text c="var(--ink-2)" mt={6}>
            ИНН {c.inn} · {c.okved_code} {c.okved_name} · {c.is_bank_client ? `клиент банка с ${date(c.bank_client_since)}` : 'не клиент банка'}
          </Text>
        </Box>
        <Stack gap={6} align="flex-end">
          <StatusBadge label={a.status_label} tone={a.status_tone} />
          {sla && (
            <Text size="sm" c={sla.overdue ? 'bad' : 'dimmed'}>
              Норматив: {sla.text}
            </Text>
          )}
          <Text size="sm" c="dimmed">
            Исполнитель: {a.assigned_name ?? 'не назначен'}
          </Text>
        </Stack>
      </Group>

      {(actions.length > 0 || d.actions.includes('assign')) && (
        <Box pos="sticky" top={0} py={12} mb={20} bg="#fff" style={{ zIndex: 5, borderBottom: '1px solid var(--line)' }}>
          <Group justify="space-between" wrap="wrap" gap="sm">
            <Text size="sm" c="var(--ink-2)">
              Нужный уровень: <b>{d.authority.required_level_title ?? '—'}</b> · ваши полномочия: <b>{d.authority.role_title}</b>
              {d.authority.limit ? ` до ${money(d.authority.limit)}` : ''}
            </Text>
            <Group gap="xs">
              {d.actions.includes('assign') && !a.assigned_to && (
                <Button variant="default" leftSection={<IconUserCheck size={16} />} onClick={() => assign.mutate()} loading={assign.isPending}>
                  Взять в работу
                </Button>
              )}
              {actions.map((x) => (
                <Button key={x} color={ACTION_META[x].color} variant={ACTION_META[x].variant} leftSection={ACTION_META[x].icon} onClick={() => setAction(x)}>
                  {ACTION_META[x].label}
                </Button>
              ))}
            </Group>
          </Group>
        </Box>
      )}

      <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }} spacing="md" className="enter">
        <Plate size="sm">
          <Text size="sm" c="dimmed">
            Запрос
          </Text>
          <Money value={a.amount} size={26} />
          <Text size="xs" c="dimmed" mt={6}>
            {a.product.name}, {months(a.term_months)} · {PURPOSES[a.purpose]?.title ?? a.purpose}
          </Text>
        </Plate>
        <Plate size="sm">
          <Text size="sm" c="dimmed">
            Скоринг
          </Text>
          <Group gap={10} mt={4} wrap="nowrap">
            {sc && <GradeChip grade={sc.grade} size={30} />}
            <Text fz={26} fw={700} className="display num" lh={1.1}>
              {sc ? sc.score : '—'}
            </Text>
          </Group>
          <Text size="xs" c="dimmed" mt={6}>
            {sc ? `PD ${share(sc.pd, 2)} · ${sc.model}` : 'ещё не рассчитан'}
          </Text>
        </Plate>
        <Plate size="sm">
          <Text size="sm" c="dimmed">
            Рекомендация движка
          </Text>
          <Box mt={6}>{outcome ? <Status tone={outcome.color}><Text span fw={700} fz={18} className="display">{outcome.short}</Text></Status> : <Text fz={26} fw={700}>—</Text>}</Box>
          <Text size="xs" c="dimmed" mt={8}>
            {rec && rec.outcome !== 'decline' ? `${money(rec.amount)} · ${months(rec.term_months)} · ${pct(rec.rate, 2)}` : rec ? 'см. причины ниже' : ''}
          </Text>
        </Plate>
        <Stat
          label="Посильность (DSCR)"
          value={aff?.dscr_at_offer ? String(aff.dscr_at_offer).replace('.', ',') : '—'}
          hint={aff ? `минимум ${String(aff.min_dscr).replace('.', ',')} · ограничение: ${CAP_TITLE[aff.binding_cap] ?? aff.binding_cap}` : ''}
        />
      </SimpleGrid>

      {a.manual_reasons?.length > 0 && (
        <Plate tone="info" size="sm" style={{ marginTop: 16 }}>
          <Text size="sm" fw={600}>
            Почему заявка у специалиста
          </Text>
          <List size="sm" spacing={2} mt={4}>
            {a.manual_reasons.map((r: string) => (
              <List.Item key={r}>{r}</List.Item>
            ))}
          </List>
        </Plate>
      )}

      <Tabs value={tab} onChange={setTab} keepMounted={false} mt={28}>
        <ScrollArea type="never">
          <Tabs.List mb="lg" style={{ flexWrap: 'nowrap' }}>
            <Tabs.Tab value="decision">Рекомендация и расчёт</Tabs.Tab>
            <Tabs.Tab value="scoring">Скоринг</Tabs.Tab>
            <Tabs.Tab value="checks">Проверки</Tabs.Tab>
            <Tabs.Tab value="sources">Источники</Tabs.Tab>
            <Tabs.Tab value="form">Анкета и документы</Tabs.Tab>
            <Tabs.Tab value="log">Журнал</Tabs.Tab>
            <Tabs.Tab value="memo" leftSection={<IconFileDescription size={15} />}>
              Заключение
            </Tabs.Tab>
          </Tabs.List>
        </ScrollArea>

        <Tabs.Panel value="decision">
          {!rec ? (
            <Text c="dimmed">Рекомендация появится после скоринга.</Text>
          ) : (
            <Grid gutter="lg">
              <Grid.Col span={{ base: 12, md: 6 }}>
                <Plate>
                  <Group justify="space-between" wrap="wrap" gap="xs">
                    <Title order={3}>Рекомендация</Title>
                    <Tag tone="info">{rec.level_title}</Tag>
                  </Group>
                  <Box mt="sm">
                    <Status tone={outcome?.color}>{outcome?.title}</Status>
                  </Box>
                  {rec.outcome !== 'decline' && (
                    <Box mt="md">
                      <KV cols={2} items={[['Сумма', money(rec.amount)], ['Срок', months(rec.term_months)], ['Ставка', pct(rec.rate, 2)], ['Платёж', money(rec.monthly_payment)]]} />
                    </Box>
                  )}
                  {rec.counter_changes?.length > 0 && (
                    <Plate tone="warn" size="sm" style={{ marginTop: 16 }}>
                      <Text size="sm" fw={600}>
                        Контрпредложение
                      </Text>
                      <Stack gap={2} mt={4}>
                        {rec.counter_changes.map((x: string) => (
                          <Text key={x} size="sm">
                            {x}
                          </Text>
                        ))}
                      </Stack>
                    </Plate>
                  )}
                  {rec.reason_codes?.length > 0 && (
                    <Plate tone="bad" size="sm" style={{ marginTop: 16 }}>
                      <Text size="sm" fw={600}>
                        Причины отказа
                      </Text>
                      <Stack gap={4} mt={4}>
                        {rec.reason_codes.map((r: { code: string; client_text: string; details: string }) => (
                          <Text key={r.code} size="sm">
                            <b>{r.code}</b> — {r.details}
                          </Text>
                        ))}
                      </Stack>
                    </Plate>
                  )}
                  {rec.conditions?.length > 0 && (
                    <Box mt="md">
                      <Text size="sm" fw={600}>
                        Условия
                      </Text>
                      <List size="sm" spacing={2} mt={4}>
                        {rec.conditions.map((x: string) => (
                          <List.Item key={x}>{x}</List.Item>
                        ))}
                      </List>
                    </Box>
                  )}
                  <Text size="xs" c="dimmed" mt="md">
                    Политика v{rec.policy_version} · модель {rec.model_version} · {dateTime(rec.created_at)}
                  </Text>
                </Plate>
                {rec.explanation && (
                  <Plate style={{ marginTop: 16 }}>
                    <Title order={3}>Объяснение оценки</Title>
                    <SimpleGrid cols={{ base: 1, sm: 2 }} mt="sm">
                      <Box>
                        <Text size="sm" fw={600} c="ok">
                          Повышают
                        </Text>
                        <Stack gap={3} mt={4}>
                          {rec.explanation.positives.map((p: { title: string; value: string }) => (
                            <Text key={p.title} size="sm">
                              {p.title}: {p.value}
                            </Text>
                          ))}
                        </Stack>
                      </Box>
                      <Box>
                        <Text size="sm" fw={600} c="bad">
                          Снижают
                        </Text>
                        <Stack gap={3} mt={4}>
                          {rec.explanation.negatives.map((p: { title: string; value: string; lost_points: number }) => (
                            <Text key={p.title} size="sm">
                              {p.title}: {p.value} <Text span c="dimmed">(−{p.lost_points})</Text>
                            </Text>
                          ))}
                        </Stack>
                      </Box>
                    </SimpleGrid>
                  </Plate>
                )}
              </Grid.Col>
              <Grid.Col span={{ base: 12, md: 6 }}>
                {aff && (
                  <Plate>
                    <Title order={3}>Расчёт посильной суммы</Title>
                    <div className="rows" style={{ marginTop: 10 }}>
                      <Row k="Подтверждённая выручка в месяц" v={money(aff.monthly_revenue)} />
                      <Row k="источник" v={aff.revenue_source} muted />
                      <Row k="× отраслевая маржинальность" v={share(aff.sector_margin, 0)} />
                      <Row k="= операционный денежный поток" v={money(aff.operating_cash_flow)} />
                      <Row k="÷ минимальный DSCR" v={String(aff.min_dscr).replace('.', ',')} />
                      <Row k="− текущие платежи по кредитам" v={money(aff.existing_payments)} />
                      <Row k="= посильный новый платёж" v={money(aff.max_new_payment)} strong />
                    </div>
                    <Text size="sm" fw={600} mt="lg" mb={2}>
                      Ограничения суммы
                    </Text>
                    <div className="rows">
                      {Object.entries(aff.caps as Record<string, number>).map(([k, v]) => (
                        <Row key={k} k={`${CAP_TITLE[k] ?? k}${k === aff.binding_cap ? ' — ограничивает' : ''}`} v={money(v)} strong={k === aff.binding_cap} />
                      ))}
                      <Row k="Максимум к одобрению" v={money(aff.approved_max)} strong />
                    </div>
                  </Plate>
                )}
              </Grid.Col>
            </Grid>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="scoring">
          {sc ? (
            <Section title={`Скоринговая карта: ${sc.score} баллов, грейд ${sc.grade}, PD ${share(sc.pd, 2)}`} right={<Tag>{sc.model}</Tag>}>
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
          <ScrollArea>
            <Table miw={760} verticalSpacing={10}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Проверка</Table.Th>
                  <Table.Th>Результат</Table.Th>
                  <Table.Th>Детали</Table.Th>
                  <Table.Th>Источник</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {d.checks.map((ch: Dossier, i: number) => (
                  <Table.Tr key={i}>
                    <Table.Td>
                      <Text size="sm" fw={600}>
                        {ch.title}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {ch.stage === 'validation' ? 'полнота данных' : 'кредитная политика'}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Stack gap={4}>
                        <Status tone={CHECK_RESULT[ch.result]?.color} size="sm">
                          {CHECK_RESULT[ch.result]?.title ?? ch.result}
                        </Status>
                        {ch.effect && <Tag tone={ch.effect === 'stop' ? 'bad' : 'info'}>{ch.effect === 'stop' ? 'стоп-фактор' : 'ручная проверка'}</Tag>}
                      </Stack>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{ch.details}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed">
                        {ch.source}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        </Tabs.Panel>

        <Tabs.Panel value="sources">
          <Stack gap="lg">
            <Accordion variant="separated" multiple>
              {d.sources.map((s: Dossier) => (
                <Accordion.Item key={s.source} value={s.source}>
                  <Accordion.Control>
                    <Group justify="space-between" pr="md" wrap="nowrap">
                      <Text fw={600} size="sm">
                        {s.title}
                      </Text>
                      <Group gap={12} wrap="nowrap">
                        {s.at && (
                          <Text size="xs" c="dimmed" visibleFrom="sm">
                            {dateTime(s.at)}
                          </Text>
                        )}
                        <Status tone={SOURCE_STATUS[s.status]?.color} size="sm">
                          {SOURCE_STATUS[s.status]?.title ?? s.status}
                        </Status>
                      </Group>
                    </Group>
                  </Accordion.Control>
                  <Accordion.Panel>
                    {s.error && (
                      <Alert color="bad" mb="sm">
                        {s.error}
                      </Alert>
                    )}
                    <SourceFacts s={s} />
                    {s.data && (
                      <Code block mt="sm" mah={260} style={{ overflow: 'auto', background: '#fff' }}>
                        {JSON.stringify(s.data, null, 2)}
                      </Code>
                    )}
                  </Accordion.Panel>
                </Accordion.Item>
              ))}
            </Accordion>
            <Section title="Журнал вызовов источников">
              <ScrollArea>
                <Table fz="xs" verticalSpacing={6} miw={760}>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Время</Table.Th>
                      <Table.Th>Источник</Table.Th>
                      <Table.Th>Результат</Table.Th>
                      <Table.Th>Попытка</Table.Th>
                      <Table.Th>HTTP</Table.Th>
                      <Table.Th>мс</Table.Th>
                      <Table.Th>Ошибка</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {d.integration_calls.map((ic: Dossier) => (
                      <Table.Tr key={ic.id}>
                        <Table.Td>{dateTime(ic.created_at)}</Table.Td>
                        <Table.Td>{ic.title}</Table.Td>
                        <Table.Td>
                          <Status tone={SOURCE_STATUS[ic.status]?.color} size="sm">
                            {SOURCE_STATUS[ic.status]?.title ?? ic.status}
                          </Status>
                        </Table.Td>
                        <Table.Td>{ic.attempt}</Table.Td>
                        <Table.Td>{ic.http_status ?? '—'}</Table.Td>
                        <Table.Td className="num">{ic.duration_ms}</Table.Td>
                        <Table.Td>
                          <Tooltip label={ic.error ?? ''} disabled={!ic.error}>
                            <Text size="xs" truncate maw={220}>
                              {ic.error ?? ''}
                            </Text>
                          </Tooltip>
                        </Table.Td>
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
              <Plate>
                <Title order={3} mb="md">
                  Анкета
                </Title>
                <Stack gap="lg">
                  <KV items={[['Контакт', `${form.contact?.name ?? '—'}, ${form.contact?.phone ?? ''}`], ['Руководитель (анкета)', form.company?.director_name], ['Руководитель (ЕГРЮЛ)', c.director_name], ['Сотрудников', form.company?.employees]]} />
                  <KV items={[['Выручка в месяц (заявлено)', money(form.financials?.monthly_revenue)], ['Выручка за год', money(form.financials?.revenue_last_year)], ['Платежи по кредитам', money(form.financials?.existing_loans_monthly_payment)], ['Цель', a.purpose_text ?? PURPOSES[a.purpose]?.title]]} />
                  <KV items={[['Залог', COLLATERAL[form.collateral?.type ?? 'none']], ['Стоимость залога', money(form.collateral?.value)], ['Поручитель', form.guarantor?.full_name ?? '—'], ['ИНН поручителя', form.guarantor?.inn ?? '—']]} />
                </Stack>
              </Plate>
              {a.statement && (
                <Box mt="lg">
                  <StatementCard st={a.statement} />
                </Box>
              )}
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <Section title="Документы">
                <DocumentsList appId={a.id} docs={d.documents} bank />
                {d.documents.filter((x: Dossier) => x.status === 'uploaded').length > 0 && actions.length > 0 && (
                  <Stack gap={6} mt="sm">
                    {d.documents
                      .filter((x: Dossier) => x.status === 'uploaded')
                      .map((x: Dossier) => (
                        <Group key={x.id} justify="space-between" wrap="nowrap">
                          <Text size="xs" truncate>
                            {x.file_name}
                          </Text>
                          <Group gap={6} wrap="nowrap">
                            <Button size="compact-xs" color="ok" variant="light" onClick={() => review.mutate({ docId: x.id, status: 'accepted' })}>
                              Принять
                            </Button>
                            <Button size="compact-xs" color="bad" variant="light" onClick={() => review.mutate({ docId: x.id, status: 'rejected' })}>
                              Отклонить
                            </Button>
                          </Group>
                        </Group>
                      ))}
                  </Stack>
                )}
              </Section>
              {d.tasks.length > 0 && (
                <Section title="Запросы клиенту" mt={32}>
                  <div className="rows">
                    {d.tasks.map((t: Dossier) => (
                      <Box key={t.id} py={10}>
                        <Group gap={8} justify="space-between" wrap="nowrap">
                          <Text size="sm" fw={600}>
                            {t.title}
                          </Text>
                          <Status tone={t.status === 'open' ? 'warn' : 'ok'} size="sm">
                            {t.status === 'open' ? 'ожидает' : t.status === 'answered' ? 'выполнено' : t.status}
                          </Status>
                        </Group>
                        {t.answer_text && (
                          <Text size="xs" c="dimmed">
                            Ответ: {t.answer_text}
                          </Text>
                        )}
                      </Box>
                    ))}
                  </div>
                </Section>
              )}
            </Grid.Col>
          </Grid>
        </Tabs.Panel>

        <Tabs.Panel value="log">
          <Grid gutter={40}>
            <Grid.Col span={{ base: 12, md: 7 }}>
              <Section title="События заявки">
                <Timeline events={d.events} bank />
              </Section>
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 5 }}>
              <Section title="Решения">
                <div className="rows">
                  {d.decisions.map((x: Dossier) => (
                    <Box key={x.id} py={10}>
                      <Group gap={8} wrap="wrap">
                        <Status tone={OUTCOME[x.outcome]?.color} size="sm">
                          {x.kind === 'recommendation' ? 'Рекомендация' : 'Решение'}: {OUTCOME[x.outcome]?.title ?? x.outcome}
                        </Status>
                        <Text size="xs" c="dimmed">
                          {LEVELS[x.level] ?? x.level}
                        </Text>
                      </Group>
                      <Text size="xs" c="dimmed" mt={2}>
                        {x.decided_by_name ?? '—'} · {dateTime(x.created_at)} · политика v{x.policy_version}
                      </Text>
                      {x.comment && <Text size="xs">{x.comment}</Text>}
                    </Box>
                  ))}
                </div>
              </Section>
              {d.signatures.length > 0 && (
                <Section title="Подписи (ПЭП)" mt={32}>
                  <div className="rows">
                    {d.signatures.map((s: Dossier) => (
                      <Box key={s.document_hash + s.document_kind} py={8}>
                        <Text size="sm" fw={500}>
                          {s.document_title}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {s.signer_name} · {dateTime(s.signed_at)} · IP {s.ip ?? '—'}
                        </Text>
                      </Box>
                    ))}
                  </div>
                </Section>
              )}
            </Grid.Col>
          </Grid>
        </Tabs.Panel>

        <Tabs.Panel value="memo">
          <Plate>
            <Group justify="space-between" mb="sm" wrap="wrap">
              <Title order={3}>Черновик кредитного заключения</Title>
              {memo.data && <Tag>{memo.data.provider === 'llm' ? 'LLM с открытыми весами' : 'шаблон по данным досье'}</Tag>}
            </Group>
            {memo.isLoading ? <InlineLoading text="Готовим заключение…" /> : memo.data ? <Markdown text={memo.data.markdown} /> : null}
            <Text size="xs" c="dimmed" mt="md">
              Все цифры берутся из досье. Заключение — черновик: решение принимает специалист.
            </Text>
          </Plate>
        </Tabs.Panel>
      </Tabs>
      <DecisionModal key={action ?? 'none'} d={d} action={action} onClose={() => setAction(null)} />
      <Text c="dimmed" fz="xs" mt={32}>
        Просмотр досье фиксируется в журнале аудита.
      </Text>
    </Box>
  );
}
