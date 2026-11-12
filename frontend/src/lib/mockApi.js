// Demo-only fake backend (`npm run dev:mock`). Same raw shape as POST /api/chat so the
// real normalizer runs. All aids are illustrative examples, flagged es_ejemplo.

import { normalizeChatResponse, normalizeAid } from './aids.js';
import { ApiError } from './api.js';
import { extractNumber } from './voice.js';

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

function extract(messages, profile) {
  const p = { ...profile };
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

function evaluate(def, p) {
  const requisitos = def.reqs.map((r) => {
    const v = r.test(p);
    return { descripcion: r.descripcion, campo: r.campo, estado: v === null ? 'por_confirmar' : v ? 'cumple' : 'no_cumple' };
  });
  const resultado = requisitos.some((r) => r.estado === 'no_cumple') ? 'no_elegible'
    : requisitos.some((r) => r.estado === 'por_confirmar') ? 'condicional' : 'elegible';
  const { reqs, ...rest } = def;
  return { ...rest, resultado, requisitos, datos_faltantes: requisitos.filter((r) => r.estado === 'por_confirmar').map((r) => r.campo) };
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
    return normalizeChatResponse({ answer: `Con dos datos más puedo buscar ayudas que encajen contigo.\n\n${q.map((x, i) => `${i + 1}. ${x}`).join('\n')}\n\nPor qué te lo pregunto: las ayudas cambian según la actividad y la comunidad.`, aids: [], sources: [], trace: [] });
  }

  const evaluated = Object.values(AIDS).map((d) => evaluate(d, p));
  const trace = [
    { tool: 'search_aids', arguments: { comunidad: p.comunidad, tipo_ganado: p.tipo_ganado, solo_abiertas: true }, ok: true },
    { tool: 'check_eligibility', arguments: { aid_id: 'ej-ovino-asociada', profile: p }, ok: true },
    { tool: 'check_eligibility', arguments: { aid_id: 'ej-jovenes', profile: p }, ok: true },
  ];
  const sources = [{ url: 'https://www.fega.gob.es/es', nombre: 'FEGA · PEPAC 2023-2027', fecha_verificacion: '2026-11-10' }];

  if (/solicit|pedirla|c[oó]mo la pido/.test(last)) {
    trace.push({ tool: 'get_application_guide', arguments: { aid_id: 'ej-ovino-asociada' }, ok: true });
    return normalizeChatResponse({
      answer: 'Para la **ayuda de ejemplo A** los pasos son:\n\n1. Reúne la documentación de tu explotación (REGA y censo).\n2. Presenta la solicitud única de la PAC en la sede electrónica de tu comunidad o en una entidad colaboradora.\n3. Marca la línea de ayuda asociada al ovino.\n\nEl plazo no está verificado: confírmalo en https://www.fega.gob.es/es o en tu oficina comarcal antes de presentar nada.',
      aids: evaluated, sources, trace,
    });
  }
  if (/alternativ/.test(last)) {
    trace.push({ tool: 'find_alternatives', arguments: { aid_id: 'ej-modernizacion', max_resultados: 3 }, ok: true });
    return normalizeChatResponse({ answer: 'La **ayuda de ejemplo C** pide un mínimo de 500 cabezas y, según tus datos, no se cumple. Como alternativa, la ayuda de ejemplo A encaja con tu actividad y ubicación.', aids: evaluated, sources, trace });
  }

  const best = evaluated[0];
  const ask = p.agricultor_activo == null ? '\n\n¿Estás dado de alta como agricultor activo?\n\nPor qué te lo pregunto: es un requisito para cobrar los pagos directos de la PAC.' : '';
  return normalizeChatResponse({
    answer: `Con lo que me has contado he encontrado ${evaluated.length} ayudas de ejemplo. La que mejor encaja es la **${best.nombre}**: ${best.resultado === 'elegible' ? 'cumples lo que sé hasta ahora.' : 'cumples parte de los requisitos y faltan datos por confirmar.'}${ask}`,
    aids: evaluated, sources, trace,
  });
}

export async function mockGetAid(id) {
  await wait(300);
  const def = AIDS[id];
  if (!def) throw new ApiError('not_found', 'No hemos encontrado esa ayuda.', 404);
  const { reqs, ...rest } = def;
  return normalizeAid({ ...rest, requisitos: reqs.map((r) => ({ descripcion: r.descripcion, campo: r.campo })) });
}

export async function mockGetHealth() {
  return { status: 'ok', aids_loaded: Object.keys(AIDS).length, data_source: 'demo', llm_configured: false };
}

export async function mockTranscribe() {
  await wait(1200);
  return 'Tengo unas trescientas ovejas en Teruel y quería saber qué ayudas hay para mí.';
}
