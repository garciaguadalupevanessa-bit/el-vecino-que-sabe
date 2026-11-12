import { toBackendProfile } from './backendContract.js';

// Builds the POST /api/chat payload within the backend limits (spec §4.4):
// 1–30 messages, role user|assistant (user ≤ 4000 chars, assistant ≤ 8000), last one from the user.

export const MAX_MESSAGES = 30;
// Same limits as backend/app/models/api.py (MAX_USER_CHARS / MAX_ASSISTANT_CHARS).
export const MAX_CHARS = 4000;
export const MAX_ASSISTANT_CHARS = 8000;

export function validateUserText(text) {
  const t = typeof text === 'string' ? text.trim() : '';
  if (!t) return 'Escribe tu pregunta antes de enviarla.';
  if (t.length > MAX_CHARS) return `Tu mensaje es muy largo. Usa como máximo ${MAX_CHARS} caracteres.`;
  return null;
}

export function buildMessages(history) {
  let msgs = history
    .filter((m) => (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string' && m.content.trim())
    .map((m) => ({ role: m.role, content: m.content.trim().slice(0, m.role === 'user' ? MAX_CHARS : MAX_ASSISTANT_CHARS) }));

  // Drop trailing assistant messages so the last one is the user's.
  while (msgs.length && msgs[msgs.length - 1].role !== 'user') msgs.pop();
  msgs = msgs.slice(-MAX_MESSAGES);
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
