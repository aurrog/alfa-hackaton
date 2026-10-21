/** HTTP-клиент API: токен, ошибки RFC 7807, идемпотентность, загрузка файлов. */

const TOKEN_KEY = 'scc.token';

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

let token: string | null = readToken();

export function setToken(t: string | null) {
  token = t;
  try {
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* хранилище недоступно (приватный режим) — токен живёт до перезагрузки */
  }
}

export const getToken = () => token;

export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  status: number;
  code: string;
  errors: FieldError[];
  body: Record<string, unknown>;
  constructor(status: number, body: Record<string, unknown>) {
    super((body.detail as string) || (body.title as string) || `Ошибка ${status}`);
    this.status = status;
    this.code = (body.code as string) || 'error';
    this.errors = (body.errors as FieldError[]) || [];
    this.body = body;
  }
}

/** UUID для Idempotency-Key (randomUUID недоступен вне защищённого контекста — например, по http на IP). */
export function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    try {
      return crypto.randomUUID();
    } catch {
      /* fallthrough */
    }
  }
  const b = new Uint8Array(16);
  (typeof crypto !== 'undefined' ? crypto : { getRandomValues: (a: Uint8Array) => a.map(() => Math.floor(Math.random() * 256)) }).getRandomValues(b);
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

let onUnauthorized: (() => void) | null = null;
export const setUnauthorizedHandler = (fn: () => void) => {
  onUnauthorized = fn;
};

interface Opts {
  body?: unknown;
  form?: FormData;
  idempotent?: boolean;
  params?: Record<string, string | number | boolean | undefined | null>;
  raw?: boolean;
}

async function request<T>(method: string, path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.idempotent) headers['Idempotency-Key'] = uuid();
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  let url = path;
  if (opts.params) {
    const q = new URLSearchParams();
    Object.entries(opts.params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.set(k, String(v));
    });
    const s = q.toString();
    if (s) url += `?${s}`;
  }
  let res: Response;
  try {
    res = await fetch(url, { method, headers, body });
  } catch {
    throw new ApiError(0, { detail: 'Нет связи с сервером. Проверьте подключение и повторите.', code: 'network' });
  }
  if (res.status === 401 && token) {
    setToken(null);
    onUnauthorized?.();
  }
  if (!res.ok) {
    let data: Record<string, unknown> = {};
    try {
      data = await res.json();
    } catch {
      data = { detail: `Ошибка ${res.status}` };
    }
    throw new ApiError(res.status, data);
  }
  if (opts.raw) return res as unknown as T;
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}

export const api = {
  get: <T>(path: string, params?: Opts['params']) => request<T>('GET', path, { params }),
  post: <T>(path: string, body?: unknown, opts: Omit<Opts, 'body'> = {}) => request<T>('POST', path, { ...opts, body }),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, { body }),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, { body }),
  del: <T>(path: string) => request<T>('DELETE', path),
  upload: <T>(path: string, form: FormData) => request<T>('POST', path, { form }),
  /** Скачать файл с авторизацией (ссылкой <a href> заголовок не передать). */
  async download(path: string, fallbackName: string) {
    const res = await request<Response>('GET', path, { raw: true });
    const blob = await res.blob();
    const cd = res.headers.get('content-disposition') || '';
    const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
    const name = m ? decodeURIComponent(m[1]) : fallbackName;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 1000);
  },
  async blob(path: string): Promise<Blob> {
    const res = await request<Response>('GET', path, { raw: true });
    return res.blob();
  },
};

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.errors.length) return `${e.message}: ${e.errors.map((x) => x.message).join('; ')}`;
    return e.message;
  }
  return e instanceof Error ? e.message : 'Неизвестная ошибка';
}
