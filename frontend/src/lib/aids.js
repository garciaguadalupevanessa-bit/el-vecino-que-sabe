// Normalizes the /api/chat and /api/aids/{id} payloads into one stable shape for the UI.
// The backend contract (spec §4.3–4.4) uses Spanish field names; English aliases are
// accepted too, so a small naming drift in the backend does not break the screen.

import { safeHttpUrl, displayHost } from './urls.js';

export const ELIGIBILITY = {
  elegible: { label: 'Encaje favorable', tone: 'success', icon: '✓', rank: 0 },
  condicional: { label: 'Pendiente de comprobar', tone: 'warning', icon: '!', rank: 1 },
  no_elegible: { label: 'No cumple los requisitos conocidos', tone: 'error', icon: '✕', rank: 2 },
  desconocido: { label: 'Sin evaluar todavía', tone: 'info', icon: '?', rank: 3 },
};

export const RELIABILITY = {
  verificada: { label: 'Verificada', help: 'Información contrastada con la fuente oficial.' },
  extraida: { label: 'Extraída', help: 'Extraída de documentación oficial; algunos detalles pueden necesitar revisión.' },
  solo_metadatos: { label: 'Solo metadatos', help: 'Solo disponemos de información básica. Consulta la fuente oficial antes de decidir.' },
};

export const REQUIREMENT = {
  cumple: { label: 'coincide', tone: 'success', icon: '✓' },
  no_cumple: { label: 'no se cumple', tone: 'error', icon: '✕' },
  por_confirmar: { label: 'pendiente de confirmar', tone: 'warning', icon: '!' },
};

export const NO_VERIFIED = 'Sin dato verificado · consulta la fuente oficial';

const first = (obj, keys) => {
  for (const k of keys) {
    const v = k.split('.').reduce((o, p) => (o == null ? undefined : o[p]), obj);
    if (v !== undefined && v !== null && v !== '') return v;
  }
  return undefined;
};

const norm = (v) => String(v ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[\s-]+/g, '_');

export function normalizeEligibility(value) {
  const v = norm(value);
  if (['elegible', 'eligible', 'cumple', 'favorable'].includes(v)) return 'elegible';
  if (['condicional', 'conditional', 'por_confirmar', 'pendiente', 'unknown'].includes(v)) return 'condicional';
  if (['no_elegible', 'not_eligible', 'ineligible', 'no_cumple'].includes(v)) return 'no_elegible';
  return 'desconocido';
}

export function normalizeRequirementStatus(value) {
  if (value === true) return 'cumple';
  if (value === false) return 'no_cumple';
  const v = norm(value);
  if (['cumple', 'met', 'ok', 'pass', 'true', 'si', 'coincide'].includes(v)) return 'cumple';
  if (['no_cumple', 'not_met', 'fail', 'false', 'no'].includes(v)) return 'no_cumple';
  return 'por_confirmar';
}

export function normalizeReliability(value) {
  const v = norm(value);
  if (v.startsWith('verific')) return 'verificada';
  if (v.startsWith('extra')) return 'extraida';
  return 'solo_metadatos';
}

function toList(v) {
  if (v == null || v === '') return [];
  if (Array.isArray(v)) return v.map((x) => (typeof x === 'string' ? x : x?.descripcion ?? x?.paso ?? x?.texto ?? x?.nombre ?? JSON.stringify(x))).filter(Boolean);
  if (typeof v === 'string') return v.split(/\n+|(?<=\.)\s+(?=\d+[.)]\s)/).map((s) => s.replace(/^\s*(\d+[.)]|[-•*])\s*/, '').trim()).filter(Boolean);
  return [];
}

function toText(v) {
  if (v == null || v === '') return null;
  if (typeof v === 'number') return v.toLocaleString('es-ES');
  if (typeof v === 'string') return v;
  if (typeof v === 'object') return v.texto ?? v.descripcion ?? v.valor ?? null;
  return String(v);
}

function normalizeRequirement(r) {
  if (typeof r === 'string') return { descripcion: r, campo: null, estado: 'por_confirmar', detalle: null };
  return {
    descripcion: first(r, ['descripcion', 'description', 'texto', 'nombre', 'requisito', 'campo', 'field']) ?? 'Requisito',
    campo: first(r, ['campo', 'field']) ?? null,
    estado: normalizeRequirementStatus(first(r, ['estado', 'status', 'resultado', 'result', 'cumple', 'met'])),
    detalle: first(r, ['detalle', 'motivo', 'reason', 'explicacion', 'mensaje', 'message']) ?? null,
  };
}

function boolOrNull(v) {
  if (v === true || v === false) return v;
  const n = norm(v);
  if (['true', 'si', 'abierta'].includes(n)) return true;
  if (['false', 'no', 'cerrada'].includes(n)) return false;
  return null;
}

/** One aid in a single shape, whatever endpoint it came from. */
export function normalizeAid(raw) {
  if (!raw || typeof raw !== 'object') return null;
  const ev = first(raw, ['evaluacion', 'eligibility', 'elegibilidad_detalle', 'check']) ;
  const evObj = ev && typeof ev === 'object' ? ev : {};

  const reqSource = first(evObj, ['requisitos', 'requirements', 'checks', 'detalle']) ??
    first(raw, ['requisitos_evaluados', 'requirements_evaluated', 'requisitos']);
  const requisitos = Array.isArray(reqSource)
    // Unevaluated definitions (no status at all) are still listed, as "por confirmar".
    ? reqSource.filter((r) => r && (typeof r === 'string' || typeof r === 'object') && !r.bloque && !r.block).map(normalizeRequirement)
    : [];

  const resultadoRaw = first(evObj, ['resultado', 'result', 'overall', 'global', 'estado']) ??
    first(raw, ['resultado', 'resultado_global', 'elegibilidad', 'eligibility', 'estado', 'status']);
  let resultado = normalizeEligibility(typeof resultadoRaw === 'string' ? resultadoRaw : undefined);
  // If the backend sent requirement states but no global result, derive it like the engine does.
  if (resultado === 'desconocido' && requisitos.length && Array.isArray(reqSource) && reqSource.some((r) => r && typeof r === 'object' && (r.estado ?? r.status) !== undefined)) {
    resultado = requisitos.some((r) => r.estado === 'no_cumple') ? 'no_elegible'
      : requisitos.some((r) => r.estado === 'por_confirmar') ? 'condicional' : 'elegible';
  }

  const faltan = first(evObj, ['datos_faltantes', 'faltan', 'missing', 'missing_fields']) ??
    first(raw, ['datos_faltantes', 'missing_fields', 'faltan']);

  const url = safeHttpUrl(first(raw, ['url_fuente', 'source_url', 'fuente.url', 'url']));

  return {
    id: String(first(raw, ['id', 'aid_id', 'codigo']) ?? ''),
    nombre: first(raw, ['nombre', 'name', 'titulo', 'title']) ?? 'Ayuda sin nombre',
    organismo: first(raw, ['organismo', 'body', 'organism']) ?? null,
    ambito: first(raw, ['ambito', 'scope']) ?? null,
    tipo_ayuda: first(raw, ['tipo_ayuda', 'type']) ?? null,
    descripcion: first(raw, ['descripcion_corta', 'descripcion', 'description', 'resumen']) ?? null,
    fiabilidad: normalizeReliability(first(raw, ['fiabilidad', 'reliability'])),
    url_fuente: url,
    host_fuente: displayHost(url),
    fecha_verificacion: first(raw, ['fecha_verificacion', 'verified_at', 'fuente.fecha_verificacion']) ?? null,
    verificado_por: first(raw, ['verificado_por', 'verified_by']) ?? null,
    importe: toText(first(raw, ['importe', 'amount'])),
    plazo: toText(first(raw, ['plazo', 'deadline'])),
    abierta: boolOrNull(first(raw, ['abierta', 'open'])),
    pasos: toList(first(raw, ['guia.pasos', 'pasos', 'steps', 'como_solicitar', 'how_to_apply'])),
    como_solicitar: typeof raw.como_solicitar === 'string' ? raw.como_solicitar : null,
    documentacion: toList(first(raw, ['guia.documentacion', 'documentacion', 'documents'])),
    alternativas: (first(raw, ['alternativas', 'alternatives']) ?? []).map((a) => (typeof a === 'object' ? String(a.id ?? a.aid_id ?? '') : String(a))).filter(Boolean),
    notas: first(raw, ['notas', 'notes']) ?? null,
    resultado,
    requisitos,
    datos_faltantes: Array.isArray(faltan) ? faltan.map(String) : [],
    cambio_sugerido: first(raw, ['que_cambiaria', 'cambio', 'what_would_change', 'motivo_alternativa']) ?? null,
    es_ejemplo: Boolean(raw.es_ejemplo),
  };
}

/** Merges two normalized versions of the same aid (chat result + detail fetch). */
export function mergeAid(base, extra) {
  if (!base) return extra;
  if (!extra) return base;
  const out = { ...base };
  for (const [k, v] of Object.entries(extra)) {
    const empty = v == null || v === '' || (Array.isArray(v) && v.length === 0) || (k === 'resultado' && v === 'desconocido');
    if (!empty && (out[k] == null || out[k] === '' || (Array.isArray(out[k]) && out[k].length === 0) || (k === 'resultado' && out[k] === 'desconocido'))) out[k] = v;
  }
  return out;
}

export function sortAids(aids) {
  return [...aids].sort((a, b) => ELIGIBILITY[a.resultado].rank - ELIGIBILITY[b.resultado].rank);
}

export function requirementCounts(aid) {
  const c = { total: aid.requisitos.length, cumple: 0, no_cumple: 0, por_confirmar: 0 };
  for (const r of aid.requisitos) c[r.estado] += 1;
  return c;
}

/** One-line reason for compact cards. */
export function shortReason(aid) {
  const c = requirementCounts(aid);
  if (aid.resultado === 'no_elegible') {
    const failed = aid.requisitos.find((r) => r.estado === 'no_cumple');
    return failed ? `Pide «${failed.descripcion}» y, según tus datos, no se cumple.` : 'Un requisito no se cumple.';
  }
  const missing = aid.datos_faltantes.length || c.por_confirmar;
  if (missing) return missing === 1 ? 'Falta 1 dato por confirmar.' : `Faltan ${missing} datos por confirmar.`;
  if (aid.resultado === 'elegible') return 'Cumples lo que sabemos hasta ahora.';
  return aid.descripcion ?? 'Abre el detalle para ver los requisitos.';
}

function normalizeTraceEntry(t) {
  if (!t || typeof t !== 'object') return null;
  const okRaw = first(t, ['ok', 'success', 'status', 'estado']);
  const ok = okRaw === true || ['ok', 'success', 'exito', 'completed', 'true'].includes(norm(okRaw));
  const args = first(t, ['arguments', 'args', 'params', 'parameters', 'parametros', 'input']) ?? {};
  let parsed = args;
  if (typeof args === 'string') {
    try { parsed = JSON.parse(args); } catch { parsed = { valor: args }; }
  }
  return {
    tool: String(first(t, ['tool', 'name', 'herramienta', 'function']) ?? 'herramienta'),
    args: parsed && typeof parsed === 'object' ? parsed : {},
    ok,
    error: first(t, ['error', 'mensaje_error', 'detail']) ?? null,
  };
}

export function formatArgs(args) {
  return Object.entries(args)
    .filter(([k]) => k !== 'profile' && k !== 'perfil')
    .map(([k, v]) => `${k}=${Array.isArray(v) ? `[${v.join(', ')}]` : typeof v === 'object' && v !== null ? '{…}' : v}`)
    .concat('profile' in args || 'perfil' in args ? ['perfil'] : [])
    .join(', ');
}

function normalizeSource(s) {
  if (typeof s === 'string') {
    const url = safeHttpUrl(s);
    return url ? { url, nombre: displayHost(url), fecha_verificacion: null } : null;
  }
  if (!s || typeof s !== 'object') return null;
  const url = safeHttpUrl(first(s, ['url', 'url_fuente', 'href']));
  if (!url) return null;
  return {
    url,
    nombre: first(s, ['nombre', 'name', 'titulo', 'title']) ?? displayHost(url),
    fecha_verificacion: first(s, ['fecha_verificacion', 'verified_at', 'fecha']) ?? null,
  };
}

export function normalizeChatResponse(data) {
  const d = data && typeof data === 'object' ? data : {};
  const aids = (Array.isArray(d.aids) ? d.aids : []).map(normalizeAid).filter(Boolean);
  const seen = new Set();
  const unique = aids.filter((a) => (a.id && seen.has(a.id) ? false : (seen.add(a.id), true)));
  const sources = (Array.isArray(d.sources) ? d.sources : []).map(normalizeSource).filter(Boolean);
  return {
    answer: typeof d.answer === 'string' && d.answer.trim() ? d.answer : 'No he podido redactar una respuesta. Prueba a preguntarlo de otra forma.',
    aids: sortAids(unique),
    sources,
    trace: (Array.isArray(d.trace) ? d.trace : []).map(normalizeTraceEntry).filter(Boolean),
  };
}

/** Spanish date "12 de noviembre de 2026" from ISO; leaves other strings untouched. */
export function formatDate(value) {
  if (!value) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value));
  if (!m) return String(value);
  const months = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  return `${Number(m[3])} de ${months[Number(m[2]) - 1]} de ${m[1]}`;
}
