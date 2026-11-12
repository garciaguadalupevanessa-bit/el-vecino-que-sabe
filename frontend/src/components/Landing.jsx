// Public landing page (wireframe Paso 1) and the optional sign-in / sign-up screens
// (Paso 2 and 3). Accounts are out of the MVP: those two screens are a labelled preview
// with disabled fields (no passwords are collected); "Seguir sin cuenta" is the real path.
import { useEffect, useRef } from 'react';
import { APP_NAME, APP_TAGLINE } from '../lib/brand.js';
import { RELIABILITY } from '../lib/aids.js';

function Logo() {
  return <img className="brand-mark" src="/favicon.svg" alt="" width="32" height="32" />;
}

function Faq({ q, children, open }) {
  return (
    <details className="collapsible faq" open={open}>
      <summary>{q}</summary>
      <div className="collapsible-body">{children}</div>
    </details>
  );
}

// Original decorative illustration (fields, sun, sheep) instead of the photo placeholder.
function FieldsArt() {
  return (
    <svg className="landing-art" viewBox="0 0 400 280" role="img" aria-label="Ilustración de un campo con ovejas">
      <rect width="400" height="280" rx="16" className="art-sky" />
      <circle cx="320" cy="70" r="34" className="art-sun" />
      <path d="M0 170 Q100 120 200 160 T400 150 V280 H0Z" className="art-hill-back" />
      <path d="M0 210 Q120 170 230 205 T400 195 V280 H0Z" className="art-hill" />
      {[[90, 215], [140, 228], [250, 222]].map(([x, y]) => (
        <g key={x} transform={`translate(${x} ${y})`} className="art-sheep">
          <ellipse cx="0" cy="0" rx="20" ry="13" className="art-wool" />
          <circle cx="20" cy="-6" r="7" className="art-head" />
          <rect x="-12" y="9" width="4" height="10" className="art-head" />
          <rect x="8" y="9" width="4" height="10" className="art-head" />
        </g>
      ))}
    </svg>
  );
}

export function Landing({ onStart, onLogin }) {
  return (
    <div className="landing">
      <a className="skip-link" href="#landing-main">Saltar al contenido</a>
      <header className="landing-nav">
        <span className="brand"><Logo />{APP_NAME}</span>
        <nav aria-label="Secciones de la página" className="landing-links">
          <a href="#como-funciona">Cómo funciona</a>
          <a href="#fiarte">Por qué fiarte</a>
          <a href="#cubrimos">Qué cubrimos</a>
          <a href="#preguntas">Preguntas</a>
        </nav>
        <button type="button" className="btn btn-ghost" onClick={onLogin}>Entrar</button>
        <button type="button" className="btn" onClick={onStart}>Buscar ayudas</button>
      </header>

      <main id="landing-main">
        <section className="landing-hero landing-band">
          <div className="landing-wrap landing-hero-grid">
            <div>
              <p className="pill">Para agricultores y ganaderos de España</p>
              <h1>Descubre qué ayudas pueden encajar con tu explotación.</h1>
              <p className="landing-lead">{APP_TAGLINE} Sin papeleo para empezar.</p>
              <div className="btn-row">
                <button type="button" className="btn" onClick={onStart}>Buscar ayudas</button>
                <a className="btn btn-secondary" href="#como-funciona">Cómo funciona</a>
              </div>
              <p className="support">Gratis · Sin registro · Sin DNI ni datos bancarios</p>
            </div>
            <FieldsArt />
          </div>
        </section>

        <section className="landing-band landing-band-light">
          <div className="landing-wrap landing-two">
            <h2>Puede haber ayudas que encajen con tu explotación y que todavía no conozcas.</h2>
            <p className="muted">Están repartidas entre el BOE, la BDNS, el FEGA y los boletines de cada comunidad, y escritas en lenguaje administrativo. Te ayudamos a ordenarlas.</p>
          </div>
        </section>

        <section className="landing-band" id="como-funciona" aria-labelledby="como-title">
          <div className="landing-wrap">
            <h2 id="como-title">Cómo funciona</h2>
            <ol className="landing-steps">
              <li className="card"><span className="step-n">1</span><h3>Cuéntanos lo básico</h3><p>Dónde está tu explotación, qué actividad tienes y su tamaño aproximado. Nada más para empezar.</p></li>
              <li className="card"><span className="step-n">2</span><h3>Revisamos los requisitos</h3><p>Buscamos en nuestra base de ayudas oficiales y comprobamos con reglas fijas qué encaja y qué falta.</p></li>
              <li className="card"><span className="step-n">3</span><h3>Te decimos qué hacer</h3><p>Pasos, documentos y el enlace a la ficha oficial. Y alternativas si una ayuda no encaja.</p></li>
            </ol>
          </div>
        </section>

        <section className="landing-band landing-band-light" id="fiarte" aria-labelledby="fiarte-title">
          <div className="landing-wrap landing-two">
            <div>
              <h2 id="fiarte-title">Por qué puedes fiarte</h2>
              <p>No inventamos importes, plazos ni requisitos. Si un dato no está comprobado, te lo decimos.</p>
              {Object.entries(RELIABILITY).map(([key, r]) => (
                <p key={key}><span className="badge badge-reliability">{r.label}</span><br /><span className="support">{r.help}</span></p>
              ))}
              <p>Cada ayuda muestra su fuente oficial, el organismo responsable y la fecha en que la comprobamos.</p>
            </div>
            <div>
              <p className="eyebrow">Así se ve un resultado</p>
              <div className="card card-featured">
                <div className="badges">
                  <span className="badge tone-success"><span className="badge-icon" aria-hidden="true"><span>✓</span></span>Encaje favorable</span>
                  <span className="badge badge-example">Ejemplo ilustrativo · no es una ayuda real</span>
                </div>
                <h3>Ayuda de ejemplo · pago asociado al ovino</h3>
                <ul className="req-list">
                  <li><span className="req-icon tone-success" aria-hidden="true">✓</span><span>Actividad ganadera: <strong>coincide</strong></span></li>
                  <li><span className="req-icon tone-success" aria-hidden="true">✓</span><span>Ubicación: <strong>coincide</strong></span></li>
                  <li><span className="req-icon tone-warning" aria-hidden="true">!</span><span>Agricultor activo: <strong>pendiente de confirmar</strong></span></li>
                </ul>
                <p className="support">Fuente oficial · organismo responsable · fecha de comprobación</p>
              </div>
            </div>
          </div>
        </section>

        <section className="landing-band" id="cubrimos" aria-labelledby="cubrimos-title">
          <div className="landing-wrap landing-narrow">
            <h2 id="cubrimos-title">Qué cubrimos hoy</h2>
            <ul className="req-list">
              <li><span className="req-icon tone-success" aria-hidden="true">✓</span><span><strong>Ayudas estatales de la PAC:</strong> sí</span></li>
              <li><span className="req-icon tone-warning" aria-hidden="true">!</span><span><strong>Ayudas de una comunidad autónoma:</strong> en preparación</span></li>
              <li><span className="req-icon tone-error" aria-hidden="true">✕</span><span><strong>Resto de comunidades y ayudas locales:</strong> todavía no</span></li>
            </ul>
            <p className="muted">Estamos ampliando la base de ayudas comprobadas. Si no encontramos nada para ti, te lo diremos claramente.</p>
          </div>
        </section>

        <section className="landing-band landing-band-light" id="preguntas" aria-labelledby="faq-title">
          <div className="landing-wrap landing-narrow">
            <h2 id="faq-title">Preguntas frecuentes</h2>
            <Faq q="¿Me garantiza que me concedan una ayuda?" open><p>No. Te orientamos sobre los requisitos con la información disponible. La decisión es siempre de la administración: confirma en la fuente oficial o en tu oficina comarcal.</p></Faq>
            <Faq q="¿Tengo que registrarme o dar mi DNI?"><p>No. Puedes usarlo sin cuenta y nunca te pediremos DNI ni datos bancarios. Lo que nos cuentes se guarda solo en tu dispositivo.</p></Faq>
            <Faq q="¿Presentáis la solicitud por mí?"><p>No. Te explicamos los pasos y te damos el enlace oficial; la solicitud la presentas tú o tu entidad colaboradora.</p></Faq>
            <Faq q="¿Qué ayudas cubrís?"><p>Hoy, ayudas estatales de la PAC y las de la comunidad que tenemos cargada. Estamos ampliando la base.</p></Faq>
            <Faq q="¿De dónde sale la información?"><p>De fuentes oficiales (FEGA, BOE, BDNS y boletines autonómicos). Cada ayuda muestra su fuente, la fecha en que la comprobamos y si está verificada.</p></Faq>
          </div>
        </section>

        <section className="landing-band">
          <div className="landing-wrap">
            <div className="landing-cta">
              <div>
                <h2>Empieza con tres preguntas</h2>
                <p>Sin registro. Como hablar con un técnico de la cooperativa.</p>
              </div>
              <button type="button" className="btn btn-on-dark" onClick={onStart}>Buscar ayudas</button>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-wrap">
          <p><strong>{APP_NAME}</strong></p>
          <p>Información orientativa sobre ayudas públicas. No sustituye a la resolución de la administración ni al asesoramiento profesional.</p>
          <p>Tech for Inclusion Challenge · Ebury × Somos F5</p>
        </div>
      </footer>
    </div>
  );
}

function AuthShell({ title, intro, onBack, children }) {
  const h = useRef(null);
  useEffect(() => { h.current?.focus(); }, []);
  return (
    <div className="auth">
      <main className="auth-card card">
        <button type="button" className="btn btn-ghost back" onClick={onBack}>← Volver</button>
        <h1 ref={h} tabIndex={-1}>{title}</h1>
        <p className="muted">{intro}</p>
        <p className="notice notice-warning" role="note"><strong>Vista previa.</strong> Las cuentas llegarán después del reto: estos campos están desactivados. Puedes usar todo sin cuenta.</p>
        {children}
      </main>
    </div>
  );
}

/* Paso 2 · Entrar */
export function Login({ onBack, onContinue, onSignup }) {
  return (
    <AuthShell title="Entrar" intro="Entra para recuperar tu explotación y tus conversaciones." onBack={onBack}>
      <div className="field"><label htmlFor="login-mail">Correo electrónico</label><input id="login-mail" type="email" placeholder="nombre@correo.es" disabled autoComplete="off" /></div>
      <div className="field"><label htmlFor="login-pass">Contraseña</label><input id="login-pass" type="password" disabled autoComplete="off" /></div>
      <button type="button" className="btn btn-block" disabled>Entrar</button>
      <p className="auth-or" aria-hidden="true">o</p>
      <button type="button" className="btn btn-secondary btn-block" onClick={onContinue}>Seguir sin cuenta</button>
      <p className="notice notice-info">La cuenta es <strong>opcional</strong>. Servirá para ver tu explotación en el móvil y en el ordenador. Sin cuenta, todo se guarda en este dispositivo.</p>
      <p className="auth-switch">¿No tienes cuenta? <button type="button" className="link-btn" onClick={onSignup}>Crear una</button></p>
    </AuthShell>
  );
}

/* Paso 3 · Crear cuenta */
export function Signup({ onBack, onContinue, onLogin }) {
  return (
    <AuthShell title="Crear cuenta" intro="Solo necesitas un correo. Lo de tu explotación te lo pregunto después, en la conversación, poco a poco." onBack={onBack}>
      <fieldset className="form-section">
        <legend>¿Quién eres?</legend>
        <label className="pay-option pay-option-on pay-head"><input type="radio" name="who" defaultChecked disabled /><span><strong>Agricultor o ganadero</strong><span className="support">Busco ayudas para mi explotación</span></span></label>
        <label className="pay-option pay-head"><input type="radio" name="who" disabled /><span><strong>Técnico o asesor</strong><span className="support">Oriento a otras personas (varias explotaciones: más adelante)</span></span></label>
      </fieldset>
      <div className="field"><label htmlFor="su-name">Nombre</label><input id="su-name" type="text" placeholder="Cómo quieres que te llame" disabled /><p className="hint">Opcional.</p></div>
      <div className="field"><label htmlFor="su-mail">Correo electrónico</label><input id="su-mail" type="email" placeholder="nombre@correo.es" disabled autoComplete="off" /></div>
      <div className="field"><label htmlFor="su-pass">Contraseña</label><input id="su-pass" type="password" disabled autoComplete="off" /><p className="hint">Al menos 8 caracteres.</p></div>
      <p className="notice notice-info">Nunca te pediremos DNI ni datos bancarios.</p>
      <label className="check"><input type="checkbox" disabled /> Acepto la política de privacidad y que los datos de mi explotación se guarden en mi cuenta. Puedo borrarlos cuando quiera.</label>
      <label className="check"><input type="checkbox" disabled /> Entiendo que la información es orientativa y no garantiza que me concedan una ayuda.</label>
      <button type="button" className="btn btn-block" disabled>Crear cuenta y empezar</button>
      <p className="auth-or" aria-hidden="true">o</p>
      <button type="button" className="btn btn-secondary btn-block" onClick={onContinue}>Seguir sin cuenta</button>
      <p className="auth-switch">¿Ya tienes cuenta? <button type="button" className="link-btn" onClick={onLogin}>Entrar</button></p>
    </AuthShell>
  );
}
