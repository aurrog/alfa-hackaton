import { Alert, Badge, Box, Button, Card, Grid, Group, List, Modal, SimpleGrid, Stack, Text, Textarea, ThemeIcon, Title } from '@mantine/core';
import { IconAlertTriangle, IconArrowRight, IconBolt, IconCheck, IconCircleCheck, IconCircleX, IconFileText, IconLoader2, IconSignature, IconX } from '@tabler/icons-react';
import { useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { api, errorText } from '../../api/client';
import type { Application } from '../../api/types';
import { DocDropzone, DocumentsList } from '../../components/Documents';
import { RouteMap } from '../../components/RouteMap';
import { Schedule } from '../../components/Schedule';
import { SignModal } from '../../components/SignModal';
import { Timeline } from '../../components/Timeline';
import { ErrorAlert, Loading, PageHeader, Section, StatusBadge, WaitingChip } from '../../components/ui';
import { date, dateTime, money, months, pct } from '../../lib/format';
import { useApplication, useSetApplication } from './hooks';

const LIVE = new Set(['submitted', 'data_check', 'enrichment', 'scoring', 'disbursement']);

function TasksBlock({ app, onChange }: { app: Application; onChange: (a: Application) => void }) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const open = app.tasks.filter((t) => t.status === 'open');
  const answer = async (taskId: string) => {
    setBusy(taskId);
    setError(null);
    try {
      onChange(await api.post<Application>(`/api/v1/applications/${app.id}/tasks/${taskId}/answer`, { text: answers[taskId] }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  };
  const resume = async () => {
    setBusy('resume');
    setError(null);
    try {
      onChange(await api.post<Application>(`/api/v1/applications/${app.id}/resume`));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  };
  return (
    <Card style={{ borderColor: 'var(--mantine-color-amber-4)', borderWidth: 2 }}>
      <Group gap={8} mb="xs">
        <ThemeIcon color="amber" variant="filled" radius="xl" size={28}>
          <IconBolt size={16} />
        </ThemeIcon>
        <Title order={3}>Нужны уточнения</Title>
      </Group>
      <Text size="sm" c="dimmed" mb="md">
        Выполните задачи — после этого нажмите «Вернуть заявку в работу», и проверка продолжится автоматически.
      </Text>
      <Stack gap="sm">
        {app.tasks
          .filter((t) => t.status !== 'cancelled')
          .map((t) => (
            <Card key={t.id} padding="md" withBorder bg={t.status === 'open' ? undefined : 'var(--mantine-color-lime-0)'}>
              <Group justify="space-between" wrap="nowrap" align="flex-start">
                <Box>
                  <Group gap={6}>
                    <Text fw={600}>{t.title}</Text>
                    <Badge size="xs" color={t.from_bank ? 'violet' : 'route'}>
                      {t.from_bank ? 'запрос специалиста' : 'автоматическая проверка'}
                    </Badge>
                  </Group>
                  {t.description && (
                    <Text size="sm" c="dimmed">
                      {t.description}
                    </Text>
                  )}
                </Box>
                {t.status !== 'open' && (
                  <Badge color="lime" leftSection={<IconCheck size={11} />}>
                    выполнено
                  </Badge>
                )}
              </Group>
              {t.status === 'open' && t.kind === 'document' && (
                <Box mt="sm">
                  <DocDropzone appId={app.id} docType={t.doc_type ?? 'other'} onUploaded={onChange} compact />
                </Box>
              )}
              {t.status === 'open' && t.kind === 'question' && (
                <Group mt="sm" align="flex-end" wrap="nowrap">
                  <Textarea style={{ flex: 1 }} autosize minRows={1} placeholder="Ваш ответ" value={answers[t.id] ?? ''} onChange={(e) => setAnswers((a) => ({ ...a, [t.id]: e.currentTarget.value }))} />
                  <Button onClick={() => answer(t.id)} loading={busy === t.id} disabled={!answers[t.id]?.trim()}>
                    Ответить
                  </Button>
                </Group>
              )}
              {t.answer_text && (
                <Text size="sm" mt={6}>
                  Ваш ответ: {t.answer_text}
                </Text>
              )}
            </Card>
          ))}
      </Stack>
      {error && (
        <Alert color="signal" variant="light" mt="sm">
          {error}
        </Alert>
      )}
      <Group justify="flex-end" mt="md">
        <Button color="amber" rightSection={<IconArrowRight size={16} />} disabled={open.length > 0} loading={busy === 'resume'} onClick={resume}>
          {open.length ? `Осталось задач: ${open.length}` : 'Вернуть заявку в работу'}
        </Button>
      </Group>
    </Card>
  );
}

function OfferBlock({ app, onChange }: { app: Application; onChange: (a: Application) => void }) {
  const o = app.offer!;
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [contract, setContract] = useState<string | null>(null);
  const [sign, setSign] = useState(false);
  const [declineOpen, setDeclineOpen] = useState(false);
  const canSign = app.company.membership?.can_sign;
  const act = async (name: string, fn: () => Promise<Application>) => {
    setBusy(name);
    setError(null);
    try {
      onChange(await fn());
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  };
  const showContract = async () => {
    setBusy('contract');
    try {
      setContract(await api.get<string>(`/api/v1/applications/${app.id}/contract`));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  };
  const isLE = app.company.legal_form === 'LE';
  return (
    <Card style={app.status === 'offer_issued' ? { borderColor: 'var(--mantine-color-lime-5)', borderWidth: 2 } : undefined}>
      <Group justify="space-between" align="flex-start">
        <Box>
          <Group gap={8}>
            <ThemeIcon color="lime" radius="xl" size={28}>
              <IconCircleCheck size={18} />
            </ThemeIcon>
            <Title order={3}>{o.is_counter ? 'Банк готов выдать кредит на других условиях' : 'Кредитное предложение'}</Title>
          </Group>
          {app.status === 'offer_issued' && (
            <Text size="sm" c="dimmed" mt={4}>
              Действует до {dateTime(o.expires_at)}
            </Text>
          )}
        </Box>
        <Badge color={o.status === 'accepted' ? 'lime' : o.status === 'active' ? 'route' : 'gray'} size="lg">
          {o.status === 'accepted' ? 'принято' : o.status === 'active' ? 'ждёт решения' : o.status === 'declined' ? 'отклонено' : o.status === 'expired' ? 'истекло' : o.status}
        </Badge>
      </Group>
      <SimpleGrid cols={{ base: 2, sm: 4 }} mt="lg">
        {[
          ['Сумма', money(o.amount)],
          ['Срок', months(o.term_months)],
          ['Ставка', pct(o.rate, 2)],
          [o.payment_kind === 'annuity' ? 'Платёж в месяц' : 'Проценты в месяц', money(o.monthly_payment)],
        ].map(([k, v]) => (
          <Box key={k}>
            <Text size="xs" c="dimmed">
              {k}
            </Text>
            <Text fz={22} fw={700} className="num" ff="Unbounded, Onest, sans-serif">
              {v}
            </Text>
          </Box>
        ))}
      </SimpleGrid>
      <Text size="sm" c="dimmed" mt="xs" className="num">
        Всего выплат {money(o.total_payment)} · переплата {money(o.overpayment)} · эффективная ставка {pct(o.effective_rate, 2)} (без комиссий)
      </Text>
      {o.changes.length > 0 && (
        <Alert color="amber" variant="light" mt="md" icon={<IconAlertTriangle size={18} />} title="Что изменилось относительно запроса">
          <List size="sm" spacing={4}>
            {o.changes.map((c) => (
              <List.Item key={c}>{c}</List.Item>
            ))}
          </List>
          <Text size="xs" mt={6}>
            Платёж должен быть посильным для денежного потока бизнеса — так банк защищает и вас, и себя. Вы можете отказаться без последствий.
          </Text>
        </Alert>
      )}
      {o.conditions.length > 0 && (
        <Box mt="md">
          <Text size="sm" fw={600} mb={4}>
            Условия
          </Text>
          <List size="sm" spacing={2}>
            {o.conditions.map((c) => (
              <List.Item key={c}>{c}</List.Item>
            ))}
          </List>
        </Box>
      )}
      <Box mt="md">
        <Text size="sm" fw={600} mb={4}>
          График платежей
        </Text>
        <Schedule rows={o.schedule} />
      </Box>
      {error && (
        <Alert color="signal" variant="light" mt="md">
          {error}
        </Alert>
      )}
      {!canSign && ['offer_issued', 'offer_accepted'].includes(app.status) && (
        <Alert color="amber" variant="light" mt="md">
          Принять предложение и подписать договор может руководитель или собственник с правом подписи.
        </Alert>
      )}
      <Group mt="lg" justify="flex-end">
        {app.actions.includes('decline_offer') && (
          <Button variant="default" color="gray" leftSection={<IconX size={16} />} onClick={() => setDeclineOpen(true)}>
            Отказаться
          </Button>
        )}
        {app.actions.includes('accept_offer') && (
          <Button color="lime" c="ink.9" leftSection={<IconCheck size={16} />} loading={busy === 'accept'} onClick={() => act('accept', () => api.post<Application>(`/api/v1/applications/${app.id}/offer/accept`, undefined, { idempotent: true }))}>
            Принять предложение
          </Button>
        )}
        {['offer_accepted', 'disbursement', 'issued'].includes(app.status) && (
          <Button variant="light" leftSection={<IconFileText size={16} />} loading={busy === 'contract'} onClick={showContract}>
            {app.status === 'offer_accepted' ? 'Посмотреть договор' : 'Договор'}
          </Button>
        )}
        {app.actions.includes('sign_contract') && (
          <Button leftSection={<IconSignature size={16} />} onClick={() => setSign(true)}>
            Подписать договор
          </Button>
        )}
      </Group>
      <Modal opened={!!contract} onClose={() => setContract(null)} size="xl" title={<Text fw={700}>Кредитный договор</Text>}>
        {contract && <iframe title="Договор" srcDoc={contract} sandbox="" style={{ width: '100%', height: '70vh', border: '1px solid var(--line)', borderRadius: 8, background: '#fff' }} />}
        {app.actions.includes('sign_contract') && (
          <Group justify="flex-end" mt="md">
            <Button leftSection={<IconSignature size={16} />} onClick={() => { setContract(null); setSign(true); }}>
              Подписать договор
            </Button>
          </Group>
        )}
      </Modal>
      <Modal opened={declineOpen} onClose={() => setDeclineOpen(false)} title={<Text fw={700}>Отказаться от предложения?</Text>} centered>
        <Text size="sm">Заявка будет закрыта. Это не влияет на кредитную историю — подать новую заявку можно в любой момент.</Text>
        <Group justify="flex-end" mt="lg">
          <Button variant="default" onClick={() => setDeclineOpen(false)}>
            Оставить
          </Button>
          <Button color="signal" loading={busy === 'decline'} onClick={() => act('decline', () => api.post<Application>(`/api/v1/applications/${app.id}/offer/decline`, { comment: 'Клиент отказался в кабинете' })).then(() => setDeclineOpen(false))}>
            Отказаться
          </Button>
        </Group>
      </Modal>
      <SignModal
        opened={sign}
        onClose={() => setSign(false)}
        title="Подписание кредитного договора"
        documents={[`Кредитный договор на ${money(o.amount)}`, ...(isLE ? ['Договор поручительства собственника'] : [])]}
        onSign={async (password) => onChange(await api.post<Application>(`/api/v1/applications/${app.id}/contract/sign`, { password }, { idempotent: true }))}
        confirmLabel="Подписать договор"
      />
    </Card>
  );
}

function DeclineBlock({ app }: { app: Application }) {
  const e = app.explanation!;
  return (
    <Card style={{ borderColor: 'var(--mantine-color-signal-3)' }}>
      <Group gap={8}>
        <ThemeIcon color="signal" radius="xl" size={28} variant="light">
          <IconCircleX size={18} />
        </ThemeIcon>
        <Title order={3}>{e.headline}</Title>
      </Group>
      <Text size="sm" fw={600} mt="md" mb={4}>
        Причины решения
      </Text>
      <List size="sm" spacing={6}>
        {e.reasons.map((r) => (
          <List.Item key={r.code}>{r.text}</List.Item>
        ))}
      </List>
      {e.plan.length > 0 && (
        <Card mt="md" padding="md" bg="var(--mantine-color-route-0)" withBorder={false}>
          <Text fw={700} mb={6}>
            Что сделать, чтобы следующая заявка была одобрена
          </Text>
          <List type="ordered" size="sm" spacing={6}>
            {e.plan.map((p) => (
              <List.Item key={p}>{p}</List.Item>
            ))}
          </List>
          {e.can_reapply_after && (
            <Text size="xs" c="dimmed" mt="sm">
              Повторная заявка: {/^\d{4}-/.test(e.can_reapply_after) ? `рекомендуем не раньше ${date(e.can_reapply_after)}` : e.can_reapply_after}
            </Text>
          )}
        </Card>
      )}
      {(e.negatives.length > 0 || e.positives.length > 0) && (
        <SimpleGrid cols={{ base: 1, sm: 2 }} mt="md">
          <Box>
            <Text size="sm" fw={600} mb={4}>
              Сильнее всего снизили оценку
            </Text>
            {e.negatives.map((n) => (
              <Text key={n.title} size="sm">
                • {n.title}: <b>{n.value}</b>
              </Text>
            ))}
          </Box>
          <Box>
            <Text size="sm" fw={600} mb={4}>
              Ваши сильные стороны
            </Text>
            {e.positives.map((n) => (
              <Text key={n.title} size="sm">
                • {n.title}: <b>{n.value}</b>
              </Text>
            ))}
          </Box>
        </SimpleGrid>
      )}
      <Group mt="md">
        <Button variant="light" component={Link} to="/products">
          Подобрать другой продукт
        </Button>
      </Group>
    </Card>
  );
}

export function ApplicationPage() {
  const { id } = useParams();
  const q = useApplication(id);
  const setApp = useSetApplication();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const app = q.data;
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  if (!app) return null;
  if (['draft', 'pending_signature'].includes(app.status) && app.actions.includes('edit')) return <Navigate to={`/applications/${app.id}/edit`} replace />;
  const live = LIVE.has(app.status);
  const cancel = async () => {
    setBusy(true);
    try {
      setApp(await api.post<Application>(`/api/v1/applications/${app.id}/cancel`, { comment: 'Отозвана клиентом в кабинете' }));
      setCancelOpen(false);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Stack gap="lg">
      <PageHeader
        eyebrow={`Заявка ${app.number} · ${app.company.short_name}`}
        title={app.product.name}
        subtitle={`${money(app.amount)} на ${months(app.term_months)} · ${app.purpose_title}`}
        right={<StatusBadge label={app.status_label} tone={app.status_tone} size="lg" pulse={live} />}
      />
      <Card>
        <Group justify="space-between" mb="md" wrap="wrap">
          <WaitingChip waiting={app.waiting} due={app.sla_due_at} />
          {live && (
            <Group gap={6} c="route">
              <IconLoader2 size={16} className="pulse" />
              <Text size="sm" c="route">
                Статус обновляется автоматически
              </Text>
            </Group>
          )}
        </Group>
        <RouteMap stages={app.stages} waiting={app.waiting} />
        <Text mt="md" size="sm">
          {app.status_hint}
        </Text>
        {app.next_action && (
          <Text fw={700} mt={6} c={app.waiting === 'client' ? 'amber.8' : undefined}>
            → {app.next_action}
          </Text>
        )}
      </Card>
      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Stack gap="lg">
            {app.status === 'info_requested' && <TasksBlock app={app} onChange={setApp} />}
            {app.offer && <OfferBlock app={app} onChange={setApp} />}
            {app.status === 'declined' && app.explanation && <DeclineBlock app={app} />}
            {app.loan && (
              <Card style={{ borderColor: 'var(--mantine-color-teal-4)', borderWidth: 2 }}>
                <Group gap={8}>
                  <ThemeIcon color="teal" radius="xl">
                    <IconCircleCheck size={18} />
                  </ThemeIcon>
                  <Title order={3}>Деньги на счёте</Title>
                </Group>
                <Text size="sm" mt="sm">
                  {money(app.loan.amount)} зачислены на расчётный счёт {app.loan.settlement_account}. Договор {app.loan.contract_number}, ссудный счёт {app.loan.loan_account}.
                </Text>
                <Button mt="md" variant="light" color="teal" component={Link} to="/loans">
                  График платежей в разделе «Кредиты»
                </Button>
              </Card>
            )}
            {(live || app.waiting === 'bank') && !app.offer && (
              <Card>
                <Text fw={600}>Что происходит сейчас</Text>
                <Text size="sm" c="dimmed" mt={4}>
                  {app.waiting === 'bank'
                    ? 'Заявку рассматривает специалист банка. Если понадобятся документы или пояснения, задача появится здесь и в уведомлениях.'
                    : 'Система проверяет анкету, запрашивает сведения из ЕГРЮЛ/ЕГРИП, ФНС и бюро кредитных историй и рассчитывает оценку. Обычно это занимает меньше минуты.'}
                </Text>
              </Card>
            )}
            <Section title="Документы">
              <DocumentsList appId={app.id} docs={app.documents} />
            </Section>
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Stack gap="lg">
            <Section title="История заявки">
              <Timeline events={app.events} limit={14} />
            </Section>
            {app.signatures.length > 0 && (
              <Section title="Подписанные документы">
                <Stack gap={6}>
                  {app.signatures.map((s) => (
                    <Box key={s.document_hash + s.document_kind}>
                      <Text size="sm" fw={600}>
                        {s.document_title}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {s.signer_name} · {dateTime(s.signed_at)} · ПЭП
                      </Text>
                      <Text size="xs" c="dimmed" className="mono" truncate>
                        SHA-256 {s.document_hash}
                      </Text>
                    </Box>
                  ))}
                </Stack>
              </Section>
            )}
            {app.actions.includes('cancel') && (
              <Button variant="subtle" color="gray" onClick={() => setCancelOpen(true)}>
                Отозвать заявку
              </Button>
            )}
          </Stack>
        </Grid.Col>
      </Grid>
      <Modal opened={cancelOpen} onClose={() => setCancelOpen(false)} title={<Text fw={700}>Отозвать заявку?</Text>} centered>
        <Text size="sm">Рассмотрение будет остановлено. Данные компании сохранятся и подставятся в новую заявку.</Text>
        <Group justify="flex-end" mt="lg">
          <Button variant="default" onClick={() => setCancelOpen(false)}>
            Нет
          </Button>
          <Button color="signal" onClick={cancel} loading={busy}>
            Отозвать
          </Button>
        </Group>
      </Modal>
    </Stack>
  );
}
