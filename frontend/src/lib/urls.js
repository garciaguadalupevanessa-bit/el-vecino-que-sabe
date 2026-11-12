// Only http(s) links are ever rendered (spec §4.7).

export function safeHttpUrl(value) {
  if (typeof value !== 'string' || !value.trim()) return null;
  try {
    const url = new URL(value.trim());
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null;
  } catch {
    return null;
  }
}

/** "https://www.fega.gob.es/x" -> "fega.gob.es" */
export function displayHost(value) {
  const safe = safeHttpUrl(value);
  if (!safe) return null;
  return new URL(safe).hostname.replace(/^www\./, '');
}
