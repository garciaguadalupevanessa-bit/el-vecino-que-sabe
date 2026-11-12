// Bridge between the UI (Spanish labels and values, kept in localStorage) and the real
// backend contract (backend/app/models/profile.py · FarmProfile, English field names).
// The backend ignores unknown fields (extra="ignore"), so a wrong name is silently lost:
// every field must go through this mapping.

const FIELD_MAP = {
  comunidad: 'region',
  provincia: 'province',
  tipo_ganado: 'livestock_type',
  num_cabezas: 'head_count',
  sistema: 'production_system',
  forma_juridica: 'legal_form',
  edad_titular: 'holder_age',
  anos_actividad: 'years_active',
  hectareas_pasto: 'pasture_hectares',
  inscrita_rega: 'rega_registered',
  agricultor_activo: 'active_farmer',
  objetivo: 'goal',
};

const VALUE_MAP = {
  tipo_ganado: { bovino: 'cattle', ovino: 'sheep', caprino: 'goat', porcino: 'pig', equino: 'equine', avicola: 'poultry', apicola: 'bees', otro: 'other' },
  sistema: { extensivo: 'extensive', intensivo: 'intensive', ecologico: 'organic', mixto: 'mixed' },
  forma_juridica: { persona_fisica: 'individual', sociedad_limitada: 'limited_company', sociedad_anonima: 'corporation', cooperativa: 'cooperative', comunidad_bienes: 'joint_property', otra: 'other' },
  objetivo: { renta: 'income', incorporacion: 'start_up', modernizacion: 'modernization', seguro: 'insurance', sanidad: 'animal_health', ecologico: 'organic', otro: 'other' },
};

const invert = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [v, k]));
const FIELD_BACK = invert(FIELD_MAP);
const VALUE_BACK = Object.fromEntries(Object.entries(VALUE_MAP).map(([k, m]) => [k, invert(m)]));

const mapValue = (field, v, maps) => {
  const m = maps[field];
  if (!m) return v;
  return Array.isArray(v) ? v.map((x) => m[x]).filter(Boolean) : m[v];
};

/** Validated UI profile -> FarmProfile JSON for POST /api/chat. */
export function toBackendProfile(profile = {}) {
  const out = {};
  for (const [es, en] of Object.entries(FIELD_MAP)) {
    const v = profile[es];
    if (v === undefined || v === null || v === '') continue;
    const mapped = mapValue(es, v, VALUE_MAP);
    if (mapped === undefined || (Array.isArray(mapped) && !mapped.length)) continue;
    out[en] = mapped;
  }
  if (out.livestock_type?.length || out.head_count != null || out.rega_registered != null) out.farm_activities = ['livestock'];
  return out;
}

/** FarmProfile JSON -> UI profile (for the mock backend and for future profile echoes). */
export function fromBackendProfile(profile = {}) {
  const out = {};
  for (const [en, es] of Object.entries(FIELD_BACK)) {
    const v = profile?.[en];
    if (v === undefined || v === null) continue;
    const mapped = mapValue(es, v, VALUE_BACK);
    if (mapped !== undefined) out[es] = mapped;
  }
  return out;
}

/** "active_farmer" -> "agricultor_activo" (for missing_fields); unknown names pass through. */
export const fromBackendField = (name) => FIELD_BACK[name] ?? name;

/** "national" -> "estatal"; anything else is the region name. */
export const scopeLabel = (scope) => (scope === 'national' ? 'estatal' : scope);
