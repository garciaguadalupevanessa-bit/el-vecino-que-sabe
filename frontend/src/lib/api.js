// Backend API client. Error messages are user-facing (Spanish).
let BASE = "";
// API base URL (empty = same origin; nginx/Vite forward /api to the backend)
export function configureBase(url) {
  BASE = String(url ?? "").replace(/\/$/, "");
}

export class ApiError extends Error {}

// The backend requires the history to start and end with a user message.
export function trimHistory(messages, max = 20) {
  const h = messages.slice(-max);
  while (h.length && h[0].role !== "user") h.shift();
  return h;
}

async function errorDetail(resp) {
  try {
    const d = (await resp.json())?.detail;
    return typeof d === "string" ? d : null;
  } catch {
    return null;
  }
}

export async function sendChat(messages, profile, { timeoutMs = 90_000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let resp;
  try {
    resp = await fetch(`${BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, profile }),
      signal: ctrl.signal,
    });
  } catch (e) {
    if (e?.name === "AbortError") throw new ApiError("La consulta ha tardado demasiado. Inténtalo de nuevo.");
    throw new ApiError("No se ha podido conectar con el servidor. Comprueba tu conexión e inténtalo de nuevo.");
  } finally {
    clearTimeout(timer);
  }

  if (resp.status === 422) {
    throw new ApiError("Los datos no son válidos. Revisa el perfil y que el mensaje no supere los 4000 caracteres.");
  }
  if (!resp.ok) {
    const detail = await errorDetail(resp);
    throw new ApiError(detail ?? `El servidor ha devuelto un error inesperado (código ${resp.status}).`);
  }
  const data = await resp.json();
  if (typeof data?.answer !== "string") throw new ApiError("La respuesta del servidor no tiene el formato esperado.");
  return {
    answer: data.answer,
    aids: Array.isArray(data.aids) ? data.aids : [],
    sources: Array.isArray(data.sources) ? data.sources : [],
    trace: Array.isArray(data.trace) ? data.trace : [],
    coverage_notes: Array.isArray(data.coverage_notes) ? data.coverage_notes : [],
  };
}
