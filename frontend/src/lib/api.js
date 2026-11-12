// API client. The browser only talks to /api/* (nginx or the Vite proxy).

import { normalizeChatResponse, normalizeAid } from './aids.js';

export const CHAT_TIMEOUT_MS = 90_000;

export class ApiError extends Error {
  constructor(kind, message, status = null) {
    super(message);
    this.kind = kind; // 'timeout' | 'network' | 'validation' | 'ai' | 'not_found' | 'server'
    this.status = status;
  }
}

const MESSAGES = {
  timeout: 'La respuesta está tardando más de lo normal. Tu pregunta sigue aquí: puedes volver a intentarlo.',
  network: 'Sin conexión con el servicio. Tu pregunta sigue aquí: puedes volver a intentarlo en unos momentos.',
  validation: 'Algún dato no es válido. Revisa «Mi explotación» y tu mensaje, y vuelve a intentarlo.',
  ai: 'Ahora mismo no podemos completar la búsqueda. Tu pregunta sigue aquí. Puedes volver a intentarlo en unos momentos.',
  not_found: 'No hemos encontrado esa ayuda.',
  server: 'Ha fallado algo en el servicio. Tu pregunta sigue aquí: puedes volver a intentarlo.',
};

function detailText(body) {
  const d = body?.detail ?? body?.message ?? body?.error;
  if (typeof d === 'string') return d;
  // FastAPI 422: detail is a list of { loc, msg }.
  if (Array.isArray(d) && d.length) return null;
  return null;
}

export async function errorFromResponse(res) {
  let body = null;
  try { body = await res.json(); } catch { /* not JSON */ }
  const detail = detailText(body);
  if (res.status === 422) return new ApiError('validation', MESSAGES.validation, 422);
  if (res.status === 404) return new ApiError('not_found', MESSAGES.not_found, 404);
  // 502 messages are written for the user by the backend (spec §4.8): show them as they are.
  if (res.status === 502 || res.status === 503) return new ApiError('ai', detail || MESSAGES.ai, res.status);
  return new ApiError('server', MESSAGES.server, res.status);
}

async function request(path, { method = 'GET', body, timeoutMs = 15_000, fetchImpl = globalThis.fetch, signal } = {}) {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  const onAbort = () => controller.abort();
  signal?.addEventListener('abort', onAbort);
  try {
    const res = await fetchImpl(path, {
      method,
      headers: body ? { 'Content-Type': 'application/json', Accept: 'application/json' } : { Accept: 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    if (!res.ok) throw await errorFromResponse(res);
    return await res.json();
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (timedOut) throw new ApiError('timeout', MESSAGES.timeout);
    if (signal?.aborted) throw new ApiError('network', 'Búsqueda cancelada.');
    throw new ApiError('network', MESSAGES.network);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
}

export async function sendChat(payload, opts = {}) {
  const data = await request('/api/chat', { method: 'POST', body: payload, timeoutMs: CHAT_TIMEOUT_MS, ...opts });
  return normalizeChatResponse(data);
}

export async function getAid(id, opts = {}) {
  const data = await request(`/api/aids/${encodeURIComponent(id)}`, opts);
  return normalizeAid(data);
}

export async function getHealth(opts = {}) {
  return request('/api/health', { timeoutMs: 8_000, ...opts });
}

/**
 * Voice option A: POST /api/transcribe (multipart, field "audio") -> { text }.
 * The audio is not stored: the backend transcribes it with Groq Whisper and discards it.
 */
export async function transcribeAudio(blob, { fetchImpl = globalThis.fetch, timeoutMs = 45_000, signal } = {}) {
  const form = new FormData();
  const ext = (blob.type.split('/')[1] || 'webm').split(';')[0];
  form.append('audio', blob, `mensaje.${ext}`);
  form.append('language', 'es');
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  signal?.addEventListener('abort', () => controller.abort());
  let res;
  try {
    res = await fetchImpl('/api/transcribe', { method: 'POST', body: form, signal: controller.signal });
  } catch {
    throw new ApiError(timedOut ? 'timeout' : 'network', 'No he podido convertir tu voz en texto.');
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 404 || res.status === 405 || res.status === 501) {
    throw new ApiError('unavailable', 'El reconocimiento de voz del servidor todavía no está disponible.', res.status);
  }
  if (!res.ok) throw await errorFromResponse(res);
  let data = null;
  try { data = await res.json(); } catch { /* ignore */ }
  const text = typeof data?.text === 'string' ? data.text.trim() : '';
  if (!text) throw new ApiError('empty', 'No he captado ninguna palabra.');
  return text;
}
