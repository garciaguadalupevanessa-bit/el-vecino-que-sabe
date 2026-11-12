import { FARM_ACTIVITIES, LIVESTOCK, REGIONS } from "../lib/profile.js";

// Labels are user-facing (Spanish); option values are the English values the backend expects.
const YES_NO = [["", "No lo sé"], ["yes", "Sí"], ["no", "No"]];
const SYSTEMS = [["", "Sin indicar"], ["extensive", "Extensivo"], ["intensive", "Intensivo"], ["organic", "Ecológico"], ["mixed", "Mixto"]];
const LEGAL_FORMS = [
  ["", "Sin indicar"], ["individual", "Persona física"], ["limited_company", "Sociedad limitada"],
  ["corporation", "Sociedad anónima"], ["cooperative", "Cooperativa"], ["joint_property", "Comunidad de bienes"], ["other", "Otra"],
];
const GOALS = [
  ["", "Sin indicar"], ["income", "Apoyo a la renta"], ["start_up", "Incorporarme al sector"],
  ["modernization", "Modernizar la explotación"], ["insurance", "Seguro agrario"], ["animal_health", "Sanidad animal"],
  ["organic", "Producción ecológica"], ["other", "Otro"],
];

export default function ProfileForm({ values, errors, onChange, onExample, onClear }) {
  const set = (field) => (e) => onChange({ ...values, [field]: e.target.value });

  const toggleLivestock = (value) => {
    const selected = new Set(values.livestock_type);
    if (selected.has(value)) selected.delete(value);
    else selected.add(value);
    onChange({ ...values, livestock_type: [...selected] });
  };
  const toggleActivity = (value) => {
    const selected = new Set(values.farm_activities);
    if (selected.has(value)) selected.delete(value);
    else selected.add(value);
    onChange({ ...values, farm_activities: [...selected] });
  };

  const textField = (id, label) => (
    <>
      <label htmlFor={id}>{label}</label>
      <input id={id} type="text" maxLength={id === "municipality" ? 100 : 60} value={values[id]} onChange={set(id)} />
    </>
  );

  const numberField = (id, label, extra = {}) => (
    <div>
      <label htmlFor={id}>{label}</label>
      <input
        id={id} type="number" inputMode="decimal" value={values[id]} onChange={set(id)}
        aria-invalid={errors[id] ? "true" : "false"} aria-describedby={`err-${id}`} {...extra}
      />
      <span className="error" id={`err-${id}`}>{errors[id] ?? ""}</span>
    </div>
  );

  const selectField = (id, label, options) => (
    <div>
      <label htmlFor={id}>{label}</label>
      <select id={id} value={values[id]} onChange={set(id)}>
        {options.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
      </select>
    </div>
  );

  return (
    <aside className="panel profile" aria-labelledby="profile-title">
      <h2 id="profile-title">Tu explotación</h2>
      <p className="help">Cuanto más completes, más precisa será la respuesta. Todo es opcional.</p>

      <form onSubmit={(e) => e.preventDefault()} noValidate autoComplete="off">
        <label htmlFor="region">Comunidad autónoma</label>
        <select id="region" value={values.region} onChange={set("region")}>
          <option value="">Selecciona…</option>
          {REGIONS.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>

        {textField("province", "Provincia")}
        {textField("municipality", "Municipio")}

        <fieldset>
          <legend>Actividad de la explotación</legend>
          <div className="checks">
            {FARM_ACTIVITIES.map(([value, label]) => (
              <label key={value}><input type="checkbox" checked={values.farm_activities.includes(value)} onChange={() => toggleActivity(value)} />{label}</label>
            ))}
          </div>
        </fieldset>

        <label htmlFor="crop_types">Cultivos (separados por comas)</label>
        <input id="crop_types" type="text" maxLength={500} value={values.crop_types} onChange={set("crop_types")} placeholder="Cereal, olivar…" />
        <div className="row">
          {numberField("agricultural_area_hectares", "Superficie agrícola (ha)", { min: 0, step: "any" })}
          {numberField("irrigated_hectares", "Superficie de regadío (ha)", { min: 0, step: "any" })}
        </div>

        <fieldset>
          <legend>Tipo de ganado</legend>
          <div className="checks">
            {LIVESTOCK.map(([value, label]) => (
              <label key={value}>
                <input type="checkbox" checked={values.livestock_type.includes(value)} onChange={() => toggleLivestock(value)} />
                {label}
              </label>
            ))}
          </div>
        </fieldset>

        {numberField("head_count", "Número de cabezas", { min: 0, max: 1000000 })}
        {selectField("production_system", "Sistema de producción", SYSTEMS)}
        {selectField("legal_form", "Forma jurídica del titular", LEGAL_FORMS)}

        <div className="row">
          {numberField("holder_age", "Edad del titular", { min: 16, max: 110 })}
          {numberField("years_active", "Años en activo", { min: 0, max: 80 })}
        </div>

        {numberField("pasture_hectares", "Hectáreas de pasto", { min: 0, step: "any" })}

        <div className="row">
          {selectField("rega_registered", "¿Inscrita en REGA?", YES_NO)}
          {selectField("active_farmer", "¿Agricultor activo?", YES_NO)}
        </div>

        {selectField("goal", "¿Qué quieres conseguir?", GOALS)}

        <div className="actions">
          <button type="button" className="secondary" onClick={onExample}>Cargar ejemplo</button>
          <button type="button" className="secondary" onClick={onClear}>Borrar perfil</button>
        </div>
      </form>
    </aside>
  );
}
