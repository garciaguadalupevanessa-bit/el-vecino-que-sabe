// Demo-only fake backend (`npm run dev:mock`). It receives and returns exactly the real
// backend shapes (FarmProfile in, ChatResponse out, see backend/app/models/api.py), so the
// real mapping and normalizer run. All aids are illustrative examples, flagged es_ejemplo.

import { normalizeChatResponse, normalizeAid } from './aids.js';
import { ApiError } from './api.js';
import { extractNumber } from './voice.js';
import { fromBackendProfile } from './backendContract.js';

const AIDS = {
  'ej-ovino-asociada': {
    id: 'ej-ovino-asociada', es_ejemplo: true,
    nombre: 'Ayuda de ejemplo A · pago asociado al ovino',
    organismo: 'FEGA y la consejería de tu comunidad', ambito: 'estatal', tipo_ayuda: 'pac_asociada',
    descripcion_corta: 'Pago anual por cabeza para explotaciones de ovino que se pide en la solicitud única de la PAC.',
    fiabilidad: 'verificada', url_fuente: 'https://www.fega.gob.es/es', fecha_verificacion: '2026-11-10', verificado_por: 'Equipo',
    plazo: null, importe: null, abierta: true,
    como_solicitar: 'Reúne la documentación de tu explotación.\nPresenta la solicitud única de la PAC en la sede electrónica de tu comunidad o en una entidad colaboradora.\nMarca la línea de ayuda asociada al ovino.',
    documentacion: ['Datos del REGA de la explotación', 'Declaración del censo de animales'],
    alternativas: ['ej-jovenes'],
    reqs: [
      { descripcion: 'Actividad ganadera (ovino)', campo: 'tipo_ganado', test: (p) => (p.tipo_ganado ? p.tipo_ganado.includes('ovino') : null) },
      { descripcion: 'Ubicación en España', campo: 'comunidad', test: (p) => (p.comunidad ? true : null) },
      { descripcion: 'Mínimo de 30 animales', campo: 'num_cabezas', test: (p) => (p.num_cabezas == null ? null : p.num_cabezas >= 30) },
      { descripcion: 'Inscrita en el REGA', campo: 'inscrita_rega', test: (p) => p.inscrita_rega ?? null },
      { descripcion: 'Agricultor activo', campo: 'agricultor_activo', test: (p) => p.agricultor_activo ?? null },
    ],
  },
  'ej-jovenes': {
    id: 'ej-jovenes', es_ejemplo: true,
    nombre: 'Ayuda de ejemplo B · jóvenes agricultores',
    organismo: 'Consejería de Agricultura', ambito: 'Aragón', tipo_ayuda: 'incorporacion',
    descripcion_corta: 'Ayuda para la primera instalación de personas jóvenes como titulares de una explotación.',
    fiabilidad: 'extraida', url_fuente: 'https://www.mapa.gob.es/es/', fecha_verificacion: '2026-11-05',
    plazo: null, importe: null, abierta: null, como_solicitar: null, documentacion: [], alternativas: [],
    reqs: [
      { descripcion: 'Edad del titular hasta 40 años', campo: 'edad_titular', test: (p) => (p.edad_titular == null ? null : p.edad_titular <= 40) },
      { descripcion: 'Hasta 5 años de actividad', campo: 'anos_actividad', test: (p) => (p.anos_actividad == null ? null : p.anos_actividad <= 5) },
      { descripcion: 'Agricultor activo', campo: 'agricultor_activo', test: (p) => p.agricultor_activo ?? null },
    ],
  },
  'ej-modernizacion': {
    id: 'ej-modernizacion', es_ejemplo: true,
    nombre: 'Ayuda de ejemplo C · modernización de explotaciones',
    organismo: 'Consejería de Agricultura', ambito: 'Aragón', tipo_ayuda: 'modernizacion',
    descripcion_corta: 'Inversiones para modernizar instalaciones ganaderas.',
    fiabilidad: 'solo_metadatos', url_fuente: 'https://www.mapa.gob.es/es/', fecha_verificacion: null,
    alternativas: ['ej-ovino-asociada', 'ej-jovenes'],
    que_cambiaria: 'Superar un mínimo de 500 cabezas.',
    reqs: [
      { descripcion: 'Mínimo de 500 cabezas', campo: 'num_cabezas', test: (p) => (p.num_cabezas == null ? null : p.num_cabezas >= 500) },
    ],
  },
};

function extract(messages, backendProfile) {
  const p = fromBackendProfile(backendProfile);
  const text = messages.filter((m) => m.role === 'user').map((m) => m.content.toLowerCase()).join(' ');
  if (!p.tipo_ganado && /ovej|ovino/.test(text)) p.tipo_ganado = ['ovino'];
  if (!p.tipo_ganado && /cabra|caprino/.test(text)) p.tipo_ganado = ['caprino'];
  if (!p.tipo_ganado && /vaca|bovino/.test(text)) p.tipo_ganado = ['bovino'];
  if (!p.comunidad && /teruel|arag[oó]n|huesca|zaragoza/.test(text)) p.comunidad = 'Aragón';
  const n = /((?:\S+\s+){0,3})(ovejas|cabezas|cabras|vacas|animales)/.exec(text);
  if (p.num_cabezas == null && n && extractNumber(n[1])) p.num_cabezas = extractNumber(n[1]);
  if (p.agricultor_activo == null && /soy agricultor activo|s[ií], lo soy/.test(text)) p.agricultor_activo = true;
  return p;
}

const RELIABILITY_EN = { verificada: 'verified', extraida: 'extracted', solo_metadatos: 'metadata_only' };
const FIELD_EN = { tipo_ganado: 'livestock_type', comunidad: 'region', num_cabezas: 'head_count', inscrita_rega: 'rega_registered', agricultor_activo: 'active_farmer', edad_titular: 'holder_age', anos_actividad: 'years_active' };

/** Aid model (GET /api/aids/{id}) for an example definition. */
function asBackendAid(def) {
  return {
    id: def.id, es_ejemplo: true, name: def.nombre, agency: def.organismo, scope: def.ambito === 'estatal' ? 'national' : def.ambito,
    aid_type: def.tipo_ayuda, short_description: def.descripcion_corta, reliability: RELIABILITY_EN[def.fiabilidad],
    source_url: def.url_fuente, verified_on: def.fecha_verificacion, verified_by: def.verificado_por ?? null,
    deadline: def.plazo ?? null, amount: def.importe ?? null, open: def.abierta ?? null,
    how_to_apply: def.como_solicitar ? def.como_solicitar.split('\n') : [], documents: def.documentacion ?? [],
    alternatives: def.alternativas ?? [], que_cambiaria: def.que_cambiaria,
    requirements: def.reqs.map((r) => ({ description: r.descripcion, field: FIELD_EN[r.campo] })),
  };
}

/** EvaluatedAid (POST /api/chat) with the requirements engine's output shape. */
function evaluate(def, p) {
  const requirements = def.reqs.map((r) => {
    const v = r.test(p);
    const status = v === null ? 'unknown' : v ? 'met' : 'not_met';
    return {
      description: r.descripcion, status, missing_field: v === null ? FIELD_EN[r.campo] : null,
      reason: `${r.campo} (debug)`,
      explanation_es: v === null ? 'Falta indicar este dato en tu explotación.' : v ? 'El dato cumple.' : 'El dato no cumple.',
    };
  });
  const statuses = new Set(requirements.map((r) => r.status));
  const overall_result = statuses.has('not_met') ? 'not_met' : statuses.has('unknown') ? 'unknown' : 'met';
  const { requirements: _defs, ...aid } = asBackendAid(def);
  return { ...aid, overall_result, requirements };
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

export async function mockSendChat(payload) {
  await wait(1800);
  const msgs = payload.messages ?? [];
  const last = (msgs.at(-1)?.content ?? '').toLowerCase();
  if (last.includes('simular error')) throw new ApiError('ai', 'Ahora mismo no podemos completar la búsqueda. Tu pregunta sigue aquí. Puedes volver a intentarlo en unos momentos.', 502);
  const p = extract(msgs, payload.profile ?? {});

  if (!p.comunidad || !p.tipo_ganado) {
    const q = [];
    if (!p.tipo_ganado) q.push('¿Qué tipo de ganado o cultivo tienes?');
    if (!p.comunidad) q.push('¿En qué comunidad autónoma está tu explotación?');
    return normalizeChatResponse({ coverage_notes: [], answer: `Con dos datos más puedo buscar ayudas que encajen contigo.\n\n${q.map((x, i) => `${i + 1}. ${x}`).join('\n')}\n\nPor qué te lo pregunto: las ayudas cambian según la actividad y la comunidad.`, aids: [], sources: [], trace: [] });
  }

  const evaluated = Object.values(AIDS).map((d) => evaluate(d, p));
  const trace = [
    { tool: 'search_aids', input: { region: p.comunidad, livestock_type: payload.profile?.livestock_type ?? ['sheep'], only_open: true }, ok: true },
    { tool: 'check_eligibility', input: { aid_id: 'ej-ovino-asociada', profile: {} }, ok: true },
    { tool: 'check_eligibility', input: { aid_id: 'ej-jovenes', profile: {} }, ok: true },
  ];
  const sources = [{ url: 'https://www.fega.gob.es/es', name: 'FEGA · PEPAC 2023-2027', verified_on: '2026-11-10', reliability: 'verified' }];

  if (/solicit|pedirla|c[oó]mo la pido/.test(last)) {
    trace.push({ tool: 'get_application_guide', input: { aid_id: 'ej-ovino-asociada' }, ok: true });
    return normalizeChatResponse({
      answer: 'Para la **ayuda de ejemplo A** los pasos son:\n\n1. Reúne la documentación de tu explotación (REGA y censo).\n2. Presenta la solicitud única de la PAC en la sede electrónica de tu comunidad o en una entidad colaboradora.\n3. Marca la línea de ayuda asociada al ovino.\n\nEl plazo no está verificado: confírmalo en https://www.fega.gob.es/es o en tu oficina comarcal antes de presentar nada.',
      aids: evaluated, sources, trace,
    });
  }
  if (/alternativ/.test(last)) {
    trace.push({ tool: 'find_alternatives', input: { aid_id: 'ej-modernizacion', max_results: 3 }, ok: true });
    return normalizeChatResponse({ answer: 'La **ayuda de ejemplo C** pide un mínimo de 500 cabezas y, según tus datos, no se cumple. Como alternativa, la ayuda de ejemplo A encaja con tu actividad y ubicación.', aids: evaluated, sources, trace });
  }

  const best = evaluated[0];
  const ask = p.agricultor_activo == null ? '\n\n¿Estás dado de alta como agricultor activo?\n\nPor qué te lo pregunto: es un requisito para cobrar los pagos directos de la PAC.' : '';
  return normalizeChatResponse({
    answer: `Con lo que me has contado he encontrado ${evaluated.length} ayudas de ejemplo. La que mejor encaja es la **${best.name}**: ${best.overall_result === 'met' ? 'cumples lo que sé hasta ahora.' : 'cumples parte de los requisitos y faltan datos por confirmar.'}${ask}`,
    aids: evaluated, sources, trace,
  });
}

export async function mockGetAid(id) {
  await wait(300);
  const def = AIDS[id];
  if (!def) throw new ApiError('not_found', 'No hemos encontrado esa ayuda.', 404);
  return normalizeAid(asBackendAid(def));
}

export async function mockGetHealth() {
  return { status: 'ok', aids_loaded: Object.keys(AIDS).length, data_source: 'demo', llm_configured: false };
}

export async function mockTranscribe() {
  await wait(1200);
  return 'Tengo unas trescientas ovejas en Teruel y quería saber qué ayudas hay para mí.';
}
