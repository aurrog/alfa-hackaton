export const PURPOSES: Record<string, { title: string; hint: string; icon: string }> = {
  working_capital: { title: 'Пополнить оборот', hint: 'Закупка товара и сырья, запасы, зарплаты', icon: 'box' },
  equipment: { title: 'Купить оборудование', hint: 'Станки, техника, транспорт, кассы', icon: 'tool' },
  cash_gap: { title: 'Закрыть кассовый разрыв', hint: 'Регулярно и ненадолго, пока покупатели не заплатили', icon: 'clock' },
  contract: { title: 'Исполнить контракт', hint: 'Госзаказ или крупный заказчик', icon: 'file' },
  expansion: { title: 'Развить бизнес', hint: 'Новая точка, ремонт, новое направление', icon: 'rocket' },
  any: { title: 'Другие цели', hint: 'Любые законные цели бизнеса', icon: 'dots' },
};

export const COLLATERAL: Record<string, string> = {
  none: 'Без залога',
  real_estate: 'Недвижимость',
  equipment: 'Оборудование',
  vehicle: 'Транспорт',
  goods: 'Товары в обороте',
  guarantee_fund: 'Поручительство гарантийного фонда',
};

export const DOC_TYPES: Record<string, string> = {
  bank_statement: 'Выписка по расчётному счёту',
  financial_statements: 'Бухгалтерская отчётность',
  collateral_docs: 'Документы по залогу',
  purchase_contract: 'Договор или счёт на приобретение',
  state_contract: 'Контракт с заказчиком',
  explanation: 'Пояснение',
  other: 'Прочие документы',
};

export const PRODUCT_KIND: Record<string, string> = {
  term_loan: 'Срочный кредит',
  overdraft: 'Овердрафт',
  credit_line: 'Кредитная линия',
};

export const LEVELS: Record<string, string> = {
  auto: 'Автоматически',
  analyst: 'Аналитик',
  senior_analyst: 'Старший аналитик',
  committee: 'Кредитный комитет',
};

export const OUTCOME: Record<string, { title: string; short: string; color: string }> = {
  approve: { title: 'Одобрить', short: 'Одобрить', color: 'ok' },
  counter_offer: { title: 'Одобрить на изменённых условиях', short: 'Другие условия', color: 'ok' },
  decline: { title: 'Отказать', short: 'Отказать', color: 'bad' },
  refer: { title: 'Ручная проверка', short: 'Ручная проверка', color: 'info' },
};

export const CHECK_RESULT: Record<string, { title: string; color: string }> = {
  pass: { title: 'Пройдена', color: 'ok' },
  warn: { title: 'Внимание', color: 'warn' },
  fail: { title: 'Не пройдена', color: 'bad' },
  unavailable: { title: 'Нет данных', color: '' },
  info: { title: 'Учтено', color: 'info' },
};

export const SOURCE_STATUS: Record<string, { title: string; color: string }> = {
  ok: { title: 'Получено', color: 'ok' },
  not_found: { title: 'Нет записей', color: '' },
  retrying: { title: 'Повтор', color: 'warn' },
  unavailable: { title: 'Недоступен', color: 'bad' },
  error: { title: 'Ошибка', color: 'bad' },
  timeout: { title: 'Таймаут', color: 'bad' },
  circuit_open: { title: 'Предохранитель', color: 'bad' },
  rejected: { title: 'Отклонено', color: 'warn' },
};

/** Цвет грейда риска (фон квадратика с буквой). */
export const GRADE_HEX: Record<string, string> = { A: '#149c55', B: '#56b37a', C: '#d9a400', D: '#f08a00', E: '#d92d20' };

/** Тон статуса (поле status_tone из API) → класс состояния: warn | info | ok | bad | '' (нейтральный). */
export const TONE: Record<string, string> = {
  gray: '', yellow: 'warn', orange: 'warn', blue: 'info', violet: 'info', green: 'ok', teal: 'ok', red: 'bad',
};

export const MSP: Record<string, string> = { micro: 'Микропредприятие', small: 'Малое предприятие', medium: 'Среднее предприятие' };
