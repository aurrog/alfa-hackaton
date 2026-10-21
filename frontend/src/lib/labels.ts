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

export const OUTCOME: Record<string, { title: string; color: string }> = {
  approve: { title: 'Одобрить', color: 'lime' },
  counter_offer: { title: 'Одобрить на изменённых условиях', color: 'lime' },
  decline: { title: 'Отказать', color: 'signal' },
  refer: { title: 'Ручная проверка', color: 'violet' },
};

export const CHECK_RESULT: Record<string, { title: string; color: string }> = {
  pass: { title: 'Пройдена', color: 'lime' },
  warn: { title: 'Внимание', color: 'amber' },
  fail: { title: 'Не пройдена', color: 'signal' },
  unavailable: { title: 'Нет данных', color: 'gray' },
  info: { title: 'Учтено', color: 'route' },
};

export const SOURCE_STATUS: Record<string, { title: string; color: string }> = {
  ok: { title: 'Получено', color: 'lime' },
  not_found: { title: 'Нет записей', color: 'gray' },
  retrying: { title: 'Повтор', color: 'amber' },
  unavailable: { title: 'Недоступен', color: 'signal' },
  error: { title: 'Ошибка', color: 'signal' },
  timeout: { title: 'Таймаут', color: 'signal' },
  circuit_open: { title: 'Предохранитель', color: 'signal' },
  rejected: { title: 'Отклонено', color: 'amber' },
};

export const GRADE_COLOR: Record<string, string> = { A: 'lime', B: 'teal', C: 'amber', D: 'orange', E: 'signal' };

/** Тон статуса (поле status_tone из API) → цвет Mantine. */
export const TONE: Record<string, string> = {
  gray: 'gray', yellow: 'amber', blue: 'route', orange: 'amber', violet: 'violet', green: 'lime', teal: 'teal', red: 'signal',
};

export const MSP: Record<string, string> = { micro: 'Микропредприятие', small: 'Малое предприятие', medium: 'Среднее предприятие' };
