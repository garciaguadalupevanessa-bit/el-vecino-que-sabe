// Farm profile model: constants, validation and payload building. It does not touch the DOM,
// so it can be tested with Node. Labels and messages are user-facing (Spanish); keys and values are English.
export const REGIONS = [
  "Andalucía", "Aragón", "Asturias", "Illes Balears", "Canarias", "Cantabria", "Castilla y León",
  "Castilla-La Mancha", "Cataluña", "Ceuta", "Comunitat Valenciana", "Extremadura", "Galicia",
  "Comunidad de Madrid", "Melilla", "Región de Murcia", "Navarra", "País Vasco", "La Rioja",
];

export const LIVESTOCK = [
  ["cattle", "Vacuno"], ["sheep", "Ovino (ovejas)"], ["goat", "Caprino (cabras)"],
  ["pig", "Porcino (cerdos)"], ["equine", "Equino (caballos)"], ["poultry", "Avícola (aves)"],
  ["bees", "Apícola (abejas)"], ["other", "Otro"],
];
export const FARM_ACTIVITIES = [["agriculture", "Agricultura"], ["livestock", "Ganadería"]];

export const EXAMPLE = {
  region: "Aragón", province: "Teruel", municipality: "Alcañiz", livestock_type: ["sheep"], head_count: "300",
  farm_activities: ["livestock"], crop_types: "", agricultural_area_hectares: "", irrigated_hectares: "",
  production_system: "extensive", legal_form: "individual", holder_age: "29", years_active: "2",
  pasture_hectares: "", rega_registered: "", active_farmer: "", goal: "income",
};

// Same limits as the backend (app/models/profile.py)
const LIMITS = {
  head_count: { min: 0, max: 1_000_000, integer: true, label: "El número de cabezas" },
  holder_age: { min: 16, max: 110, integer: true, label: "La edad" },
  years_active: { min: 0, max: 80, integer: true, label: "Los años en activo" },
  pasture_hectares: { min: 0, max: Infinity, integer: false, label: "Las hectáreas" },
  agricultural_area_hectares: { min: 0, max: Infinity, integer: false, label: "La superficie agrícola" },
  irrigated_hectares: { min: 0, max: Infinity, integer: false, label: "La superficie de regadío" },
};

export function validateProfile(values) {
  const errors = {};
  for (const [field, lim] of Object.entries(LIMITS)) {
    const raw = String(values[field] ?? "").trim();
    if (raw === "") continue;
    const n = Number(raw.replace(",", "."));
    if (!Number.isFinite(n)) errors[field] = `${lim.label} debe ser un número.`;
    else if (lim.integer && !Number.isInteger(n)) errors[field] = `${lim.label} debe ser un número entero.`;
    else if (n < lim.min) errors[field] = `${lim.label} no puede ser menor que ${lim.min}.`;
    else if (n > lim.max) errors[field] = `${lim.label} no puede ser mayor que ${lim.max}.`;
  }
  return errors;
}

const YES_NO = { yes: true, no: false };

// Returns only the filled fields, with the types the backend expects.
export function buildProfile(v) {
  const p = {};
  const text = (k) => { const s = String(v[k] ?? "").trim(); if (s) p[k] = s; };
  const number = (k) => {
    const s = String(v[k] ?? "").trim();
    if (s !== "" && Number.isFinite(Number(s.replace(",", ".")))) p[k] = Number(s.replace(",", "."));
  };
  text("region"); text("province"); text("municipality");
  if (Array.isArray(v.farm_activities) && v.farm_activities.length) p.farm_activities = [...v.farm_activities];
  const crops = String(v.crop_types ?? "").split(",").map((x) => x.trim()).filter(Boolean);
  if (crops.length) p.crop_types = crops;
  number("agricultural_area_hectares"); number("irrigated_hectares");
  if (Array.isArray(v.livestock_type) && v.livestock_type.length) p.livestock_type = [...v.livestock_type];
  number("head_count"); text("production_system"); text("legal_form");
  number("holder_age"); number("years_active"); number("pasture_hectares");
  for (const k of ["rega_registered", "active_farmer"]) {
    if (v[k] in YES_NO) p[k] = YES_NO[v[k]];
  }
  text("goal");
  return p;
}

export const EMPTY_PROFILE = {
  region: "", province: "", municipality: "", farm_activities: [], crop_types: "", agricultural_area_hectares: "", irrigated_hectares: "",
  livestock_type: [], head_count: "", production_system: "", legal_form: "",
  holder_age: "", years_active: "", pasture_hectares: "", rega_registered: "", active_farmer: "", goal: "",
};

// What is stored in localStorage may be incomplete or corrupt: normalise it for the controlled inputs.
export function normalizeStoredProfile(stored) {
  const profile = { ...EMPTY_PROFILE, livestock_type: [] };
  if (!stored || typeof stored !== "object") return profile;
  for (const k of Object.keys(EMPTY_PROFILE)) {
    if (k === "livestock_type" || k === "farm_activities") {
      profile[k] = Array.isArray(stored[k]) ? stored[k].filter((x) => typeof x === "string") : [];
    } else if (typeof stored[k] === "string" || typeof stored[k] === "number") {
      profile[k] = String(stored[k]);
    }
  }
  return profile;
}
