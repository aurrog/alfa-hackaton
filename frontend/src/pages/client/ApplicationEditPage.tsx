import { Alert, Badge, Box, Button, Card, Grid, Group, List, NumberInput, Select, SimpleGrid, Stack, Stepper, Text, TextInput, Textarea, ThemeIcon, Title } from '@mantine/core';
import { IconAlertCircle, IconArrowLeft, IconArrowRight, IconCheck, IconCircleCheck, IconCloudCheck, IconDownload, IconLoader2, IconSend, IconSignature } from '@tabler/icons-react';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { api, errorText } from '../../api/client';
import type { Application } from '../../api/types';
import { DocDropzone, DocumentsList, StatementCard } from '../../components/Documents';
import { SignModal } from '../../components/SignModal';
import { ErrorAlert, KV, Loading, PageHeader, Section, SourceMark, StatusBadge } from '../../components/ui';
import { annuity, date, money, months } from '../../lib/format';
import { COLLATERAL, PURPOSES } from '../../lib/labels';
import { useApplication, useProducts, useSetApplication } from './hooks';

type Form = Record<string, Record<string, unknown>>;
type Top = { amount: number; term_months: number; purpose: string; purpose_text: string };

const STEPS = ['Условия', 'Компания', 'Финансы', 'Обеспечение', 'Документы', 'Отправка'];
const FIELD_STEP: Record<string, number> = { amount: 0, term_months: 0, purpose: 0, contact: 1, company: 1, financials: 2, collateral: 3, guarantor: 3 };

function stepOf(field: string) {
  return FIELD_STEP[field.split('.')[0]] ?? 5;
}

export function ApplicationEditPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const q = useApplication(id);
  const setApp = useSetApplication();
  const app = q.data;
  const products = useProducts(app?.company.id);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<Form | null>(null);
  const [top, setTop] = useState<Top | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [showErrors, setShowErrors] = useState(false);
  const [sign, setSign] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const dirty = useRef<Record<string, unknown>>({});
  const timer = useRef<number | undefined>(undefined);
  const inflight = useRef<Promise<void> | null>(null);

  useEffect(() => {
    if (app && !form) {
      setForm(JSON.parse(JSON.stringify(app.form)));
      setTop({ amount: app.amount, term_months: app.term_months, purpose: app.purpose, purpose_text: app.purpose_text ?? '' });
    }
  }, [app, form]);

  /** Отправить накопленные изменения (последовательно, без гонок). */
  const flush = useCallback(async () => {
    window.clearTimeout(timer.current);
    if (inflight.current) await inflight.current;
    const patch = dirty.current;
    if (!Object.keys(patch).length || !id) return;
    dirty.current = {};
    setSaving(true);
    inflight.current = api
      .patch<Application>(`/api/v1/applications/${id}`, patch)
      .then((a) => {
        setApp(a);
        setSaveError(null);
        setSavedAt(new Date());
      })
      .catch((e) => {
        setSaveError(errorText(e));
        for (const [k, v] of Object.entries(patch)) {
          const cur = dirty.current[k];
          dirty.current[k] = cur && typeof cur === 'object' && v && typeof v === 'object' ? { ...(v as object), ...(cur as object) } : (cur ?? v);
        }
      })
      .finally(() => {
        inflight.current = null;
        setSaving(false);
      });
    await inflight.current;
  }, [id, setApp]);

  const schedule = useCallback(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void flush(), 700);
  }, [flush]);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const setField = (section: string, key: string, value: unknown) => {
    setForm((f) => ({ ...(f ?? {}), [section]: { ...((f ?? {})[section] ?? {}), [key]: value } }));
    dirty.current[section] = { ...((dirty.current[section] as object) ?? {}), [key]: value === '' ? null : value };
    schedule();
  };
  const setTopField = <K extends keyof Top>(key: K, value: Top[K]) => {
    setTop((t) => (t ? { ...t, [key]: value } : t));
    dirty.current[key] = value === '' ? null : value;
    schedule();
  };

  if (q.isLoading || !form || !top) return q.error ? <ErrorAlert error={q.error} /> : <Loading />;
  if (!app) return null;
  if (!['draft', 'pending_signature'].includes(app.status)) return <Navigate to={`/applications/${app.id}`} replace />;

  const canSign = app.company.membership?.can_sign;
  const editable = app.actions.includes('edit');
  const prefill = app.prefill;
  const errs = app.validation_errors;
  const errFor = (field: string) => (showErrors ? errs.find((e) => e.field === field)?.message : undefined);
  const product = products.data?.items.find((p) => p.code === app.product.code);
  const rate = product?.rate_from ?? 20;
  const payment = app.product.kind === 'term_loan' ? annuity(top.amount, rate, top.term_months) : (top.amount * rate) / 1200;
  const missingDocs = app.checklist.filter((i) => i.required && !i.satisfied);
  const isLE = app.company.legal_form === 'LE';
  const f = (s: string) => form[s] ?? {};
  const v = (s: string, k: string) => (f(s)[k] as string | number | null | undefined) ?? '';

  const text = (section: string, key: string, label: string, extra: Record<string, unknown> = {}) => (
    <TextInput
      label={<Group gap={6}>{label}<SourceMark source={prefill[`${section}.${key}`] ?? (section === 'company' ? prefill.company : section === 'contact' ? prefill.contact : section === 'guarantor' ? prefill.guarantor : undefined)} /></Group>}
      value={String(v(section, key) ?? '')}
      onChange={(e) => setField(section, key, e.currentTarget.value)}
      error={errFor(`${section}.${key}`)}
      disabled={!editable}
      className={prefill[`${section}.${key}`] || (prefill[section] && v(section, key)) ? 'prefilled' : undefined}
      {...extra}
    />
  );
  const money_ = (section: string, key: string, label: string, description?: string) => (
    <NumberInput
      label={<Group gap={6}>{label}<SourceMark source={prefill[`${section}.${key}`]} /></Group>}
      description={description}
      value={(v(section, key) as number) ?? ''}
      onChange={(x) => setField(section, key, x === '' ? null : Number(x))}
      min={0}
      step={10_000}
      suffix=" ₽"
      error={errFor(`${section}.${key}`)}
      disabled={!editable}
      className={prefill[`${section}.${key}`] ? 'prefilled' : undefined}
    />
  );

  const go = async (n: number) => {
    await flush();
    setStep(n);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const doSubmit = async (password: string, c: { bki: boolean; pd: boolean }) => {
    await flush();
    const a = await api.post<Application>(`/api/v1/applications/${app.id}/submit`, { password, consent_bki: c.bki, consent_pd: c.pd }, { idempotent: true });
    setApp(a);
    nav(`/applications/${app.id}`);
  };
  const action = async (path: string, body?: unknown) => {
    setBusy(true);
    setActionError(null);
    try {
      await flush();
      const a = await api.post<Application>(`/api/v1/applications/${app.id}/${path}`, body);
      setApp(a);
      if (a.status !== 'draft' && a.status !== 'pending_signature') nav(`/applications/${app.id}`);
    } catch (e) {
      setActionError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const onUploaded = (a: Application) => {
    setApp(a);
    setForm((cur) => ({ ...(cur ?? {}), financials: { ...((cur ?? {}).financials ?? {}), ...(a.form.financials ?? {}) } }));
  };

  const docs: string[] = [`Заявка на кредит ${app.number}`, 'Согласие на запрос кредитной истории заёмщика'];
  if (isLE) docs.push(`Согласие поручителя (${String(v('guarantor', 'full_name')) || 'собственник'}) на запрос кредитной истории`);
  docs.push('Согласие на обработку персональных данных');

  const nextBtn = (n: number, label = 'Далее') => (
    <Group justify="space-between" mt="lg">
      <Button variant="default" leftSection={<IconArrowLeft size={16} />} onClick={() => go(Math.max(n - 2, 0))} disabled={n <= 1}>
        Назад
      </Button>
      <Button rightSection={<IconArrowRight size={16} />} onClick={() => go(n)}>
        {label}
      </Button>
    </Group>
  );

  return (
    <Stack gap="lg">
      <PageHeader
        eyebrow={`Заявка ${app.number}`}
        title={app.product.name}
        subtitle={app.status === 'pending_signature' ? 'Заявка подготовлена и ждёт подписи руководителя.' : 'Проверьте данные — большинство полей уже заполнено. Всё сохраняется автоматически.'}
        right={
          <Group gap="sm">
            <StatusBadge label={app.status_label} tone={app.status_tone} />
            <Text size="xs" c={saveError ? 'signal' : 'dimmed'}>
              {saving ? (
                <Group gap={4}><IconLoader2 size={14} className="pulse" /> сохраняем…</Group>
              ) : saveError ? (
                'не сохранено'
              ) : savedAt ? (
                <Group gap={4}><IconCloudCheck size={14} /> сохранено</Group>
              ) : null}
            </Text>
          </Group>
        }
      />
      {saveError && (
        <Alert color="signal" variant="light" icon={<IconAlertCircle size={18} />} title="Изменения не сохранились">
          {saveError}
        </Alert>
      )}
      {app.status === 'pending_signature' && !canSign && (
        <Alert color="amber" variant="light" title="Заявка передана на подпись">
          Руководитель увидит задачу в кабинете. Если нужно что-то поправить — верните заявку на доработку.
          <Group mt="sm">
            <Button size="xs" variant="white" color="amber" onClick={() => action('return-to-draft', { comment: 'Нужно внести изменения' })} loading={busy}>
              Вернуть на доработку
            </Button>
          </Group>
        </Alert>
      )}
      <Card>
        <Stepper active={step} onStepClick={(n) => void go(n)} size="sm" allowNextStepsSelect>
          {STEPS.map((s, i) => (
            <Stepper.Step key={s} label={s} color={showErrors && errs.some((e) => stepOf(e.field) === i) ? 'signal' : undefined} />
          ))}
        </Stepper>
      </Card>

      {step === 0 && (
        <Grid gutter="lg">
          <Grid.Col span={{ base: 12, md: 8 }}>
            <Section title="Условия кредита">
              <Stack>
                <SimpleGrid cols={{ base: 1, sm: 2 }}>
                  <NumberInput label="Сумма" value={top.amount} onChange={(x) => setTopField('amount', Number(x) || 0)} min={app.product.min_amount} max={app.product.max_amount} step={50_000} suffix=" ₽" error={errFor('amount')} disabled={!editable} description={`от ${money(app.product.min_amount)} до ${money(app.product.max_amount)}`} />
                  <NumberInput label="Срок, мес." value={top.term_months} onChange={(x) => setTopField('term_months', Number(x) || app.product.min_term)} min={app.product.min_term} max={app.product.max_term} error={errFor('term_months')} disabled={!editable} description={`от ${app.product.min_term} до ${app.product.max_term} мес.`} />
                </SimpleGrid>
                <Select label="Цель" value={top.purpose} onChange={(x) => x && setTopField('purpose', x)} data={(app.product.purposes.length ? app.product.purposes : Object.keys(PURPOSES)).map((c) => ({ value: c, label: PURPOSES[c]?.title ?? c }))} error={errFor('purpose')} disabled={!editable} allowDeselect={false} />
                <Textarea label="На что именно пойдут деньги" placeholder="Например: покупка кофемашины и холодильной витрины" value={top.purpose_text} onChange={(e) => setTopField('purpose_text', e.currentTarget.value)} autosize minRows={2} disabled={!editable} />
              </Stack>
            </Section>
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 4 }}>
            <Card className="hero">
              <Text size="sm" className="muted">
                {app.product.kind === 'term_loan' ? 'Ориентировочный платёж' : 'Проценты при полном использовании'}
              </Text>
              <Text fz={30} fw={700} ff="Unbounded, Onest, sans-serif" className="num" mt={4}>
                {money(payment)}
              </Text>
              <Text size="sm" className="muted" mt={4}>
                в месяц · {money(top.amount)} на {months(top.term_months)} по ставке от {String(rate).replace('.', ',')}%
              </Text>
              <Text size="xs" className="muted" mt="md">
                Точные условия — в предложении после оценки. Ставка зависит от оценки риска, залога и истории в банке.
              </Text>
            </Card>
          </Grid.Col>
          <Grid.Col span={12}>{nextBtn(1)}</Grid.Col>
        </Grid>
      )}

      {step === 1 && (
        <Stack>
          <Section title="Компания" right={<SourceMark source={prefill.company} />}>
            <KV
              cols={3}
              items={[
                ['Наименование', app.company.name],
                ['ИНН / ОГРН', `${app.company.inn} / ${app.company.ogrn ?? '—'}`],
                ['Дата регистрации', date(app.company.registration_date)],
                ['ОКВЭД', `${app.company.okved_code} ${app.company.okved_name ?? ''}`],
                ['Регион', app.company.region_name],
                ['Расчётный счёт', app.company.is_bank_client ? `в нашем банке, ${app.company.settlement_account ?? ''}` : 'в другом банке'],
              ]}
            />
            <SimpleGrid cols={{ base: 1, sm: 2 }} mt="md">
              {text('company', 'director_name', 'Руководитель')}
              {text('company', 'actual_address', 'Фактический адрес')}
              <NumberInput label="Сотрудников" value={(v('company', 'employees') as number) ?? ''} onChange={(x) => setField('company', 'employees', x === '' ? null : Number(x))} min={0} disabled={!editable} />
              {text('company', 'website', 'Сайт')}
            </SimpleGrid>
          </Section>
          <Section title="Контактное лицо">
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              {text('contact', 'name', 'ФИО')}
              {text('contact', 'position', 'Должность')}
              {text('contact', 'phone', 'Телефон')}
              {text('contact', 'email', 'E-mail')}
            </SimpleGrid>
          </Section>
          {nextBtn(2)}
        </Stack>
      )}

      {step === 2 && (
        <Stack>
          <Section title="Финансовые показатели">
            {app.company.is_bank_client ? (
              <Alert color="lime" variant="light" icon={<IconCircleCheck size={18} />} mb="md">
                Выручка и платежи подставлены по оборотам на вашем расчётном счёте — документы для подтверждения не нужны.
              </Alert>
            ) : (
              <Alert color="route" variant="light" mb="md">
                Счёт открыт в другом банке — загрузите выписку за 12 месяцев, и система сама посчитает обороты. Или укажите цифры вручную.
              </Alert>
            )}
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              {money_('financials', 'monthly_revenue', 'Выручка в месяц', 'среднемесячные поступления от покупателей')}
              {money_('financials', 'revenue_last_year', 'Выручка за прошлый год')}
              {money_('financials', 'net_profit_monthly', 'Чистая прибыль в месяц', 'необязательно')}
              {money_('financials', 'existing_loans_monthly_payment', 'Платежи по текущим кредитам в месяц')}
            </SimpleGrid>
          </Section>
          {!app.company.is_bank_client && (
            <Section
              title="Выписка по счёту"
              right={
                <Button size="xs" variant="subtle" leftSection={<IconDownload size={14} />} onClick={() => api.download(`/api/v1/demo/sample-statement/${app.company.id}`, 'kl_to_1c.txt')}>
                  Демо-выписка 1С
                </Button>
              }
            >
              {app.statement ? <StatementCard st={app.statement} /> : <DocDropzone appId={app.id} docType="bank_statement" onUploaded={onUploaded} />}
            </Section>
          )}
          {nextBtn(3)}
        </Stack>
      )}

      {step === 3 && (
        <Stack>
          <Section title="Обеспечение">
            <Text size="sm" c="dimmed" mb="sm">
              Залог не обязателен для небольших сумм, но позволяет получить больше и дешевле.
              {app.product.collateral_required_from ? ` По этому продукту залог нужен от ${money(app.product.collateral_required_from)}.` : ''}
            </Text>
            <SimpleGrid cols={{ base: 1, sm: 3 }}>
              <Select label="Вид залога" value={String(v('collateral', 'type') || 'none')} onChange={(x) => setField('collateral', 'type', x)} data={Object.entries(COLLATERAL).map(([value, label]) => ({ value, label }))} disabled={!editable} allowDeselect={false} />
              {v('collateral', 'type') && v('collateral', 'type') !== 'none' && (
                <>
                  {money_('collateral', 'value', 'Оценочная стоимость')}
                  {text('collateral', 'description', 'Описание')}
                </>
              )}
            </SimpleGrid>
          </Section>
          {isLE ? (
            <Section title="Поручитель — собственник бизнеса" right={<SourceMark source={prefill.guarantor} />}>
              <Text size="sm" c="dimmed" mb="sm">
                Для кредита компании нужно поручительство собственника. Данные подставлены из ЕГРЮЛ и профиля.
              </Text>
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                {text('guarantor', 'full_name', 'ФИО')}
                {text('guarantor', 'inn', 'ИНН физического лица')}
                {text('guarantor', 'birth_date', 'Дата рождения', { type: 'date' })}
                <NumberInput label="Доля в капитале, %" value={(v('guarantor', 'share') as number) ?? ''} onChange={(x) => setField('guarantor', 'share', x === '' ? null : Number(x))} min={0} max={100} disabled={!editable} />
              </SimpleGrid>
            </Section>
          ) : (
            <Alert variant="light" color="gray">
              Для индивидуального предпринимателя поручительство не требуется.
            </Alert>
          )}
          {nextBtn(4)}
        </Stack>
      )}

      {step === 4 && (
        <Stack>
          <Section title="Документы">
            <Text size="sm" c="dimmed" mb="md">
              Список собран под ваш продукт, сумму и данные, которые уже есть у банка. Недостающие документы можно донести позже — банк пришлёт задачу.
            </Text>
            <Stack gap="md">
              {app.checklist.length === 0 && <Text size="sm">Документы не нужны.</Text>}
              {app.checklist.map((i) => (
                <Card key={i.doc_type} padding="md" withBorder>
                  <Group justify="space-between" align="flex-start" wrap="nowrap">
                    <Group gap="sm" wrap="nowrap" align="flex-start">
                      <ThemeIcon variant="light" color={i.satisfied ? 'lime' : i.required ? 'amber' : 'gray'} radius="xl">
                        {i.satisfied ? <IconCheck size={16} /> : <IconAlertCircle size={16} />}
                      </ThemeIcon>
                      <Box>
                        <Text fw={600}>{i.title}</Text>
                        <Text size="sm" c="dimmed">
                          {i.reason}
                        </Text>
                      </Box>
                    </Group>
                    <Badge color={i.satisfied ? 'lime' : i.required ? 'amber' : 'gray'}>{i.satisfied ? (i.satisfied_by === 'internal_data' ? 'не нужна' : 'загружено') : i.required ? 'нужно' : 'по желанию'}</Badge>
                  </Group>
                  {!i.satisfied && editable && (
                    <Box mt="sm">
                      <Text size="xs" c="dimmed" mb={6}>
                        {i.hint}
                      </Text>
                      <DocDropzone appId={app.id} docType={i.doc_type} onUploaded={onUploaded} compact />
                    </Box>
                  )}
                </Card>
              ))}
            </Stack>
          </Section>
          <Section title="Загруженные файлы">
            <DocumentsList appId={app.id} docs={app.documents} onDeleted={setApp} canDelete={editable} />
            {editable && (
              <Box mt="md">
                <DocDropzone appId={app.id} docType="other" onUploaded={onUploaded} compact label="Добавить прочий документ" />
              </Box>
            )}
          </Section>
          {nextBtn(5)}
        </Stack>
      )}

      {step === 5 && (
        <Grid gutter="lg">
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Section title="Проверьте заявку">
              <KV
                items={[
                  ['Продукт', app.product.name],
                  ['Сумма и срок', `${money(top.amount)} на ${months(top.term_months)}`],
                  ['Цель', PURPOSES[top.purpose]?.title ?? top.purpose],
                  ['Залог', COLLATERAL[String(v('collateral', 'type') || 'none')]],
                  ['Выручка в месяц', money(Number(v('financials', 'monthly_revenue')) || null)],
                  ['Поручитель', isLE ? String(v('guarantor', 'full_name') || '—') : 'не требуется'],
                ]}
              />
              {errs.length > 0 ? (
                <Alert color="amber" variant="light" mt="md" title="Чтобы отправить заявку, заполните:">
                  <List size="sm">
                    {errs.map((e) => (
                      <List.Item key={e.field}>
                        <Text component="button" size="sm" c="amber.9" td="underline" style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer' }} onClick={() => { setShowErrors(true); void go(stepOf(e.field)); }}>
                          {e.message}
                        </Text>
                      </List.Item>
                    ))}
                  </List>
                </Alert>
              ) : (
                <Alert color="lime" variant="light" mt="md" icon={<IconCircleCheck size={18} />}>
                  Анкета заполнена. {missingDocs.length ? `Не хватает документов: ${missingDocs.map((d) => d.title.toLowerCase()).join(', ')} — банк запросит их после проверки.` : 'Документы в порядке.'}
                </Alert>
              )}
            </Section>
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 5 }}>
            <Card>
              <Title order={3}>{canSign ? 'Подпись и отправка' : 'Передача на подпись'}</Title>
              <Text size="sm" c="dimmed" mt={6}>
                {canSign
                  ? 'Подпишите заявку и согласия простой электронной подписью — заявка сразу уйдёт на автоматическую проверку. Статус будет обновляться на ваших глазах.'
                  : 'У вас нет права подписи. Передайте заявку руководителю: он получит задачу в кабинете, проверит данные и отправит заявку.'}
              </Text>
              {actionError && (
                <Alert color="signal" variant="light" mt="sm">
                  {actionError}
                </Alert>
              )}
              <Stack mt="md" gap="xs">
                {canSign ? (
                  <Button size="md" leftSection={<IconSignature size={18} />} disabled={errs.length > 0} onClick={() => { setShowErrors(true); setSign(true); }}>
                    Подписать и отправить в банк
                  </Button>
                ) : (
                  app.status === 'draft' && (
                    <Button size="md" leftSection={<IconSend size={18} />} disabled={errs.length > 0} loading={busy} onClick={() => action('send-for-signature')}>
                      Передать на подпись руководителю
                    </Button>
                  )
                )}
                {app.status === 'pending_signature' && canSign && (
                  <Button variant="default" onClick={() => action('return-to-draft', { comment: 'Возвращено руководителем на доработку' })} loading={busy}>
                    Вернуть на доработку
                  </Button>
                )}
              </Stack>
            </Card>
          </Grid.Col>
          <Grid.Col span={12}>
            <Button variant="default" leftSection={<IconArrowLeft size={16} />} onClick={() => go(4)}>
              Назад
            </Button>
          </Grid.Col>
        </Grid>
      )}

      <SignModal
        opened={sign}
        onClose={() => setSign(false)}
        title="Подписание заявки"
        documents={docs}
        consents={{
          bki: <>Даю согласие на получение кредитного отчёта из бюро кредитных историй — заёмщика{isLE ? ' и поручителя' : ''} (218-ФЗ)</> as ReactNode,
          pd: 'Даю согласие на обработку персональных данных в целях рассмотрения заявки (152-ФЗ)',
        }}
        onSign={doSubmit}
        confirmLabel="Подписать и отправить"
      />
    </Stack>
  );
}
