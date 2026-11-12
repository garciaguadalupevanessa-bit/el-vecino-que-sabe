const BASE = "";

export class ReviewApiError extends Error {}

async function request(path, token, options = {}) {
  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new ReviewApiError("No se pudo conectar con el servicio de revisión.");
  }
  let data = {};
  try {
    data = await response.json();
  } catch {
    // The response may be empty when the server is unavailable.
  }
  if (!response.ok) {
    throw new ReviewApiError(data?.detail || `Error de revisión (${response.status}).`);
  }
  return data;
}

export function fetchReviewQueue(token, status = "", offset = 0, filters = {}) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (offset) params.set("offset", String(offset));
  if (filters.runId) params.set("run_id", String(filters.runId));
  if (filters.regionId) params.set("region_id", String(filters.regionId));
  if (filters.query?.trim()) params.set("q", filters.query.trim());
  const encoded = params.toString();
  const query = encoded ? `?${encoded}` : "";
  return request(`/api/admin/bdns/review${query}`, token);
}

export function fetchReviewFilterOptions(token) {
  return request("/api/admin/bdns/review/filters", token);
}

export function fetchReviewCoverage(token, runLimit = 20) {
  return request(`/api/admin/bdns/coverage?run_limit=${runLimit}`, token);
}

export function saveReviewDecision(token, bdnsCode, payload) {
  return request(`/api/admin/bdns/review/${encodeURIComponent(bdnsCode)}`, token, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function requestAIReview(token, bdnsCode) {
  return request(`/api/admin/bdns/ai-review/${encodeURIComponent(bdnsCode)}`, token, {
    method: "POST",
  });
}

export function processAIReviewQueue(token, filters = {}, limit = 10) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (filters.runId) params.set("run_id", String(filters.runId));
  if (filters.regionId) params.set("region_id", String(filters.regionId));
  if (filters.query?.trim()) params.set("q", filters.query.trim());
  return request(`/api/admin/bdns/ai-review?${params}`, token, { method: "POST" });
}

export function finalizeWithAI(token, bdnsCode) {
  return request(`/api/admin/bdns/finalize/${encodeURIComponent(bdnsCode)}`, token, { method: "POST" });
}

export function saveReviewClassification(token, bdnsCode, payload) {
  return request(`/api/admin/bdns/classification/${encodeURIComponent(bdnsCode)}`, token, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchExtractionReviewQueue(token, status = "open", offset = 0) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (offset) params.set("offset", String(offset));
  return request(`/api/admin/bdns/extraction-review?${params}`, token);
}

export function processSimpleExtractionTasks(token, limit = 50) {
  return request(`/api/admin/bdns/extraction-review/ai-process?limit=${limit}`, token, { method: "POST" });
}

export function saveExtractionReviewDecision(token, taskId, payload) {
  return request(`/api/admin/bdns/extraction-review/${taskId}`, token, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function downloadExtractionDocument(token, bdnsCode, documentId) {
  let response;
  try {
    response = await fetch(
      `${BASE}/api/admin/bdns/calls/${encodeURIComponent(bdnsCode)}/documents/${encodeURIComponent(documentId)}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
  } catch {
    throw new ReviewApiError("No se pudo conectar con el servicio de revisión.");
  }
  if (!response.ok) {
    let detail = `No se pudo descargar el documento (${response.status}).`;
    try { detail = (await response.json()).detail || detail; } catch { /* Keep the fallback message. */ }
    throw new ReviewApiError(detail);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = `bdns-${bdnsCode}-${documentId}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
