// Builds the POST /api/chat payload within the backend limits (spec §4.4):
// 1–30 messages, role user|assistant, 1–2000 chars each, last one from the user.

export const MAX_MESSAGES = 30;
export const MAX_CHARS = 2000;

export function validateUserText(text) {
  const t = typeof text === 'string' ? text.trim() : '';
  if (!t) return 'Escribe tu pregunta antes de enviarla.';
  if (t.length > MAX_CHARS) return `Tu mensaje es muy largo. Usa como máximo ${MAX_CHARS} caracteres.`;
  return null;
}

export function buildMessages(history) {
  let msgs = history
    .filter((m) => (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string' && m.content.trim())
    .map((m) => ({ role: m.role, content: m.content.trim().slice(0, MAX_CHARS) }));

  // Drop trailing assistant messages so the last one is the user's.
  while (msgs.length && msgs[msgs.length - 1].role !== 'user') msgs.pop();
  msgs = msgs.slice(-MAX_MESSAGES);
  // The window must not start with a reply whose question was cut off.
  while (msgs.length > 1 && msgs[0].role !== 'user') msgs.shift();
  return msgs;
}

export function buildChatPayload(history, profile) {
  const payload = { messages: buildMessages(history) };
  if (profile && Object.keys(profile).length) payload.profile = profile;
  return payload;
}
