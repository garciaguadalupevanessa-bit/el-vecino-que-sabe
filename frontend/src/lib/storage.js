// Browser persistence (RF-09). The storage object is injected so this stays testable.
// Every access is wrapped: storage can be missing, full or blocked.

const KEY_PROFILE = 'evqs.profile.v1';
const KEY_MESSAGES = 'evqs.messages.v1';
const KEY_RESULTS = 'evqs.results.v1';
export const STORAGE_KEYS = [KEY_PROFILE, KEY_MESSAGES, KEY_RESULTS];

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
