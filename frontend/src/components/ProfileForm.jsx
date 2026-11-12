import { useEffect, useState } from 'react';
import {
  COMUNIDADES, TIPO_GANADO, SISTEMA, FORMA_JURIDICA, OBJETIVO,
  validateProfile, profileToForm,
} from '../lib/profile.js';

function Field({ id, label, hint, error, children }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {error ? <p className="field-error" id={`${id}-error`}>{error}</p> : hint && <p className="hint" id={`${id}-hint`}>{hint}</p>}
    </div>
  );
}

function Select({ id, value, onChange, options, error }) {
  return (
    <select id={id} value={value ?? ''} onChange={(e) => onChange(e.target.value)} aria-invalid={error ? 'true' : undefined}>
      <option value="">Sin responder</option>
      {options.map((o) => (typeof o === 'string' ? <option key={o} value={o}>{o}</option> : <option key={o.value} value={o.value}>{o.label}</option>))}
    </select>
  );
}

function YesNo({ name, legend, hint, value, onChange }) {
  const opts = [['true', 'Sí'], ['false', 'No'], ['', 'No lo sé']];
  return (
    <fieldset className="field form-section">
      <legend className="label">{legend}</legend>
      <div className="segmented">
        {opts.map(([v, l]) => (
          <label key={l}>
            <input type="radio" name={name} value={v} checked={(value ?? '') === v} onChange={() => onChange(v)} />
            <span>{l}</span>
          </label>
        ))}
      </div>
      {hint && <p className="hint">{hint}</p>}
    </fieldset>
  );
}

export default function ProfileForm({ profile, onSave, onClear, onRecheck, canRecheck, onCollapse }) {
  const [form, setForm] = useState(() => profileToForm(profile));
  const [errors, setErrors] = useState({});
  const [saved, setSaved] = useState(false);

  // Keep the form in sync when the profile changes elsewhere (quick replies, "Borrar mis datos").
  useEffect(() => { setForm(profileToForm(profile)); setErrors({}); }, [profile]);

  const set = (k) => (v) => { setForm((f) => ({ ...f, [k]: v })); setSaved(false); };
  const err = (k) => errors[k];
  const inv = (k) => (errors[k] ? { 'aria-invalid': 'true', 'aria-describedby': `pf-${k}-error` } : {});

  const toggleGanado = (v) => {
    const list = new Set(form.tipo_ganado ?? []);
    list.has(v) ? list.delete(v) : list.add(v);
    set('tipo_ganado')([...list]);
  };

  const submit = (e) => {
    e.preventDefault();
    const { profile: clean, errors: errs } = validateProfile(form);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    onSave(clean);
    setSaved(true);
  };

  return (
    <form className="card" onSubmit={submit} noValidate aria-labelledby="profile-title">
      <div className="profile-head">
        <h2 id="profile-title">Mi explotación</h2>
        {onCollapse && <button type="button" className="btn btn-ghost desktop-collapse" onClick={onCollapse} aria-label="Plegar Mi explotación">«</button>}
      </div>
      <p className="support">Todo es opcional. Cámbialo cuando quieras: las ayudas se vuelven a revisar.</p>

      <fieldset className="form-section">
        <legend>Ubicación</legend>
        <Field id="pf-comunidad" label="Comunidad autónoma" error={err('comunidad')} hint="Las ayudas cambian según la comunidad.">
          <Select id="pf-comunidad" value={form.comunidad} onChange={set('comunidad')} options={COMUNIDADES} error={err('comunidad')} />
        </Field>
        <Field id="pf-provincia" label="Provincia" error={err('provincia')}>
          <input id="pf-provincia" type="text" maxLength={60} value={form.provincia ?? ''} onChange={(e) => set('provincia')(e.target.value)} autoComplete="off" {...inv('provincia')} />
        </Field>
      </fieldset>

      <fieldset className="form-section">
        <legend>Actividad</legend>
        <div className="checks" role="group" aria-label="Tipo de ganado">
          {TIPO_GANADO.map((o) => (
            <label key={o.value} className="check">
              <input type="checkbox" checked={(form.tipo_ganado ?? []).includes(o.value)} onChange={() => toggleGanado(o.value)} />
              {o.label}
            </label>
          ))}
        </div>
        <Field id="pf-sistema" label="Sistema de producción" hint="El sistema (extensivo, intensivo…) cambia qué ayudas encajan.">
          <Select id="pf-sistema" value={form.sistema} onChange={set('sistema')} options={SISTEMA} />
        </Field>
      </fieldset>

      <fieldset className="form-section">
        <legend>Tamaño</legend>
        <Field id="pf-num_cabezas" label="Número aproximado de cabezas" error={err('num_cabezas')} hint="Si no lo sabes, déjalo en blanco.">
          <input id="pf-num_cabezas" type="text" inputMode="numeric" value={form.num_cabezas ?? ''} onChange={(e) => set('num_cabezas')(e.target.value)} placeholder="Ej.: 300" {...inv('num_cabezas')} />
        </Field>
        <Field id="pf-hectareas_pasto" label="Hectáreas de pasto" error={err('hectareas_pasto')}>
          <input id="pf-hectareas_pasto" type="text" inputMode="decimal" value={form.hectareas_pasto ?? ''} onChange={(e) => set('hectareas_pasto')(e.target.value)} {...inv('hectareas_pasto')} />
        </Field>
      </fieldset>

      <fieldset className="form-section">
        <legend>Registros</legend>
        <YesNo name="pf-rega" legend="¿Inscrita en el REGA?" hint="Solo necesito sí o no, no el número." value={form.inscrita_rega} onChange={set('inscrita_rega')} />
        <YesNo name="pf-activo" legend="¿Agricultor activo?" hint="Requisito para cobrar los pagos directos de la PAC." value={form.agricultor_activo} onChange={set('agricultor_activo')} />
      </fieldset>

      <fieldset className="form-section">
        <legend>Otros datos</legend>
        <Field id="pf-edad_titular" label="Edad del titular" error={err('edad_titular')}>
          <input id="pf-edad_titular" type="text" inputMode="numeric" value={form.edad_titular ?? ''} onChange={(e) => set('edad_titular')(e.target.value)} {...inv('edad_titular')} />
        </Field>
        <Field id="pf-anos_actividad" label="Años de actividad" error={err('anos_actividad')}>
          <input id="pf-anos_actividad" type="text" inputMode="numeric" value={form.anos_actividad ?? ''} onChange={(e) => set('anos_actividad')(e.target.value)} {...inv('anos_actividad')} />
        </Field>
        <Field id="pf-forma_juridica" label="Forma jurídica">
          <Select id="pf-forma_juridica" value={form.forma_juridica} onChange={set('forma_juridica')} options={FORMA_JURIDICA} />
        </Field>
        <Field id="pf-objetivo" label="Qué buscas">
          <Select id="pf-objetivo" value={form.objetivo} onChange={set('objetivo')} options={OBJETIVO} />
        </Field>
      </fieldset>

      {Object.keys(errors).length > 0 && <p className="field-error" role="alert">Revisa los campos marcados.</p>}
      <div className="profile-actions">
        <button type="submit" className="btn btn-block">Guardar mi explotación</button>
        <p className="saved-note" role="status">{saved ? 'Guardado en este dispositivo.' : ''}</p>
        {saved && canRecheck && <button type="button" className="btn btn-secondary btn-block" onClick={onRecheck}>Volver a revisar mis ayudas</button>}
        <p className="support">Se guarda solo en este dispositivo. Nunca te pediremos DNI ni datos bancarios.</p>
        <button type="button" className="btn btn-danger btn-block" onClick={onClear}>Borrar mis datos</button>
      </div>
    </form>
  );
}
