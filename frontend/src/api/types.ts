/* Типы ответов API (подмножество полей, которые использует интерфейс). Полный контракт — /api/docs. */

export interface User {
  id: string;
  email: string;
  full_name: string;
  kind: 'client' | 'bank';
  bank_role?: string | null;
  role_title?: string | null;
  position?: string | null;
  authority_limit?: number | null;
  phone?: string | null;
}

export interface Membership {
  role: string;
  role_title: string;
  can_sign: boolean;
  position?: string | null;
}

export interface Company {
  id: string;
  inn: string;
  ogrn?: string;
  kpp?: string | null;
  legal_form: 'IP' | 'LE';
  legal_form_title: string;
  name: string;
  short_name: string;
  registration_date?: string;
  address?: string;
  region_name: string;
  okved_code?: string;
  okved_name?: string;
  sector: string;
  status: string;
  director_name?: string;
  msp_category?: string | null;
  is_bank_client: boolean;
  bank_client_since?: string | null;
  settlement_account?: string | null;
  membership?: Membership;
}

export interface Preapproved {
  product_code: string;
  product_name: string;
  max_amount: number;
  term_months: number;
  rate_from: number;
  monthly_payment: number;
  valid_until: string;
  basis: string[];
}

export interface CompanyDetails extends Company {
  preapproved: Preapproved[];
  summary: { applications: number; active_applications: number; loans: number; loans_amount: number; monthly_payments: number };
}

export interface Stage {
  key: string;
  title: string;
  state: 'done' | 'current' | 'upcoming' | 'failed' | 'skipped';
}

export interface ScheduleRow {
  n: number;
  date: string;
  payment: number;
  principal: number;
  interest: number;
  balance: number;
}

export interface Offer {
  id: string;
  amount: number;
  term_months: number;
  rate: number;
  monthly_payment: number;
  total_payment: number;
  overpayment: number;
  effective_rate: number;
  conditions: string[];
  changes: string[];
  is_counter: boolean;
  status: string;
  expires_at: string;
  payment_kind: 'annuity' | 'interest_only';
  schedule: ScheduleRow[];
}

export interface ChecklistItem {
  doc_type: string;
  title: string;
  hint: string;
  required: boolean;
  reason: string;
  satisfied: boolean;
  satisfied_by?: string | null;
}

export interface DocumentInfo {
  id: string;
  doc_type: string;
  doc_title: string;
  file_name: string;
  size_bytes: number;
  status: string;
  review_comment?: string | null;
  created_at: string;
  parsed?: boolean;
}

export interface TaskInfo {
  id: string;
  kind: 'document' | 'question';
  doc_type?: string | null;
  title: string;
  description?: string | null;
  status: string;
  answer_text?: string | null;
  from_bank: boolean;
  created_at: string;
}

export interface EventInfo {
  id: number;
  kind: string;
  title: string;
  details?: string | null;
  actor_type: string;
  actor_name?: string | null;
  to_status?: string | null;
  created_at: string;
}

export interface Explanation {
  outcome: 'approve' | 'counter_offer' | 'decline';
  headline: string;
  reasons: { code: string; text: string; hint?: string | null }[];
  positives: { title: string; value: string; label: string }[];
  negatives: { title: string; value: string; label: string; hint?: string }[];
  plan: string[];
  can_reapply_after?: string | null;
}

export interface Loan {
  id: string;
  application_id: string;
  contract_number: string;
  loan_account: string;
  settlement_account?: string;
  amount: number;
  rate: number;
  term_months: number;
  monthly_payment: number;
  schedule: ScheduleRow[];
  status: string;
  issued_at: string;
  product_name: string;
  product_kind: string;
  next_payment?: ScheduleRow | null;
}

export interface StatementInfo {
  format: string;
  account?: string;
  period: { from: string; to: string };
  months_covered: number;
  operations: number;
  months: { month: string; incoming: number; outgoing: number }[];
  avg_monthly_incoming: number;
  annualized_revenue: number;
  turnover_volatility?: number | null;
  debt_payments_monthly: number;
  own_transfers_excluded: number;
  loan_proceeds_excluded: number;
  top_payer_share?: number | null;
  payers_count: number;
  warnings: string[];
}

export interface Application {
  id: string;
  number: string;
  status: string;
  status_label: string;
  status_hint: string;
  status_tone: string;
  waiting: 'client' | 'bank' | 'system' | 'none';
  terminal: boolean;
  sla_due_at?: string | null;
  version: number;
  company: Company;
  product: { code: string; name: string; kind: string; min_amount: number; max_amount: number; min_term: number; max_term: number; purposes: string[]; collateral_required_from?: number | null };
  amount: number;
  term_months: number;
  purpose: string;
  purpose_title: string;
  purpose_text?: string | null;
  preapproved: boolean;
  form: Record<string, Record<string, unknown>>;
  prefill: Record<string, { source: string; at?: string; edited?: boolean }>;
  statement?: StatementInfo | null;
  validation_errors: { field: string; message: string }[];
  checklist: ChecklistItem[];
  stages: Stage[];
  next_action?: string | null;
  actions: string[];
  events: EventInfo[];
  documents: DocumentInfo[];
  tasks: TaskInfo[];
  offer?: Offer | null;
  explanation?: Explanation | null;
  signatures: { document_kind: string; document_title: string; document_hash: string; signer_name: string; signed_at: string }[];
  loan?: Loan | null;
  created_at: string;
  submitted_at?: string | null;
  decided_at?: string | null;
  issued_at?: string | null;
}

export interface ApplicationSummary {
  id: string;
  number: string;
  status: string;
  status_label: string;
  status_hint: string;
  status_tone: string;
  waiting: string;
  terminal: boolean;
  sla_due_at?: string | null;
  product_code: string;
  product_name: string;
  amount: number;
  term_months: number;
  created_at: string;
  submitted_at?: string | null;
  company_name: string;
  next_action?: string | null;
  open_tasks: number;
  offer?: { amount: number; term_months: number; rate: number; monthly_payment: number; is_counter: boolean } | null;
}

export interface Product {
  code: string;
  name: string;
  tagline: string;
  description: string;
  kind: string;
  purposes: { code: string; title: string }[];
  min_amount: number;
  max_amount: number;
  min_term: number;
  max_term: number;
  rate_from: number;
  features: string[];
  decision_time: string;
  gov_program: boolean;
  collateral_required_from?: number | null;
  requires_bank_client: boolean;
  eligible: boolean;
  blockers: string[];
}

export interface Recommendation {
  code: string;
  name: string;
  tagline: string;
  kind: string;
  eligible: boolean;
  best?: boolean;
  score: number;
  pros: string[];
  warnings: string[];
  blockers: string[];
  rate_from: number;
  term_months: number;
  amount: number;
  monthly_payment_from: number;
  payment_kind: string;
  decision_time: string;
  features: string[];
  min_term: number;
  max_term: number;
  min_amount: number;
  max_amount: number;
  gov_program: boolean;
}

export interface NotificationItem {
  id: string;
  kind: string;
  title: string;
  body?: string | null;
  link?: string | null;
  read: boolean;
  created_at: string;
}

export interface FeedCard {
  id: string;
  type: 'news' | 'insight';
  title: string;
  summary: string;
  body?: string;
  category: string;
  category_title: string;
  topics: string[];
  published_at?: string;
  source?: string;
  cta?: { label: string; link: string } | null;
  relevance: number;
  why: string[];
  liked?: boolean;
}

export interface Feed {
  profile: { sector: string; region: string; legal_form: string; msp_category?: string | null; bank_client: boolean; gov_priority: boolean; stages: string[]; learned_topics: Record<string, number> };
  cards: FeedCard[];
  topics: { code: string; title: string }[];
  selected_topics: string[];
}

// ------------------------------------------------------------------ банк
export interface QueueItem {
  id: string;
  number: string;
  company_name: string;
  inn: string;
  product_name: string;
  amount: number;
  term_months: number;
  status: string;
  status_label: string;
  status_tone: string;
  risk_grade?: string | null;
  score?: number | null;
  review_level?: string | null;
  assigned_name?: string | null;
  sla_due_at?: string | null;
  sla_state: 'ok' | 'warning' | 'breached' | 'none';
  submitted_at?: string | null;
  manual_reasons: string[];
  recommendation?: string | null;
}

export interface Factor {
  name: string;
  title: string;
  source: string;
  display_value: string;
  bin_label: string;
  points: number;
  max_points: number;
  lost_points: number;
  client_hint: string;
  missing: boolean;
}

// Досье — структура крупная, типизируем выборочно
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Dossier = Record<string, any>;
