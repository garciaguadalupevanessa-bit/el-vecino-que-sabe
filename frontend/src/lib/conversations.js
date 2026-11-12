// "Historial de chats": several conversations kept only in this browser.
// Pure functions; App keeps the active conversation's messages/results in state and
// writes them back here.

export const MAX_CONVERSATIONS = 20;
export const MAX_MESSAGES_PER_CONVERSATION = 60;

export function newConversationId(now = Date.now()) {
  return `c${now.toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

export function createConversation(now = Date.now()) {
  return { id: newConversationId(now), createdAt: now, updatedAt: now, messages: [], results: null };
}

/** Title = first user message, shortened. */
export function titleOf(conv) {
  const first = conv.messages?.find((m) => m.role === 'user')?.content?.trim();
  if (!first) return 'Conversación nueva';
  return first.length > 60 ? `${first.slice(0, 57).trimEnd()}…` : first;
}

export const hasUserMessages = (conv) => Boolean(conv?.messages?.some((m) => m.role === 'user'));

function cleanMessages(messages) {
  return (Array.isArray(messages) ? messages : [])
    .filter((m) => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string')
    .slice(-MAX_MESSAGES_PER_CONVERSATION);
}

function cleanConversation(c) {
  if (!c || typeof c !== 'object' || typeof c.id !== 'string') return null;
  const createdAt = Number.isFinite(c.createdAt) ? c.createdAt : 0;
  return {
    id: c.id,
    createdAt,
    updatedAt: Number.isFinite(c.updatedAt) ? c.updatedAt : createdAt,
    messages: cleanMessages(c.messages),
    results: c.results && typeof c.results === 'object' ? c.results : null,
  };
}

/** Validates what came from localStorage; falls back to the old single chat (v1 keys). */
export function restoreConversations(stored, legacy = {}, now = Date.now()) {
  const list = (Array.isArray(stored?.list) ? stored.list : []).map(cleanConversation).filter(Boolean);
  if (list.length) {
    const currentId = list.some((c) => c.id === stored.currentId) ? stored.currentId : sortByRecent(list)[0].id;
    return { currentId, list };
  }
  const conv = createConversation(now);
  conv.messages = cleanMessages(legacy.messages);
  conv.results = legacy.results ?? null;
  return { currentId: conv.id, list: [conv] };
}

export function sortByRecent(list) {
  return [...list].sort((a, b) => b.updatedAt - a.updatedAt);
}

export function getCurrent(state) {
  return state.list.find((c) => c.id === state.currentId) ?? state.list[0];
}

/** Writes the active conversation back; keeps at most MAX_CONVERSATIONS (drops the oldest). */
export function updateCurrent(state, { messages, results }, now = Date.now()) {
  const list = state.list.map((c) => {
    if (c.id !== state.currentId) return c;
    const changed = c.messages.length !== messages.length || c.results !== results;
    return { ...c, messages: cleanMessages(messages), results: results ?? null, updatedAt: changed ? now : c.updatedAt };
  });
  return { ...state, list: trim(list, state.currentId) };
}

function trim(list, keepId) {
  if (list.length <= MAX_CONVERSATIONS) return list;
  const keep = sortByRecent(list).filter((c, i) => i < MAX_CONVERSATIONS || c.id === keepId);
  return list.filter((c) => keep.includes(c));
}

/** "Nueva conversación": reuses the current one if it is still empty. */
export function startNew(state, now = Date.now()) {
  const current = getCurrent(state);
  if (current && !hasUserMessages(current)) return state;
  const conv = createConversation(now);
  return { currentId: conv.id, list: trim([...state.list, conv], conv.id) };
}

export function select(state, id) {
  return state.list.some((c) => c.id === id) ? { ...state, currentId: id } : state;
}

export function remove(state, id, now = Date.now()) {
  const list = state.list.filter((c) => c.id !== id);
  if (!list.length) {
    const conv = createConversation(now);
    return { currentId: conv.id, list: [conv] };
  }
  const currentId = state.currentId === id ? sortByRecent(list)[0].id : state.currentId;
  return { currentId, list };
}

/** Entries shown in "Historial de chats" (empty conversations are hidden). */
export function historyEntries(state) {
  return sortByRecent(state.list.filter(hasUserMessages)).map((c) => ({
    id: c.id,
    title: titleOf(c),
    updatedAt: c.updatedAt,
    messages: c.messages.filter((m) => m.role === 'user').length,
    aids: c.results?.aids?.length ?? 0,
    current: c.id === state.currentId,
  }));
}

/** "hoy, 11:30" · "ayer, 09:05" · "3 nov, 18:20" */
export function formatWhen(ts, now = Date.now()) {
  const d = new Date(ts);
  const n = new Date(now);
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((day(n) - day(d)) / 86_400_000);
  if (diff === 0) return `hoy, ${hm}`;
  if (diff === 1) return `ayer, ${hm}`;
  const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic'];
  return `${d.getDate()} ${months[d.getMonth()]}${d.getFullYear() !== n.getFullYear() ? ` ${d.getFullYear()}` : ''}, ${hm}`;
}
