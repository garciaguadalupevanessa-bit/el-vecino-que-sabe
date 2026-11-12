// Farm profile ("Mi explotación"): field definitions, validation and summary.
// Values match the backend Pydantic schema (spec §4.3). Every field is optional.

export const COMUNIDADES = [
  'Andalucía', 'Aragón', 'Asturias', 'Illes Balears', 'Canarias', 'Cantabria',
  'Castilla-La Mancha', 'Castilla y León', 'Cataluña', 'Comunitat Valenciana',
  'Extremadura', 'Galicia', 'Comunidad de Madrid', 'Región de Murcia', 'Navarra',
  'País Vasco', 'La Rioja', 'Ceuta', 'Melilla',
];

export const TIPO_GANADO = [
  { value: 'ovino', label: 'Ovino (ovejas)' },
  { value: 'caprino', label: 'Caprino (cabras)' },
  { value: 'bovino', label: 'Bovino (vacas)' },
  { value: 'porcino', label: 'Porcino (cerdos)' },
  { value: 'equino', label: 'Equino (caballos)' },
  { value: 'avicola', label: 'Avícola (aves)' },
  { value: 'apicola', label: 'Apícola (abejas)' },
  { value: 'otro', label: 'Otro' },
];

export const SISTEMA = [
  { value: 'extensivo', label: 'Extensivo' },
  { value: 'intensivo', label: 'Intensivo' },
  { value: 'ecologico', label: 'Ecológico' },
  { value: 'mixto', label: 'Mixto' },
];

export const FORMA_JURIDICA = [
  { value: 'persona_fisica', label: 'Persona física' },
  { value: 'sociedad_limitada', label: 'Sociedad limitada' },
  { value: 'sociedad_anonima', label: 'Sociedad anónima' },
  { value: 'cooperativa', label: 'Cooperativa' },
  { value: 'comunidad_bienes', label: 'Comunidad de bienes' },
  { value: 'otra', label: 'Otra' },
];

export const OBJETIVO = [
  { value: 'renta', label: 'Apoyo a la renta' },
  { value: 'incorporacion', label: 'Incorporarme (joven o nuevo)' },
  { value: 'modernizacion', label: 'Modernizar la explotación' },
  { value: 'seguro', label: 'Seguro agrario' },
  { value: 'sanidad', label: 'Sanidad animal' },
  { value: 'ecologico', label: 'Pasar a ecológico' },
  { value: 'otro', label: 'Otro' },
];

const INT_RANGES = {
  num_cabezas: [0, 1_000_000],
  edad_titular: [16, 110],
  anos_actividad: [0, 80],
};

const BOOL_FIELDS = ['inscrita_rega', 'agricultor_activo'];
const TEXT_FIELDS = ['comunidad', 'provincia'];
const ENUMS = {
  sistema: SISTEMA,
  forma_juridica: FORMA_JURIDICA,
  objetivo: OBJETIVO,
};

const fmt = (n) => n.toLocaleString('es-ES');

function isBlank(v) {
  return v === undefined || v === null || (typeof v === 'string' && v.trim() === '');
}

/**
 * Validates a raw profile (form strings, booleans, arrays) and returns
 * `{ profile, errors }`. `profile` only holds valid, non-empty fields with the
 * types the backend expects; `errors` maps field -> message in Spanish.
 */
export function validateProfile(raw = {}) {
  const profile = {};
  const errors = {};

  for (const f of TEXT_FIELDS) {
    if (isBlank(raw[f])) continue;
    const v = String(raw[f]).trim();
    if (v.length > 60) errors[f] = 'Escribe como máximo 60 caracteres.';
    else profile[f] = v;
  }

  if (!isBlank(raw.tipo_ganado)) {
    const list = Array.isArray(raw.tipo_ganado) ? raw.tipo_ganado : [raw.tipo_ganado];
    const allowed = new Set(TIPO_GANADO.map((o) => o.value));
    const clean = [...new Set(list.filter((v) => allowed.has(v)))];
    if (clean.length) profile.tipo_ganado = clean;
  }

  for (const [f, [min, max]] of Object.entries(INT_RANGES)) {
    if (isBlank(raw[f])) continue;
    const n = Number(String(raw[f]).replace(/\./g, '').replace(',', '.'));
    if (!Number.isInteger(n) || n < min || n > max) {
      errors[f] = `Escribe un número entero entre ${fmt(min)} y ${fmt(max)}.`;
    } else profile[f] = n;
  }

  if (!isBlank(raw.hectareas_pasto)) {
    const n = Number(String(raw.hectareas_pasto).replace(',', '.'));
    if (!Number.isFinite(n) || n < 0) errors.hectareas_pasto = 'Escribe un número igual o mayor que 0.';
    else profile.hectareas_pasto = n;
  }

  for (const [f, options] of Object.entries(ENUMS)) {
    if (isBlank(raw[f])) continue;
    if (options.some((o) => o.value === raw[f])) profile[f] = raw[f];
    else errors[f] = 'Elige una de las opciones.';
  }

  // Booleans: missing means "no lo sé" and is never sent as false.
  for (const f of BOOL_FIELDS) {
    const v = raw[f];
    if (v === true || v === 'true' || v === 'si') profile[f] = true;
    else if (v === false || v === 'false' || v === 'no') profile[f] = false;
  }

  return { profile, errors };
}

export function labelFor(options, value) {
  return options.find((o) => o.value === value)?.label ?? value;
}

/** Short label for the sticky strip: "Aragón · Ovino · unas 300 cabezas". */
export function profileSummary(profile = {}) {
  const parts = [];
  if (profile.comunidad) parts.push(profile.provincia ? `${profile.comunidad} (${profile.provincia})` : profile.comunidad);
  if (profile.tipo_ganado?.length) {
    parts.push(profile.tipo_ganado.map((v) => labelFor(TIPO_GANADO, v).split(' ')[0]).join(', '));
  }
  if (Number.isInteger(profile.num_cabezas)) parts.push(`unas ${fmt(profile.num_cabezas)} cabezas`);

  const missing = [];
  if (!profile.comunidad) missing.push('ubicación');
  if (!profile.tipo_ganado?.length) missing.push('actividad');
  if (!Number.isInteger(profile.num_cabezas)) missing.push('tamaño');

  if (!parts.length) return 'Sin datos todavía';
  if (missing.length && missing.length < 3) return `${parts.join(' · ')} · falta ${joinEs(missing)}`;
  return parts.join(' · ');
}

/** "a, b y c" */
export function joinEs(list) {
  if (list.length <= 1) return list.join('');
  return `${list.slice(0, -1).join(', ')} y ${list[list.length - 1]}`;
}

/** How many of the three starter fields (ubicación, actividad, tamaño) are known. */
export function starterProgress(profile = {}) {
  return [profile.comunidad, profile.tipo_ganado?.length, Number.isInteger(profile.num_cabezas)].filter(Boolean).length;
}

export function boolLabel(v) {
  if (v === true) return 'Sí';
  if (v === false) return 'No';
  return 'No lo sé';
}

/** Converts a stored profile back into form-friendly strings. */
export function profileToForm(profile = {}) {
  const form = {};
  for (const [k, v] of Object.entries(profile)) {
    if (typeof v === 'number') form[k] = String(v);
    else if (typeof v === 'boolean') form[k] = v ? 'true' : 'false';
    else form[k] = v;
  }
  return form;
}
