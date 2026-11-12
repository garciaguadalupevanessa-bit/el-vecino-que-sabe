// Browser persistence (RF-09). The storage object is injected so this stays testable.
// Every access is wrapped: storage can be missing, full or blocked.

const KEY_PROFILE = 'evqs.profile.v1';
const KEY_MESSAGES = 'evqs.messages.v1';
const KEY_RESULTS = 'evqs.results.v1';
const KEY_VOICE = 'evqs.voice.v1';
const KEY_CONVERSATIONS = 'evqs.conversations.v1';
const KEY_UI = 'evqs.ui.v1';
const KEY_DEMO = 'evqs.demo.v1';
export const STORAGE_KEYS = [KEY_PROFILE, KEY_MESSAGES, KEY_RESULTS, KEY_VOICE, KEY_CONVERSATIONS, KEY_UI, KEY_DEMO];

const MAX_STORED_MESSAGES = 60;

function read(storage, key, fallback) {
  try {
    const raw = storage?.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function write(storage, key, value) {
  try {
    storage?.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function loadState(storage) {
  const profile = read(storage, KEY_PROFILE, {});
  const messages = read(storage, KEY_MESSAGES, []);
  const results = read(storage, KEY_RESULTS, null);
  return {
    profile: profile && typeof profile === 'object' && !Array.isArray(profile) ? profile : {},
    messages: Array.isArray(messages)
      ? messages.filter((m) => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string')
      : [],
    results: results && typeof results === 'object' ? results : null,
  };
}

export const saveProfile = (storage, profile) => write(storage, KEY_PROFILE, profile);
export const saveMessages = (storage, messages) => write(storage, KEY_MESSAGES, messages.slice(-MAX_STORED_MESSAGES));
export const saveResults = (storage, results) => write(storage, KEY_RESULTS, results);
export const loadConversations = (storage) => read(storage, KEY_CONVERSATIONS, null);
export const saveConversations = (storage, state) => write(storage, KEY_CONVERSATIONS, state);
export const loadUi = (storage) => read(storage, KEY_UI, {});
/** Subscription preview state (no real payments): { plan: 'gratis' | 'pro', method }. */
export const loadDemo = (storage) => read(storage, KEY_DEMO, { plan: 'gratis' });
export const saveDemo = (storage, demo) => write(storage, KEY_DEMO, demo);
export const saveUi = (storage, ui) => write(storage, KEY_UI, ui);
/** The single-chat keys from the first version, removed once migrated. */
export function dropLegacyChat(storage) {
  for (const key of [KEY_MESSAGES, KEY_RESULTS]) {
    try { storage?.removeItem(key); } catch { /* ignore */ }
  }
}
export const loadVoiceSettings = (storage) => read(storage, KEY_VOICE, null);
export const saveVoiceSettings = (storage, settings) => write(storage, KEY_VOICE, settings);

/** "Borrar mis datos" */
export function clearAll(storage) {
  for (const key of STORAGE_KEYS) {
    try {
      storage?.removeItem(key);
    } catch {
      /* ignore */
    }
  }
}
