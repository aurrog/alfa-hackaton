import { Alert, Box, Button, Collapse, Grid, Group, List, Modal, SimpleGrid, Stack, Text, Textarea, Title } from '@mantine/core';
import { IconAlertTriangle, IconArrowRight, IconCheck, IconFileText, IconSignature } from '@tabler/icons-react';
import { useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { api, errorText } from '../../api/client';
import type { Application } from '../../api/types';
import { DocDropzone, DocumentsList } from '../../components/Documents';
import { RouteMap, currentStage } from '../../components/RouteMap';
import { Schedule } from '../../components/Schedule';
import { SignModal } from '../../components/SignModal';
import { Timeline } from '../../components/Timeline';
import { BackLink, ErrorAlert, Loading, Money, Plate, Section, Status, Tag } from '../../components/ui';
import { date, dateTime, money, months, pct, slaLeft } from '../../lib/format';
import { TONE } from '../../lib/labels';
import { CheckDraw, Spinner } from '../../lib/motion';
import { useApplication, useSetApplication } from './hooks';

const LIVE = new Set(['submitted', 'data_check', 'enrichment', 'scoring', 'disbursement']);

const CHECKS = [
  { title: 'Проверяем анкету и документы', hint: 'полнота и корректность данных' },
  { title: 'Запрашиваем ЕГРЮЛ, ФНС и бюро кредитных историй', hint: 'обычно 10–20 секунд' },
  { title: 'Считаем оценку и посильный платёж', hint: 'скоринговая модель и кредитная политика банка' },
  { title: 'Готовим решение', hint: 'одобрение, другие условия или передача специалисту' },
];
const CHECK_AT: Record<string, number> = { submitted: 0, data_check: 0, enrichment: 1, scoring: 2 };

/** Живая проверка: пока работает конвейер, пункты по очереди получают галочку. */
function LiveChecks({ status }: { status: string }) {
  const at = CHECK_AT[status] ?? 0;
  return (
    <Plate tone="white">
      <Text fw={600}>Что происходит сейчас</Text>
      <Text size="sm" c="dimmed" mt={2}>
        Обычно это меньше минуты — страницу можно не обновлять.
      </Text>
      <div className="live-steps" style={{ marginTop: 12 }}>
        {CHECKS.map((c, i) => {
          const state = i < at ? 'done' : i === at ? 'current' : 'upcoming';
          return (
            <div key={c.title} className={`live-step ${state}`}>
              <span className="ic">{state === 'done' ? <CheckDraw size={22} /> : state === 'current' ? <Spinner /> : null}</span>
              <div>
                <div className="t">{c.title}</div>
                <div className="h">{c.hint}</div>
              </div>
            </div>
          );
        })}
      </div>
    </Plate>
  );
}

function TasksBlock({ app, onChange }: { app: Application; onChange: (a: Application) => void }) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const open = app.tasks.filter((t) => t.status === 'open');
  const run = async (key: string, fn: () => Promise<Application>) => {
    setBusy(key);
    setError(null);
    try {
      onChange(await fn());
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  };
  return (
    <Plate tone="warn" size="lg">
      <Title order={2} fz={24}>
        Нужны уточнения
      </Title>
      <Text size="sm" mt={6} c="var(--ink-2)">
        Выполните задачи и верните заявку в работу — проверка продолжится автоматически.
      </Text>
      <Stack gap={10} mt="lg">
        {app.tasks
          .filter((t) => t.status !== 'cancelled')
          .map((t) => (
            <Box key={t.id} bg="#fff" p={16} style={{ borderRadius: 16 }}>
              <Group justify="space-between" wrap="nowrap" align="flex-start" gap="sm">
                <Box style={{ minWidth: 0 }}>
                  <Text fw={600} size="sm">
                    {t.title}
                  </Text>
                  {t.description && (
                    <Text size="sm" c="dimmed">
                      {t.description}
                    </Text>
                  )}
                  <Text size="xs" c="dimmed" mt={4}>
                    {t.from_bank ? 'Запрос специалиста банка' : 'Автоматическая проверка'}
                  </Text>
                </Box>
                {t.status !== 'open' && (
                  <Tag tone="ok" icon={<IconCheck size={12} />}>
                    Выполнено
                  </Tag>
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
                  <Button onClick={() => run(t.id, () => api.post<Application>(`/api/v1/applications/${app.id}/tasks/${t.id}/answer`, { text: answers[t.id] }))} loading={busy === t.id} disabled={!answers[t.id]?.trim()}>
                    Ответить
                  </Button>
                </Group>
              )}
              {t.answer_text && (
                <Text size="sm" mt={6}>
                  Ваш ответ: {t.answer_text}
                </Text>
              )}
            </Box>
          ))}
      </Stack>
      {error && (
        <Alert color="bad" mt="sm">
          {error}
        </Alert>
      )}
      <Group justify="flex-end" mt="lg">
        <Button color="brand" size="md" rightSection={<IconArrowRight size={17} />} disabled={open.length > 0} loading={busy === 'resume'} onClick={() => run('resume', () => api.post<Application>(`/api/v1/applications/${app.id}/resume`))}>
          {open.length ? `Осталось задач: ${open.length}` : 'Вернуть заявку в работу'}
        </Button>
      </Group>
    </Plate>
  );
}

function OfferBlock({ app, onChange }: { app: Application; onChange: (a: Application) => void }) {
  const o = app.offer!;
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [contract, setContract] = useState<string | null>(null);
  const [sign, setSign] = useState(false);
  const [declineOpen, setDeclineOpen] = useState(false);
  const [schedule, setSchedule] = useState(false);
  const canSign = app.company.membership?.can_sign;
  const isLE = app.company.legal_form === 'LE';
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
  const active = app.status === 'offer_issued';
  const statusText = o.status === 'accepted' ? 'Предложение принято' : o.status === 'active' ? `Действует до ${dateTime(o.expires_at)}` : o.status === 'declined' ? 'Вы отказались от предложения' : o.status === 'expired' ? 'Срок предложения истёк' : o.status;

  return (
    <Plate tone="white" size="lg" className="rise">
      <Text size="sm" c="dimmed">
        Предложение банка · {statusText}
      </Text>
      <Group gap={12} mt={6} wrap="nowrap" align="flex-start">
        {active && <CheckDraw size={28} delay={250} style={{ marginTop: 2 }} />}
        <Title order={2} fz={{ base: 22, sm: 26 }}>
          {o.is_counter ? 'Банк готов выдать кредит на других условиях' : 'Банк одобрил кредит'}
        </Title>
      </Group>
      <Group align="baseline" gap={10} mt={18} wrap="wrap">
        <Money value={o.amount} size="clamp(36px, 6vw, 52px)" countUp={active} />
        <Text fz={18} c="var(--ink-2)">
          на {months(o.term_months)}
        </Text>
      </Group>
      <SimpleGrid cols={{ base: 2, sm: 3 }} mt={22} spacing="md">
        <Box>
          <Text size="sm" c="dimmed">
            {o.payment_kind === 'annuity' ? 'Платёж в месяц' : 'Проценты в месяц'}
          </Text>
          <Money value={o.monthly_payment} size={22} />
        </Box>
        <Box>
          <Text size="sm" c="dimmed">
            Ставка
          </Text>
          <Text fz={22} fw={700} className="display num">
            {pct(o.rate, 2)}
          </Text>
        </Box>
        <Box>
          <Text size="sm" c="dimmed">
            Переплата
          </Text>
          <Money value={o.overpayment} size={22} />
        </Box>
      </SimpleGrid>
      <Text size="xs" c="dimmed" mt={10} className="num">
        Всего выплат {money(o.total_payment)} · эффективная ставка {pct(o.effective_rate, 2)} · без комиссий
      </Text>

      {o.changes.length > 0 && (
        <Plate tone="warn" size="sm" style={{ marginTop: 20 }}>
          <Group gap={8} wrap="nowrap" align="flex-start">
            <IconAlertTriangle size={18} color="var(--warn)" style={{ flex: 'none', marginTop: 1 }} />
            <Box>
              <Text size="sm" fw={600}>
                Что изменилось относительно запроса
              </Text>
              <List size="sm" spacing={3} mt={4}>
                {o.changes.map((c) => (
                  <List.Item key={c}>{c}</List.Item>
                ))}
              </List>
              <Text size="xs" mt={8} c="var(--ink-2)">
                Платёж должен быть посильным для денежного потока бизнеса — так банк защищает и вас, и себя. Отказаться можно без последствий.
              </Text>
            </Box>
          </Group>
        </Plate>
      )}

      {o.conditions.length > 0 && (
        <Box mt={20}>
          <Text size="sm" fw={600} mb={6}>
            Условия
          </Text>
          <List size="sm" spacing={3}>
            {o.conditions.map((c) => (
              <List.Item key={c}>{c}</List.Item>
            ))}
          </List>
        </Box>
      )}

      <Box mt={20}>
        <button type="button" className="link-btn" style={{ fontSize: 14 }} onClick={() => setSchedule((s) => !s)}>
          {schedule ? 'Скрыть график платежей' : 'График платежей'}
        </button>
        <Collapse in={schedule}>
          <Box mt="sm">
            <Schedule rows={o.schedule} />
          </Box>
        </Collapse>
      </Box>

      {error && (
        <Alert color="bad" mt="md">
          {error}
        </Alert>
      )}
      {!canSign && ['offer_issued', 'offer_accepted'].includes(app.status) && (
        <Text size="sm" c="var(--warn-ink)" mt="md">
          Принять предложение и подписать договор может руководитель или собственник с правом подписи.
        </Text>
      )}
      <Group mt={28} gap="sm">
        {app.actions.includes('accept_offer') && (
          <Button color="brand" size="lg" leftSection={<IconCheck size={18} />} loading={busy === 'accept'} onClick={() => act('accept', () => api.post<Application>(`/api/v1/applications/${app.id}/offer/accept`, undefined, { idempotent: true }))}>
            Принять предложение
          </Button>
        )}
        {app.actions.includes('sign_contract') && (
          <Button color="brand" size="lg" leftSection={<IconSignature size={18} />} onClick={() => setSign(true)}>
            Подписать договор
          </Button>
        )}
        {['offer_accepted', 'disbursement', 'issued'].includes(app.status) && (
          <Button variant="default" size="lg" leftSection={<IconFileText size={18} />} loading={busy === 'contract'} onClick={showContract}>
            {app.status === 'offer_accepted' ? 'Посмотреть договор' : 'Договор'}
          </Button>
        )}
        {app.actions.includes('decline_offer') && (
          <Button variant="default" size="lg" onClick={() => setDeclineOpen(true)}>
            Отказаться
          </Button>
        )}
      </Group>
      {active && (
        <Text size="xs" c="dimmed" mt={10}>
          После принятия откроется договор — его можно прочитать и подписать здесь же, деньги придут на расчётный счёт.
        </Text>
      )}

      <Modal opened={!!contract} onClose={() => setContract(null)} size="xl" title="Кредитный договор">
        {contract && <iframe title="Договор" srcDoc={contract} sandbox="" style={{ width: '100%', height: '68vh', border: '1px solid var(--line)', borderRadius: 12, background: '#fff' }} />}
        {app.actions.includes('sign_contract') && (
          <Group justify="flex-end" mt="md">
            <Button
              color="brand"
              size="md"
              leftSection={<IconSignature size={18} />}
              onClick={() => {
                setContract(null);
                setSign(true);
              }}
            >
              Подписать договор
            </Button>
          </Group>
        )}
      </Modal>
      <Modal opened={declineOpen} onClose={() => setDeclineOpen(false)} title="Отказаться от предложения?">
        <Text size="sm">Заявка будет закрыта. Это не влияет на кредитную историю — новую заявку можно подать в любой момент.</Text>
        <Group justify="flex-end" mt="xl" gap="sm">
          <Button variant="default" onClick={() => setDeclineOpen(false)}>
            Оставить
          </Button>
          <Button color="bad" loading={busy === 'decline'} onClick={() => act('decline', () => api.post<Application>(`/api/v1/applications/${app.id}/offer/decline`, { comment: 'Клиент отказался в кабинете' })).then(() => setDeclineOpen(false))}>
            Отказаться
          </Button>
        </Group>
      </Modal>
      <SignModal
        opened={sign}
        onClose={() => setSign(false)}
        title="Подписание кредитного договора"
        documents={[`Кредитный договор на ${money(o.amount)}`, ...(isLE ? ['Договор поручительства собственника'] : [])]}
        onSign={(password) => api.post<Application>(`/api/v1/applications/${app.id}/contract/sign`, { password }, { idempotent: true })}
        onDone={(a) => onChange(a as Application)}
        doneText={{ title: 'Договор подписан', text: 'Перечисляем деньги на расчётный счёт — это займёт несколько секунд.' }}
        confirmLabel="Подписать договор"
      />
    </Plate>
  );
}

function DeclineBlock({ app }: { app: Application }) {
  const e = app.explanation!;
  return (
    <Plate size="lg">
      <Title order={2} fz={{ base: 22, sm: 26 }}>
        {e.headline}
      </Title>
      <Text size="sm" fw={600} mt="lg" mb={6}>
        Почему
      </Text>
      <List size="sm" spacing={6}>
        {e.reasons.map((r) => (
          <List.Item key={r.code}>{r.text}</List.Item>
        ))}
      </List>
      {e.plan.length > 0 && (
        <Box bg="#fff" p={{ base: 16, sm: 22 }} mt="lg" style={{ borderRadius: 18 }}>
          <Text fw={600}>Что сделать, чтобы следующая заявка была одобрена</Text>
          <List type="ordered" size="sm" spacing={6} mt={8}>
            {e.plan.map((p) => (
              <List.Item key={p}>{p}</List.Item>
            ))}
          </List>
          {e.can_reapply_after && (
            <Text size="xs" c="dimmed" mt="sm">
              Повторная заявка: {/^\d{4}-/.test(e.can_reapply_after) ? `рекомендуем не раньше ${date(e.can_reapply_after)}` : e.can_reapply_after}
            </Text>
          )}
        </Box>
      )}
      {(e.negatives.length > 0 || e.positives.length > 0) && (
        <SimpleGrid cols={{ base: 1, sm: 2 }} mt="lg" spacing="lg">
          <Box>
            <Text size="sm" fw={600} mb={6}>
              Сильнее всего снизило оценку
            </Text>
            <Stack gap={4}>
              {e.negatives.map((n) => (
                <Text key={n.title} size="sm">
                  {n.title}: <b>{n.value}</b>
                </Text>
              ))}
            </Stack>
          </Box>
          <Box>
            <Text size="sm" fw={600} mb={6}>
              Ваши сильные стороны
            </Text>
            <Stack gap={4}>
              {e.positives.map((n) => (
                <Text key={n.title} size="sm">
                  {n.title}: <b>{n.value}</b>
                </Text>
              ))}
            </Stack>
          </Box>
        </SimpleGrid>
      )}
      <Group mt="xl">
        <Button variant="default" component={Link} to="/products">
          Подобрать другой продукт
        </Button>
      </Group>
    </Plate>
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
  const sla = app.waiting === 'bank' ? slaLeft(app.sla_due_at) : null;
  const stage = currentStage(app.stages);
  const cancel = async () => {
    setBusy(true);
    try {
      setApp(await api.post<Application>(`/api/v1/applications/${app.id}/cancel`, { comment: 'Отозвана клиентом в кабинете' }));
      setCancelOpen(false);
    } finally {
      setBusy(false);
    }
  };
  const tone = TONE[app.status_tone] ?? '';

  return (
    <Box>
      <BackLink to="/applications">Заявки</BackLink>
      <Group justify="space-between" align="flex-end" mt={10} mb={28} wrap="wrap" gap="md">
        <Box style={{ minWidth: 0 }}>
          <Text size="sm" c="dimmed">
            Заявка {app.number}
            {app.submitted_at ? ` · подана ${dateTime(app.submitted_at)}` : ''}
          </Text>
          <Title order={1} fz={{ base: 28, sm: 36 }} mt={4}>
            {app.product.name}
          </Title>
          <Text c="var(--ink-2)" mt={6}>
            {money(app.amount)} на {months(app.term_months)} · {app.purpose_title}
          </Text>
        </Box>
      </Group>

      <Plate size="lg">
        <Group justify="space-between" wrap="wrap" gap="sm" mb={18}>
          <Box>
            <Status tone={tone} pulse={live}>
              <Text span fw={700} fz={20} className="display">
                {app.status_label}
              </Text>
            </Status>
          </Box>
          {live ? (
            <Text size="sm" c="dimmed">
              Статус обновляется сам
            </Text>
          ) : sla ? (
            <Text size="sm" c={sla.overdue ? 'bad' : 'dimmed'}>
              Норматив рассмотрения: {sla.text}
            </Text>
          ) : null}
        </Group>
        <RouteMap stages={app.stages} waiting={app.waiting} />
        {stage && (
          <Text size="xs" c="dimmed" mt={8} hiddenFrom="sm">
            Этап {stage.index + 1} из {app.stages.length} · {stage.title}
          </Text>
        )}
        <Text mt={18} c="var(--ink-2)" maw={760}>
          {app.status_hint}
        </Text>
        {app.next_action && (
          <Text fw={600} mt={8} c={app.waiting === 'client' ? 'var(--warn-ink)' : undefined}>
            {app.waiting === 'client' ? 'Ваш шаг: ' : 'Дальше: '}
            {app.next_action}
          </Text>
        )}
      </Plate>

      <Grid gutter={{ base: 32, md: 48 }} mt={32}>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Stack gap={32}>
            {app.status === 'info_requested' && <TasksBlock app={app} onChange={setApp} />}
            {app.loan && (
              <Plate tone="ok" size="lg" className="rise">
                <Text size="sm" c="var(--ink-2)">
                  Кредит выдан {date(app.loan.issued_at)}
                </Text>
                <Group gap={12} mt={4} wrap="nowrap">
                  <CheckDraw size={28} delay={200} />
                  <Title order={2} fz={{ base: 22, sm: 26 }}>
                    Деньги на счёте
                  </Title>
                </Group>
                <Box mt={10}>
                  <Money value={app.loan.amount} size={40} countUp />
                </Box>
                <Text size="sm" mt={8}>
                  Зачислены на расчётный счёт {app.loan.settlement_account}. Договор {app.loan.contract_number}, ссудный счёт {app.loan.loan_account}.
                </Text>
                <Button mt="lg" variant="white" component={Link} to="/loans" rightSection={<IconArrowRight size={16} />}>
                  График платежей
                </Button>
              </Plate>
            )}
            {app.offer && <OfferBlock app={app} onChange={setApp} />}
            {app.status === 'declined' && app.explanation && <DeclineBlock app={app} />}
            {live && app.status !== 'disbursement' && !app.offer && <LiveChecks status={app.status} />}
            {app.waiting === 'bank' && !app.offer && (
              <Box>
                <Text fw={600}>Что происходит сейчас</Text>
                <Text size="sm" c="var(--ink-2)" mt={4} maw={640}>
                  Заявку рассматривает специалист банка. Если понадобятся документы или пояснения, задача появится здесь и в уведомлениях.
                </Text>
              </Box>
            )}
            <Section title="Документы">
              <DocumentsList appId={app.id} docs={app.documents} />
            </Section>
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Stack gap={32}>
            <Section title="История">
              <Timeline events={app.events} limit={14} />
            </Section>
            {app.signatures.length > 0 && (
              <Section title="Подписано">
                <div className="rows">
                  {app.signatures.map((s) => (
                    <Box key={s.document_hash + s.document_kind} py={10}>
                      <Text size="sm" fw={500}>
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
                </div>
              </Section>
            )}
            {app.actions.includes('cancel') && (
              <Box>
                <button type="button" className="link-btn" style={{ fontSize: 14, color: 'var(--muted)' }} onClick={() => setCancelOpen(true)}>
                  Отозвать заявку
                </button>
              </Box>
            )}
          </Stack>
        </Grid.Col>
      </Grid>
      <Modal opened={cancelOpen} onClose={() => setCancelOpen(false)} title="Отозвать заявку?">
        <Text size="sm">Рассмотрение будет остановлено. Данные компании сохранятся и подставятся в новую заявку.</Text>
        <Group justify="flex-end" mt="xl" gap="sm">
          <Button variant="default" onClick={() => setCancelOpen(false)}>
            Нет
          </Button>
          <Button color="bad" onClick={cancel} loading={busy}>
            Отозвать
          </Button>
        </Group>
      </Modal>
    </Box>
  );
}
