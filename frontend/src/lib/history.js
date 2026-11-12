import { toBackendProfile } from './backendContract.js';

// Builds the POST /api/chat payload within the backend limits (spec §4.4):
// 1–30 messages, role user|assistant (user ≤ 4000 chars, assistant ≤ 8000), last one from the user.

export const MAX_MESSAGES = 30;
// What we actually send: the backend accepts 30 messages, but Groq's free tier caps a
// request at ~8000 tokens and the system prompt + tools already use ~5000. The agent only
// needs the recent turns (the farm profile travels separately), so keep the payload small.
export const HISTORY_SENT = 8;
export const ASSISTANT_CHARS_SENT = 1200;
// Same limits as backend/app/models/api.py (MAX_USER_CHARS / MAX_ASSISTANT_CHARS).
export const MAX_CHARS = 4000;
export const MAX_ASSISTANT_CHARS = 8000;

export function validateUserText(text) {
  const t = typeof text === 'string' ? text.trim() : '';
  if (!t) return 'Escribe tu pregunta antes de enviarla.';
  if (t.length > MAX_CHARS) return `Tu mensaje es muy largo. Usa como máximo ${MAX_CHARS} caracteres.`;
  return null;
}

function shorten(m) {
  const text = m.content.trim();
  if (m.role === 'user') return text.slice(0, MAX_CHARS);
  // Earlier answers: the start carries the substance; the rest is links and disclaimers.
  return text.length > ASSISTANT_CHARS_SENT ? `${text.slice(0, ASSISTANT_CHARS_SENT).trimEnd()}…` : text;
}

export function buildMessages(history) {
  let msgs = history
    .filter((m) => (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string' && m.content.trim())
    .map((m) => ({ role: m.role, content: shorten(m) }));

  // Drop trailing assistant messages so the last one is the user's.
  while (msgs.length && msgs[msgs.length - 1].role !== 'user') msgs.pop();
  msgs = msgs.slice(-Math.min(MAX_MESSAGES, HISTORY_SENT));
  // The window must not start with a reply whose question was cut off.
  while (msgs.length > 1 && msgs[0].role !== 'user') msgs.shift();
  return msgs;
}

/** POST /api/chat body. `profile` is the UI profile; it is sent in the backend's field names. */
export function buildChatPayload(history, profile) {
  const payload = { messages: buildMessages(history) };
  const backendProfile = toBackendProfile(profile ?? {});
  if (Object.keys(backendProfile).length) payload.profile = backendProfile;
  return payload;
}
