// Only http(s) URLs are linked; any other scheme (javascript:, data:...) is dropped.
export function safeUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}
