// Account, subscription and billing (wireframes Paso 14–18) as a PREVIEW for the pitch.
// Accounts and payments are out of the MVP: nothing here charges, sends or stores payment
// data. Card and Bizum fields are shown disabled; "Pagar" only simulates the result.
import { useEffect, useRef, useState } from 'react';

const PRICE = '20,00 €';

export function PreviewNotice() {
  return (
    <p className="notice notice-warning preview-notice" role="note">
      <strong>Vista previa.</strong> Cuentas y pagos todavía no están activos: no se realiza ningún cobro
      ni se guardan datos de pago.
    </p>
  );
}

function Page({ title, onBack, backLabel = 'Volver a Ajustes', step, children }) {
  const h = useRef(null);
  useEffect(() => { h.current?.focus(); }, []);
  return (
    <div className="settings">
      {onBack && <button type="button" className="btn btn-ghost back" onClick={onBack}>← {backLabel}</button>}
      {step && (
        <div className="steps-bar" aria-label={`Contratar Pro · paso ${step} de 2`}>
          <p className="support"><strong>Contratar Pro · paso {step} de 2</strong></p>
          <div className="steps-track"><span className="on" /><span className={step === 2 ? 'on' : ''} /></div>
        </div>
      )}
      <h2 ref={h} tabIndex={-1}>{title}</h2>
      <PreviewNotice />
      {children}
    </div>
  );
}

function Toggle({ id, label, hint, checked, onChange, disabled }) {
  return (
    <div className="toggle-row">
      <label htmlFor={id} className="toggle">
        <span><strong>{label}</strong>{hint && <span className="support toggle-hint">{hint}</span>}</span>
        <input id={id} type="checkbox" role="switch" checked={checked} disabled={disabled} onChange={(e) => onChange?.(e.target.checked)} />
      </label>
    </div>
  );
}

/* Paso 14 · Información de la cuenta */
export function AccountInfo({ onBack, bigText, setBigText, onClearData }) {
  return (
    <Page title="Información de la cuenta" onBack={onBack}>
      <section className="card">
        <h3>Datos personales</h3>
        <div className="field"><label htmlFor="acc-name">Nombre</label><input id="acc-name" type="text" placeholder="Cómo quieres que te llame" disabled /></div>
        <div className="field"><label htmlFor="acc-mail">Correo electrónico</label><input id="acc-mail" type="text" placeholder="nombre@correo.es" disabled />
          <p className="hint">Lo usaremos para entrar y enviarte facturas cuando haya cuentas.</p></div>
        <div className="field"><label htmlFor="acc-role">Soy</label>
          <select id="acc-role" disabled><option>Agricultor o ganadero</option><option>Técnico o asesor</option></select></div>
      </section>
      <section className="card">
        <h3>Preferencias</h3>
        <div className="field"><label htmlFor="acc-lang">Idioma</label><select id="acc-lang" disabled><option>Español</option></select></div>
        <Toggle id="acc-mails" label="Avisos por correo" hint="Novedades de tus ayudas y plazos (plan Pro)" checked={false} disabled />
        <Toggle id="acc-bigtext" label="Tamaño de letra grande" hint="Más fácil de leer en el móvil. Ya funciona." checked={bigText} onChange={setBigText} />
      </section>
      <p className="notice notice-info">Nunca te pediremos DNI ni datos bancarios para usar la app. Solo pediríamos datos de pago si contratas el plan Pro.</p>
      <section className="card">
        <h3>Eliminar cuenta</h3>
        <p className="support">Hoy no hay cuenta: tus datos están solo en este dispositivo. Puedes borrarlos todos.</p>
        <button type="button" className="btn btn-danger" onClick={onClearData}>Borrar mis datos</button>
      </section>
    </Page>
  );
}

const FEATURES = [
  ['Buscar ayudas y ver si encajan', true],
  ['Requisitos explicados y guía de solicitud', true],
  ['Fuente oficial y fecha de cada ayuda', true],
  ['Guardar una explotación', true],
  ['Avisos de nuevas convocatorias y plazos', false],
  ['Varias explotaciones (técnicos y asesores)', false],
  ['Informe en PDF para llevar a la oficina', false],
  ['Soporte prioritario por correo', false],
];

/* Paso 15 · Suscripción */
export function Subscription({ onBack, demo, onChoosePro }) {
  const isPro = demo.plan === 'pro';
  return (
    <Page title="Suscripción" onBack={onBack}>
      <p>Lo esencial es <strong>gratis para siempre</strong>: buscar ayudas, ver si encajan y cómo pedirlas. El plan Pro añade avisos y herramientas para quien gestiona más.</p>
      <div className="plans">
        <table className="plans-table">
          <caption className="visually-hidden">Comparación de planes Gratis y Pro</caption>
          <thead>
            <tr>
              <th scope="col"><span className="visually-hidden">Función</span></th>
              <th scope="col" className="plan-free">Gratis<span className="plan-price">0 €</span><span className="support">siempre</span>{!isPro && <span className="badge tone-success">Tu plan</span>}</th>
              <th scope="col" className="plan-pro">Pro<span className="plan-price">{PRICE.replace(',00', '')}</span><span>al mes · IVA incl.</span>{isPro ? <span className="badge">Tu plan</span> : <span className="badge">Recomendado</span>}</th>
            </tr>
          </thead>
          <tbody>
            {FEATURES.map(([label, free]) => (
              <tr key={label}>
                <th scope="row">{label}</th>
                <td>{free ? <span className="yes">✓ Sí</span> : <span className="no">✕ No</span>}</td>
                <td className="plan-pro-cell"><span className="yes">✓ Sí</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {isPro
        ? <p className="notice notice-info">Ya tienes el plan Pro (demostración). Puedes cancelarlo en Facturación.</p>
        : (
          <div className="profile-actions">
            <button type="button" className="btn btn-block" onClick={onChoosePro}>Contratar Pro · {PRICE}/mes</button>
            <button type="button" className="btn btn-secondary btn-block" onClick={onBack}>Seguir con el plan Gratis</button>
          </div>
        )}
      <p className="support">Sin permanencia: cancelas cuando quieras y mantienes el acceso hasta el final del mes pagado.</p>
    </Page>
  );
}

const METHODS = [
  { value: 'tarjeta', title: 'Tarjeta', sub: 'Débito o crédito · se activa al momento' },
  { value: 'bizum', title: 'Bizum', sub: 'Con tu número de móvil · se activa al momento' },
  { value: 'transferencia', title: 'Transferencia bancaria', sub: 'Se activa en 1–2 días hábiles' },
];

/* Paso 16 · Pago */
export function Payment({ onBack, onPaid }) {
  const [method, setMethod] = useState('tarjeta');
  return (
    <Page title="Forma de pago" onBack={onBack} backLabel="Volver a Suscripción" step={1}>
      <div className="card plan-summary">
        <p><strong>Plan Pro · mensual</strong> <strong className="plan-summary-price">{PRICE}</strong></p>
        <p className="support">IVA incluido · se renueva cada mes · cancela cuando quieras</p>
      </div>
      <fieldset className="form-section">
        <legend>Elige cómo pagar</legend>
        {METHODS.map((m) => (
          <div key={m.value} className={`pay-option${method === m.value ? ' pay-option-on' : ''}`}>
            <label className="pay-head">
              <input type="radio" name="pay" value={m.value} checked={method === m.value} onChange={() => setMethod(m.value)} />
              <span><strong>{m.title}</strong><span className="support">{m.sub}</span></span>
            </label>
            {method === m.value && m.value === 'tarjeta' && (
              <div className="pay-fields">
                <div className="field"><label htmlFor="pay-card">Número de la tarjeta</label><input id="pay-card" type="text" placeholder="0000 0000 0000 0000" disabled autoComplete="off" /></div>
                <div className="pay-row">
                  <div className="field"><label htmlFor="pay-exp">Caducidad</label><input id="pay-exp" type="text" placeholder="MM/AA" disabled autoComplete="off" /></div>
                  <div className="field"><label htmlFor="pay-cvc">CVC</label><input id="pay-cvc" type="text" placeholder="123" disabled autoComplete="off" /></div>
                </div>
                <p className="hint">En esta vista previa los campos están desactivados: no escribas datos reales.</p>
              </div>
            )}
            {method === m.value && m.value === 'bizum' && (
              <div className="pay-fields">
                <div className="field"><label htmlFor="pay-phone">Teléfono asociado a Bizum</label><input id="pay-phone" type="text" placeholder="600 000 000" disabled autoComplete="off" /></div>
                <p className="hint">Recibirías la solicitud de pago en la app de tu banco.</p>
              </div>
            )}
            {method === m.value && m.value === 'transferencia' && (
              <div className="pay-fields">
                <p><strong>Beneficiario:</strong> [RAZÓN SOCIAL]</p>
                <p><strong>IBAN:</strong> [IBAN DE LA EMPRESA]</p>
                <p><strong>Concepto:</strong> [CÓDIGO DE PEDIDO]</p>
                <p className="hint">El plan se activaría cuando recibamos la transferencia (1–2 días hábiles).</p>
              </div>
            )}
          </div>
        ))}
      </fieldset>
      <p className="support">Pago seguro con [PASARELA DE PAGO]. No guardaríamos los datos de tu tarjeta.</p>
      <div className="profile-actions">
        <button type="button" className="btn btn-block" onClick={() => onPaid(method)}>Simular pago de {PRICE}</button>
        <button type="button" className="btn btn-ghost btn-block" onClick={onBack}>Cancelar</button>
      </div>
    </Page>
  );
}

/* Paso 17 · Pago completado */
export function PaymentDone({ demo, onAids, onBilling }) {
  return (
    <Page title="Ya tienes el plan Pro" step={2}>
      <div className="card done-card">
        <p className="done-icon" aria-hidden="true">✓</p>
        <p>Demostración: en la versión real te enviaríamos la factura por correo y verías aquí la fecha del próximo cobro.</p>
      </div>
      <div className="card">
        <h3>Qué podrás hacer</h3>
        <ul className="req-list">
          <li><span className="req-icon tone-success" aria-hidden="true">✓</span><span><strong>Avisos:</strong> de nuevas convocatorias y plazos</span></li>
          <li><span className="req-icon tone-success" aria-hidden="true">✓</span><span><strong>Informe PDF:</strong> para llevar a la oficina</span></li>
          <li><span className="req-icon tone-success" aria-hidden="true">✓</span><span><strong>Varias explotaciones:</strong> para técnicos y asesores</span></li>
        </ul>
      </div>
      {demo.method === 'transferencia' && <p className="notice notice-warning">Si pagas por transferencia, verás «Pendiente de recibir» hasta que llegue el pago.</p>}
      <div className="profile-actions">
        <button type="button" className="btn btn-block" onClick={onAids}>Volver a mis ayudas</button>
        <button type="button" className="btn btn-secondary btn-block" onClick={onBilling}>Ver facturación</button>
      </div>
    </Page>
  );
}

const METHOD_LABEL = { tarjeta: 'Tarjeta de demostración', bizum: 'Bizum (demostración)', transferencia: 'Transferencia bancaria (demostración)' };

/* Paso 18 · Facturación */
export function Billing({ onBack, demo, onChangePlan, onCancel }) {
  const isPro = demo.plan === 'pro';
  return (
    <Page title="Facturación" onBack={onBack}>
      <section className="card">
        <div className="profile-head"><h3>Plan actual</h3><button type="button" className="btn btn-ghost" onClick={onChangePlan}>Cambiar plan</button></div>
        <p>{isPro ? `Pro · ${PRICE}/mes (demostración)` : 'Gratis · 0 €'}</p>
        {isPro && <button type="button" className="btn btn-danger" onClick={onCancel}>Cancelar suscripción</button>}
      </section>
      <section className="card">
        <h3>Método de pago</h3>
        <p>{isPro ? METHOD_LABEL[demo.method] ?? METHOD_LABEL.tarjeta : 'Ninguno: el plan Gratis no necesita pago.'}</p>
      </section>
      <section className="card">
        <h3>Datos de facturación</h3>
        <div className="field"><label htmlFor="bill-name">Nombre o razón social</label><input id="bill-name" type="text" placeholder="Para la factura" disabled /></div>
        <div className="field"><label htmlFor="bill-nif">NIF (solo si necesitas factura completa)</label><input id="bill-nif" type="text" placeholder="Opcional" disabled />
          <p className="hint">Solo para facturas a empresas o autónomos. No hace falta para usar la app.</p></div>
      </section>
      <section className="card">
        <div className="profile-head"><h3>Facturas</h3><span className="badge badge-example">Ejemplo</span></div>
        {isPro ? (
          <ul className="invoices">
            <li><span><strong>[FECHA]</strong><span className="support">Plan Pro · {PRICE}</span></span>
              <span className={`badge ${demo.method === 'transferencia' ? 'tone-warning' : 'tone-success'}`}>{demo.method === 'transferencia' ? 'Pendiente de recibir' : 'Pagada'}</span></li>
          </ul>
        ) : <p className="support">Todavía no hay facturas.</p>}
      </section>
    </Page>
  );
}
