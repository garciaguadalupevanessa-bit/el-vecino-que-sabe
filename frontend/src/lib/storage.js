// Simple localStorage persistence (no database). Always failure-tolerant.
const PREFIX = "elvecinoquesabe:";

export function save(key, value) {
  try { localStorage.setItem(PREFIX + key, JSON.stringify(value)); } catch { /* storage unavailable */ }
}

export function load(key, fallback) {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

export function remove(key) {
  try { localStorage.removeItem(PREFIX + key); } catch { /* nothing */ }
}
