import { Alert, Box, Button, Collapse, Grid, Group, NumberInput, Select, SimpleGrid, Stack, Text, TextInput, Textarea, Title } from '@mantine/core';
import { IconAlertCircle, IconCheck, IconDownload, IconSend, IconSignature } from '@tabler/icons-react';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { api, errorText } from '../../api/client';
import type { Application } from '../../api/types';
import { DocDropzone, DocumentsList, StatementCard } from '../../components/Documents';
import { SignModal } from '../../components/SignModal';
import { ErrorAlert, KV, Loading, Money, PageTitle, Plate, SourceNote, Steps } from '../../components/ui';
import { annuity, date, money, months } from '../../lib/format';
import { COLLATERAL, PURPOSES } from '../../lib/labels';
import { FLOW } from './ProductsPage';
import { useApplication, useProducts, useSetApplication } from './hooks';

type Form = Record<string, Record<string, unknown>>;
type Top = { amount: number; term_months: number; purpose: string; purpose_text: string };

const SECTION_OF: Record<string, string> = {
  amount: 'terms', term_months: 'terms', purpose: 'terms', contact: 'contact', company: 'company', financials: 'financials', collateral: 'collateral', guarantor: 'guarantor',
};
const sectionOf = (field: string) => SECTION_OF[field.split('.')[0]] ?? 'documents';

/**
 * Раздел анкеты. Заполненный раздел свёрнут в одну строку-сводку («Компания ✓ ИП Смирнова, ИНН …  Изменить»),
 * раздел с пропусками раскрыт. Клиент проверяет то, что банк уже знает, а не перепечатывает это.
 */
function FormSection({ id, title, sub, summary, children, done, open, onToggle }: { id: string; title: string; sub?: ReactNode; summary?: ReactNode; children: ReactNode; done?: boolean; open: boolean; onToggle: () => void }) {
  return (
    <Box id={`sec-${id}`} style={{ scrollMarginTop: 90 }} className="form-section" data-open={open}>
      <Group justify="space-between" wrap="nowrap" align="flex-start" gap="md">
        <Box style={{ minWidth: 0 }}>
          <Group gap={10} wrap="nowrap">
            <Title order={3}>{title}</Title>
            {done && <IconCheck size={18} color="var(--ok)" stroke={2.4} style={{ flex: 'none' }} />}
          </Group>
          {!open && summary && (
            <Text size="sm" c="var(--ink-2)" mt={6}>
              {summary}
            </Text>
          )}
          {open && sub && (
            <Text size="sm" c="dimmed" mt={4}>
              {sub}
            </Text>
          )}
        </Box>
        {summary && (
          <button type="button" className="link-btn" style={{ fontSize: 14, flex: 'none', marginTop: 4 }} onClick={onToggle}>
            {open ? 'Свернуть' : 'Изменить'}
          </button>
        )}
      </Group>
      <Collapse in={open}>
        <Box pt={16}>{children}</Box>
      </Collapse>
    </Box>
  );
}

export function ApplicationEditPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const q = useApplication(id);
  const setApp = useSetApplication();
  const app = q.data;
  const products = useProducts(app?.company.id);
  const [form, setForm] = useState<Form | null>(null);
  const [top, setTop] = useState<Top | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});
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
      // раскрыты только разделы, где чего-то не хватает
      const initial: Record<string, boolean> = {};
      app.validation_errors.forEach((e) => (initial[sectionOf(e.field)] = true));
      setOpen(initial);
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

  const canSign = !!app.company.membership?.can_sign;
  const editable = app.actions.includes('edit');
  const prefill = app.prefill;
  const errs = app.validation_errors;
  const errFor = (field: string) => (showErrors ? errs.find((e) => e.field === field)?.message : undefined);
  const secHasErr = (sec: string) => errs.some((e) => sectionOf(e.field) === sec);
  const toggle = (sec: string) => setOpen((o) => ({ ...o, [sec]: !o[sec] }));
  const product = products.data?.items.find((p) => p.code === app.product.code);
  const rate = product?.rate_from ?? 20;
  const payment = app.product.kind === 'term_loan' ? annuity(top.amount, rate, top.term_months) : (top.amount * rate) / 1200;
  const missingDocs = app.checklist.filter((i) => i.required && !i.satisfied);
  const isLE = app.company.legal_form === 'LE';
  const f = (s: string) => form[s] ?? {};
  const v = (s: string, k: string) => (f(s)[k] as string | number | null | undefined) ?? '';
  const collateralFrom = app.product.collateral_required_from;
  const collateralNeeded = collateralFrom != null && top.amount >= collateralFrom;
  const hasCollateral = !!v('collateral', 'type') && v('collateral', 'type') !== 'none';
  const collateralVisible = collateralNeeded || hasCollateral || !!open.collateral || secHasErr('collateral');
  const sourceFor = (section: string, key: string) => prefill[`${section}.${key}`] ?? (['company', 'contact', 'guarantor'].includes(section) && v(section, key) ? prefill[section] : undefined);
  const join = (...xs: unknown[]) => xs.filter((x) => x !== '' && x !== null && x !== undefined).join(' · ');

  const text = (section: string, key: string, label: string, extra: Record<string, unknown> = {}) => (
    <Box>
      <TextInput label={label} value={String(v(section, key) ?? '')} onChange={(e) => setField(section, key, e.currentTarget.value)} error={errFor(`${section}.${key}`)} disabled={!editable} {...extra} />
      <SourceNote source={sourceFor(section, key)} />
    </Box>
  );
  const money_ = (section: string, key: string, label: string) => (
    <Box>
      <NumberInput label={label} value={(v(section, key) as number) ?? ''} onChange={(x) => setField(section, key, x === '' ? null : Number(x))} min={0} step={10_000} suffix=" ₽" error={errFor(`${section}.${key}`)} disabled={!editable} hideControls />
      <SourceNote source={prefill[`${section}.${key}`]} />
    </Box>
  );

  const goTo = (field: string) => {
    setShowErrors(true);
    const sec = sectionOf(field);
    setOpen((o) => ({ ...o, [sec]: true }));
    window.setTimeout(() => document.getElementById(`sec-${sec}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60);
  };

  const doSubmit = async (password: string, c: { bki: boolean; pd: boolean }) => {
    await flush();
    return api.post<Application>(`/api/v1/applications/${app.id}/submit`, { password, consent_bki: c.bki, consent_pd: c.pd }, { idempotent: true });
  };
  const afterSubmit = (a: unknown) => {
    setApp(a as Application);
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
  const openSign = async () => {
    setShowErrors(true);
    await flush();
    if (errs.length === 0) setSign(true);
    else goTo(errs[0].field);
  };

  const docs: string[] = [`Заявка на кредит ${app.number}`, 'Согласие на запрос кредитной истории заёмщика'];
  if (isLE) docs.push(`Согласие поручителя (${String(v('guarantor', 'full_name')) || 'собственник'}) на запрос кредитной истории`);
  docs.push('Согласие на обработку персональных данных');

  const mainCta =
    app.status === 'pending_signature' && !canSign ? null : canSign ? (
      <Button color="brand" size="lg" fullWidth leftSection={<IconSignature size={19} />} onClick={openSign}>
        Подписать и отправить
      </Button>
    ) : (
      <Button size="lg" fullWidth leftSection={<IconSend size={18} />} loading={busy} onClick={() => (errs.length ? goTo(errs[0].field) : action('send-for-signature'))}>
        Передать на подпись
      </Button>
    );

  const saveState = saving ? 'Сохраняем…' : saveError ? 'Не сохранено' : savedAt ? 'Изменения сохранены' : 'Сохраняется автоматически';
  const fin = f('financials');

  return (
    <Box>
      <PageTitle
        back={{ to: '/applications', label: 'Заявки' }}
        top={<Steps current={1} titles={FLOW} />}
        title={errs.length ? 'Проверьте данные' : 'Проверьте и подпишите'}
        sub={
          errs.length
            ? `Почти всё заполнено из ЕГРЮЛ, профиля и оборотов по счёту. Осталось ${errs.length === 1 ? 'одно поле' : `полей: ${errs.length}`}.`
            : 'Мы заполнили заявку данными, которые уже известны банку. Если всё верно — подпишите.'
        }
      />
      {saveError && (
        <Alert color="bad" mb="lg" icon={<IconAlertCircle size={18} />} title="Изменения не сохранились">
          {saveError}
        </Alert>
      )}
      {app.status === 'pending_signature' && (
        <Plate tone={canSign ? 'warn' : 'info'} size="sm" style={{ marginBottom: 24 }}>
          <Group justify="space-between" wrap="wrap" gap="sm">
            <Text size="sm" fw={500}>
              {canSign ? 'Заявку подготовил сотрудник — проверьте данные и подпишите.' : 'Заявка передана на подпись руководителю. Он увидит задачу в кабинете.'}
            </Text>
            <Button size="xs" variant="white" loading={busy} onClick={() => action('return-to-draft', { comment: canSign ? 'Возвращено руководителем на доработку' : 'Нужно внести изменения' })}>
              Вернуть на доработку
            </Button>
          </Group>
        </Plate>
      )}

      <Grid gutter={{ base: 32, md: 48 }}>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Stack gap={0} className="form-sections enter">
            <Box id="sec-terms" style={{ scrollMarginTop: 90 }} pb={28}>
              <Plate>
                <Group justify="space-between" align="flex-start" wrap="nowrap">
                  <Box>
                    <Text size="sm" c="dimmed">
                      {app.product.name} · заявка {app.number}
                    </Text>
                    <Money value={top.amount} size={32} />
                    <Text size="sm" mt={4} c="var(--ink-2)">
                      на {months(top.term_months)} · {PURPOSES[top.purpose]?.title ?? top.purpose}
                      {top.purpose_text ? ` · ${top.purpose_text}` : ''}
                    </Text>
                  </Box>
                  {editable && (
                    <Button variant="white" size="xs" onClick={() => toggle('terms')} style={{ flex: 'none' }}>
                      {open.terms ? 'Готово' : 'Изменить'}
                    </Button>
                  )}
                </Group>
                <Collapse in={!!open.terms}>
                  <Stack mt="lg" gap="md">
                    <SimpleGrid cols={{ base: 1, sm: 2 }}>
                      <NumberInput variant="default" label="Сумма" value={top.amount} onChange={(x) => setTopField('amount', Number(x) || 0)} min={app.product.min_amount} max={app.product.max_amount} step={50_000} suffix=" ₽" error={errFor('amount')} disabled={!editable} description={`от ${money(app.product.min_amount)} до ${money(app.product.max_amount)}`} />
                      <NumberInput variant="default" label="Срок, мес." value={top.term_months} onChange={(x) => setTopField('term_months', Number(x) || app.product.min_term)} min={app.product.min_term} max={app.product.max_term} error={errFor('term_months')} disabled={!editable} description={`от ${app.product.min_term} до ${app.product.max_term} мес.`} />
                    </SimpleGrid>
                    <Select variant="default" label="Цель" value={top.purpose} onChange={(x) => x && setTopField('purpose', x)} data={(app.product.purposes.length ? app.product.purposes : Object.keys(PURPOSES)).map((c) => ({ value: c, label: PURPOSES[c]?.title ?? c }))} error={errFor('purpose')} disabled={!editable} allowDeselect={false} />
                    <Textarea variant="default" label="На что именно пойдут деньги — необязательно" placeholder="Например: покупка кофемашины и холодильной витрины" value={top.purpose_text} onChange={(e) => setTopField('purpose_text', e.currentTarget.value)} autosize minRows={2} disabled={!editable} />
                  </Stack>
                </Collapse>
              </Plate>
            </Box>

            <FormSection
              id="company"
              title="Компания"
              open={!!open.company}
              onToggle={() => toggle('company')}
              done={!secHasErr('company')}
              summary={join(app.company.short_name, `ИНН ${app.company.inn}`, app.company.region_name, v('company', 'director_name') && `руководитель ${v('company', 'director_name')}`)}
            >
              <KV
                cols={2}
                items={[
                  ['Наименование', app.company.name],
                  ['ИНН / ОГРН', `${app.company.inn} / ${app.company.ogrn ?? '—'}`],
                  ['Дата регистрации', date(app.company.registration_date)],
                  ['Основной ОКВЭД', `${app.company.okved_code} ${app.company.okved_name ?? ''}`],
                  ['Регион', app.company.region_name],
                  ['Расчётный счёт', app.company.is_bank_client ? `в нашем банке${app.company.settlement_account ? `, ${app.company.settlement_account}` : ''}` : 'в другом банке'],
                ]}
              />
              <Text size="xs" c="dimmed" mt={10}>
                Из ЕГРЮЛ/ЕГРИП — менять не нужно.
              </Text>
              <SimpleGrid cols={{ base: 1, sm: 2 }} mt="lg" spacing="md" verticalSpacing="md">
                {text('company', 'director_name', 'Руководитель')}
                {text('company', 'actual_address', 'Фактический адрес')}
                <Box>
                  <NumberInput label="Сотрудников" value={(v('company', 'employees') as number) ?? ''} onChange={(x) => setField('company', 'employees', x === '' ? null : Number(x))} min={0} disabled={!editable} hideControls error={errFor('company.employees')} />
                </Box>
                {text('company', 'website', 'Сайт', { placeholder: 'необязательно' })}
              </SimpleGrid>
            </FormSection>

            <FormSection
              id="contact"
              title="Контактное лицо"
              sub="С кем связаться, если у банка появятся вопросы."
              open={!!open.contact}
              onToggle={() => toggle('contact')}
              done={!secHasErr('contact')}
              summary={join(v('contact', 'name'), v('contact', 'position'), v('contact', 'phone'), v('contact', 'email')) || 'Не заполнено'}
            >
              <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md" verticalSpacing="md">
                {text('contact', 'name', 'ФИО')}
                {text('contact', 'position', 'Должность')}
                {text('contact', 'phone', 'Телефон')}
                {text('contact', 'email', 'Электронная почта')}
              </SimpleGrid>
            </FormSection>

            <FormSection
              id="financials"
              title="Выручка и платежи"
              open={!!open.financials}
              onToggle={() => toggle('financials')}
              done={!secHasErr('financials')}
              summary={
                fin.monthly_revenue
                  ? join(`выручка ${money(Number(fin.monthly_revenue))} в месяц`, `платежи по кредитам ${money(Number(fin.existing_loans_monthly_payment) || 0)} в месяц`, app.company.is_bank_client ? 'по оборотам на счёте в банке' : app.statement ? 'по выписке' : '')
                  : 'Не заполнено'
              }
            >
              {app.company.is_bank_client ? (
                <Plate tone="ok" size="sm" style={{ marginBottom: 18 }}>
                  <Text size="sm">Подставили по оборотам на вашем расчётном счёте — подтверждать документами не нужно.</Text>
                </Plate>
              ) : (
                <Box mb={20}>
                  <Text size="sm" c="var(--ink-2)" mb={12}>
                    Счёт в другом банке — загрузите выписку за 12 месяцев, и система сама посчитает выручку и платежи. Или укажите цифры вручную.
                  </Text>
                  {app.statement ? <StatementCard st={app.statement} /> : editable && <DocDropzone appId={app.id} docType="bank_statement" onUploaded={onUploaded} />}
                  {!app.statement && (
                    <button type="button" className="link-btn" style={{ fontSize: 13, marginTop: 10, display: 'inline-flex', alignItems: 'center', gap: 6 }} onClick={() => api.download(`/api/v1/demo/sample-statement/${app.company.id}`, 'kl_to_1c.txt')}>
                      <IconDownload size={14} /> Скачать демо-выписку 1С для проверки
                    </button>
                  )}
                </Box>
              )}
              <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md" verticalSpacing="md">
                {money_('financials', 'monthly_revenue', 'Выручка в месяц')}
                {money_('financials', 'revenue_last_year', 'Выручка за прошлый год')}
                {money_('financials', 'existing_loans_monthly_payment', 'Платежи по текущим кредитам в месяц')}
                {money_('financials', 'net_profit_monthly', 'Чистая прибыль в месяц — необязательно')}
              </SimpleGrid>
            </FormSection>

            {collateralVisible ? (
              <FormSection
                id="collateral"
                title="Залог"
                sub={collateralNeeded ? `По этому продукту залог нужен от ${money(collateralFrom)}.` : 'Необязательно: с залогом можно получить больше и дешевле.'}
                open={!!open.collateral || (collateralNeeded && !hasCollateral)}
                onToggle={() => toggle('collateral')}
                done={hasCollateral && !secHasErr('collateral')}
                summary={hasCollateral ? join(COLLATERAL[String(v('collateral', 'type'))], v('collateral', 'value') && money(Number(v('collateral', 'value'))), v('collateral', 'description')) : undefined}
              >
                <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md" verticalSpacing="md">
                  <Select label="Вид залога" value={String(v('collateral', 'type') || 'none')} onChange={(x) => setField('collateral', 'type', x)} data={Object.entries(COLLATERAL).map(([value, label]) => ({ value, label }))} disabled={!editable} allowDeselect={false} error={errFor('collateral.type')} />
                  {hasCollateral && (
                    <>
                      {money_('collateral', 'value', 'Оценочная стоимость')}
                      {text('collateral', 'description', 'Описание')}
                    </>
                  )}
                </SimpleGrid>
              </FormSection>
            ) : (
              editable && (
                <Box className="form-section-plain">
                  <button type="button" className="link-btn" style={{ fontSize: 14 }} onClick={() => setOpen((o) => ({ ...o, collateral: true }))}>
                    Добавить залог
                  </button>
                  <Text span size="sm" c="dimmed">
                    {' '}
                    — с ним можно получить больше и дешевле
                  </Text>
                </Box>
              )
            )}

            {isLE && (
              <FormSection
                id="guarantor"
                title="Поручитель"
                sub="Для кредита компании нужно поручительство собственника. Данные — из ЕГРЮЛ и профиля."
                open={!!open.guarantor}
                onToggle={() => toggle('guarantor')}
                done={!secHasErr('guarantor')}
                summary={join(v('guarantor', 'full_name'), v('guarantor', 'share') !== '' && `доля ${v('guarantor', 'share')}%`, v('guarantor', 'inn') && `ИНН ${v('guarantor', 'inn')}`) || 'Не заполнено'}
              >
                <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md" verticalSpacing="md">
                  {text('guarantor', 'full_name', 'ФИО')}
                  {text('guarantor', 'inn', 'ИНН физического лица')}
                  {text('guarantor', 'birth_date', 'Дата рождения', { type: 'date' })}
                  <Box>
                    <NumberInput label="Доля в капитале, %" value={(v('guarantor', 'share') as number) ?? ''} onChange={(x) => setField('guarantor', 'share', x === '' ? null : Number(x))} min={0} max={100} disabled={!editable} hideControls error={errFor('guarantor.share')} />
                  </Box>
                </SimpleGrid>
              </FormSection>
            )}

            {app.checklist.length > 0 && (
              <FormSection
                id="documents"
                title="Документы"
                sub="Список собран под продукт, сумму и данные, которые уже есть у банка. Недостающее можно донести позже — банк пришлёт задачу."
                open={!!open.documents || missingDocs.length > 0}
                onToggle={() => toggle('documents')}
                done={missingDocs.length === 0}
                summary={missingDocs.length === 0 ? (app.documents.length ? `Загружено файлов: ${app.documents.length}` : 'Документы не нужны — банк видит обороты по счёту') : undefined}
              >
                <div className="rows">
                  {app.checklist.map((i) => {
                    const inFinancials = i.doc_type === 'bank_statement' && !app.company.is_bank_client;
                    return (
                      <Box key={i.doc_type} py={14}>
                        <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
                          <Box style={{ minWidth: 0 }}>
                            <Text fw={600} size="sm">
                              {i.title}
                            </Text>
                            <Text size="sm" c="dimmed">
                              {i.reason}
                            </Text>
                          </Box>
                          <Text size="sm" fw={500} c={i.satisfied ? 'ok' : i.required ? 'var(--warn-ink)' : 'dimmed'} style={{ flex: 'none' }}>
                            {i.satisfied ? (i.satisfied_by === 'internal_data' ? 'Не нужна' : 'Загружено') : i.required ? 'Нужно' : 'По желанию'}
                          </Text>
                        </Group>
                        {!i.satisfied && editable && !inFinancials && (
                          <Box mt={10}>
                            <DocDropzone appId={app.id} docType={i.doc_type} onUploaded={onUploaded} compact label={i.hint} />
                          </Box>
                        )}
                        {!i.satisfied && inFinancials && (
                          <button type="button" className="link-btn" style={{ fontSize: 13.5, marginTop: 8 }} onClick={() => goTo('financials.monthly_revenue')}>
                            Загрузить в разделе «Выручка и платежи»
                          </button>
                        )}
                      </Box>
                    );
                  })}
                </div>
                {app.documents.length > 0 && (
                  <Box mt="md">
                    <Text size="sm" fw={600} mb={4}>
                      Загруженные файлы
                    </Text>
                    <DocumentsList appId={app.id} docs={app.documents} onDeleted={setApp} canDelete={editable} />
                  </Box>
                )}
              </FormSection>
            )}
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <Box pos="sticky" top={92}>
            <Plate>
              <Text size="sm" c="dimmed">
                {app.product.kind === 'term_loan' ? 'Платёж в месяц' : 'Проценты в месяц при полном использовании'}
              </Text>
              <Money value={payment} prefix="≈" size={30} animate />
              <Text size="xs" c="dimmed" mt={4}>
                по ставке от {String(rate).replace('.', ',')}% · точные условия — в предложении банка
              </Text>
              <Box mt={20} pt={18} style={{ borderTop: '1px solid var(--line)' }}>
                {errs.length === 0 ? (
                  <Group gap={8} wrap="nowrap" align="flex-start">
                    <IconCheck size={18} color="var(--ok)" stroke={2.4} style={{ flex: 'none' }} />
                    <Text size="sm" fw={500}>
                      Всё заполнено.{' '}
                      {missingDocs.length ? `Не хватает: ${missingDocs.map((d) => d.title.toLowerCase()).join(', ')} — можно донести после проверки.` : 'Можно подписывать.'}
                    </Text>
                  </Group>
                ) : (
                  <Box>
                    <Text size="sm" fw={600}>
                      Осталось заполнить: {errs.length}
                    </Text>
                    <Stack gap={4} mt={8}>
                      {errs.slice(0, 6).map((e) => (
                        <button key={e.field} type="button" className="link-btn" style={{ fontSize: 13.5, textAlign: 'left' }} onClick={() => goTo(e.field)}>
                          {e.message}
                        </button>
                      ))}
                    </Stack>
                  </Box>
                )}
              </Box>
              {actionError && (
                <Alert color="bad" mt="md">
                  {actionError}
                </Alert>
              )}
              {mainCta && (
                <Box mt={20} visibleFrom="md">
                  {mainCta}
                </Box>
              )}
              <Text size="xs" c={saveError ? 'bad' : 'dimmed'} mt={10} ta="center">
                {saveState}
              </Text>
            </Plate>
            {!canSign && app.status === 'draft' && (
              <Text size="xs" c="dimmed" mt={12}>
                У вас нет права подписи: руководитель получит задачу в кабинете, проверит данные и отправит заявку.
              </Text>
            )}
          </Box>
        </Grid.Col>
      </Grid>

      {mainCta && (
        <Box className="sticky-cta" hiddenFrom="md">
          <Group justify="space-between" wrap="nowrap" gap="md">
            <Text size="sm" fw={500} style={{ flex: 'none' }}>
              {errs.length ? `Осталось: ${errs.length}` : 'Всё заполнено'}
            </Text>
            {canSign ? (
              <Button color="brand" size="md" style={{ flex: 1 }} maw={260} leftSection={<IconSignature size={18} />} onClick={openSign}>
                Подписать
              </Button>
            ) : (
              <Button size="md" style={{ flex: 1 }} maw={260} leftSection={<IconSend size={17} />} loading={busy} onClick={() => (errs.length ? goTo(errs[0].field) : action('send-for-signature'))}>
                На подпись
              </Button>
            )}
          </Group>
        </Box>
      )}

      <SignModal
        opened={sign}
        onClose={() => setSign(false)}
        title="Подписание заявки"
        step={`Шаг 3 из 3 · ${FLOW[2]}`}
        documents={docs}
        consents={{
          bki: `Даю согласие на получение кредитного отчёта из бюро кредитных историй — заёмщика${isLE ? ' и поручителя' : ''} (218-ФЗ)`,
          pd: 'Даю согласие на обработку персональных данных в целях рассмотрения заявки (152-ФЗ)',
        }}
        onSign={doSubmit}
        onDone={afterSubmit}
        doneText={{ title: 'Заявка отправлена', text: 'Подписали и передали на проверку. Статус будет обновляться на ваших глазах.' }}
        confirmLabel="Подписать и отправить"
      />
    </Box>
  );
}
