// "Ajustes" (wireframes Paso 13, 19, 20 and V6). Only screens that work without accounts:
// accounts, subscription and payments are out of the MVP.
import { useEffect, useRef } from 'react';
import { VoiceSettings } from './Voice.jsx';
import { APP_NAME } from '../lib/brand.js';

const ICONS = {
  farm: 'M12 3 3 9v12h6v-6h6v6h6V9l-9-6Zm0 2.5 7 4.7V19h-2v-6H7v6H5v-8.8l7-4.7Z',
  voice: 'M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-2.08A7 7 0 0 0 19 12h-2Z',
  map: 'M15 5.1 9 3 3 5v16l6-2 6 2 6-2V3l-6 2.1ZM10 5.5l4 1.4v11.6l-4-1.4V5.5ZM5 6.4l3-1v11.6l-3 1V6.4Zm14 11.2-3 1V7l3-1v11.6Z',
  trash: 'M9 3h6l1 2h4v2H4V5h4l1-2Zm-3 6h12l-1 12H7L6 9Zm4 2v8h2v-8h-2Zm4 0v8h2v-8h-2Z',
  help: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16Zm-1-5h2v2h-2v-2Zm1-9a4 4 0 0 0-4 4h2a2 2 0 1 1 3.2 1.6c-.9.7-2.2 1.6-2.2 3.4h2c0-.9.6-1.4 1.4-2A4 4 0 0 0 12 6Z',
  doc: 'M6 2h8l6 6v14H6V2Zm7 1.5V9h5.5L13 3.5ZM8 12v2h8v-2H8Zm0 4v2h8v-2H8Z',
  chevron: 'm9 6 6 6-6 6-1.4-1.4 4.6-4.6-4.6-4.6L9 6Z',
  back: 'M20 11H7.8l5.6-5.6L12 4l-8 8 8 8 1.4-1.4L7.8 13H20v-2Z',
};

function Icon({ name, className = 'settings-icon' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d={ICONS[name]} /></svg>
  );
}

function Row({ icon, title, subtitle, onClick, danger }) {
  return (
    <li>
      <button type="button" className={`settings-row${danger ? ' settings-row-danger' : ''}`} onClick={onClick}>
        <span className="settings-tile"><Icon name={icon} /></span>
        <span className="settings-text"><strong>{title}</strong>{subtitle && <span>{subtitle}</span>}</span>
        <Icon name="chevron" className="settings-chevron" />
      </button>
    </li>
  );
}

function Group({ label, children }) {
  return (
    <section className="settings-group" aria-label={label}>
      <h3 className="settings-group-label">{label}</h3>
      <ul>{children}</ul>
    </section>
  );
}

function Page({ title, onBack, backLabel = 'Volver a Ajustes', children }) {
  const h = useRef(null);
  useEffect(() => { h.current?.focus(); }, []);
  return (
    <div className="settings">
      <button type="button" className="btn btn-ghost back" onClick={onBack}><Icon name="back" className="back-icon" /> {backLabel}</button>
      <h2 ref={h} tabIndex={-1}>{title}</h2>
      {children}
    </div>
  );
}

function Faq({ q, children, open = false }) {
  return (
    <details className="collapsible faq" open={open}>
      <summary><Icon name="help" className="faq-icon" /> {q}</summary>
      <div className="collapsible-body">{children}</div>
    </details>
  );
}

function Help({ onBack, onAsk, onGo }) {
  return (
    <Page title="Ayuda" onBack={onBack}>
      <button type="button" className="btn btn-block" onClick={() => onAsk(null)}>Preguntar al asistente</button>
      <h3 className="settings-sub">Preguntas frecuentes</h3>
      <Faq q="¿Me garantiza que me concedan una ayuda?" open>
        <p>No. Te orientamos sobre los requisitos. La decisión es siempre de la administración: confirma en la fuente oficial o en tu oficina comarcal.</p>
      </Faq>
      <Faq q="¿Qué significa «Pendiente de comprobar»?">
        <p>Que con los datos que tenemos no podemos confirmar todos los requisitos: falta algún dato de tu explotación o la regla todavía no está comprobada en la fuente oficial. No es un «no».</p>
      </Faq>
      <Faq q="¿Cómo cambio los datos de mi explotación?">
        <p>En «Mi explotación». Al guardar, puedes volver a revisar tus ayudas con los datos nuevos.</p>
        <button type="button" className="btn btn-secondary" onClick={() => onGo('explotacion')}>Ir a Mi explotación</button>
      </Faq>
      <Faq q="¿Qué hacéis con mis datos?">
        <p>Tu explotación y tus conversaciones se guardan solo en este dispositivo. Para responderte, enviamos tu pregunta y los datos de tu explotación al servicio; no guardamos tu voz. Nunca te pediremos DNI ni datos bancarios. Puedes borrarlo todo en «Borrar mis datos».</p>
      </Faq>
      <div className="card">
        <h3 className="settings-sub">¿Necesitas hablar con alguien?</h3>
        <p>Para dudas sobre tu solicitud, tu <strong>oficina comarcal agraria</strong> es la referencia oficial.</p>
      </div>
      <div className="card">
        <h3 className="settings-sub">Guías rápidas</h3>
        <Faq q="Cómo leer un resultado">
          <p>Cada ayuda muestra si encaja (✓ Encaje favorable, ! Pendiente de comprobar, ✕ No cumple los requisitos conocidos), qué requisito lo decide, su fuente oficial y si la información está verificada.</p>
        </Faq>
        <Faq q="Qué es la solicitud única de la PAC">
          <p>Es la solicitud anual con la que se piden las ayudas directas de la PAC, en la sede electrónica de tu comunidad o a través de una entidad colaboradora.</p>
          <button type="button" className="btn btn-secondary" onClick={() => onAsk('¿Qué es la solicitud única de la PAC? Explícamelo.')}>Preguntar al asistente</button>
        </Faq>
        <Faq q="Qué es el REGA">
          <p>El Registro General de Explotaciones Ganaderas. Muchas ayudas ganaderas piden estar inscrito.</p>
          <button type="button" className="btn btn-secondary" onClick={() => onAsk('¿Qué es el REGA? Explícamelo.')}>Preguntar al asistente</button>
        </Faq>
      </div>
    </Page>
  );
}

function Terms({ onBack }) {
  return (
    <Page title="Términos y condiciones" onBack={onBack}>
      <p className="support">Resumen en lenguaje sencillo.</p>
      <Faq q={`1. Qué es ${APP_NAME}`} open>
        <p>Un servicio de orientación sobre ayudas públicas agrarias y ganaderas. No es un organismo oficial ni presenta solicitudes.</p>
      </Faq>
      <Faq q="2. Información orientativa" open>
        <p>La información puede cambiar en cada convocatoria. No garantizamos que se conceda ninguna ayuda. Confirma siempre en la fuente oficial.</p>
      </Faq>
      <Faq q="3. Tus datos">
        <p>No pedimos datos identificativos. Tu explotación y tus conversaciones se guardan solo en este dispositivo y puedes borrarlos cuando quieras.</p>
      </Faq>
      <Faq q="4. Responsabilidad">
        <p>Las decisiones sobre solicitudes son tuyas y de la administración. Ante cualquier duda, consulta tu oficina comarcal o un profesional.</p>
      </Faq>
      <p className="notice notice-warning">Proyecto del Tech for Inclusion Challenge: los textos legales completos están pendientes de redactar.</p>
    </Page>
  );
}

function Coverage({ onBack, health, isMock }) {
  return (
    <Page title="Cobertura" onBack={onBack}>
      <div className="card">
        <p><strong>Qué cubrimos hoy</strong></p>
        <ul>
          <li>Ayudas estatales de la PAC: sí.</li>
          <li>Ayudas de la comunidad autónoma que tenemos cargada: sí.</li>
          <li>Resto de comunidades y ayudas locales: todavía no.</li>
        </ul>
        <p className="support">Estamos ampliando la base de ayudas comprobadas. Si no encontramos nada para ti, te lo diremos claramente.</p>
      </div>
      <div className="card">
        <p><strong>Estado del servicio</strong></p>
        <p>
          {!health && 'Comprobando el servicio…'}
          {health?.status === 'error' && 'No hemos podido conectar con el servicio ahora mismo.'}
          {health && health.status !== 'error' && (
            <>Ayudas en nuestra base: {health.aids_loaded ?? '—'}{health.llm_configured === false && !isMock ? ' · asistente sin configurar' : ' · asistente disponible'}</>
          )}
        </p>
      </div>
    </Page>
  );
}

function ClearData({ onBack, onConfirm }) {
  return (
    <Page title="Borrar mis datos" onBack={onBack}>
      <div className="card" role="alertdialog" aria-labelledby="clear-q" aria-describedby="clear-d">
        <p id="clear-q"><strong>¿Borrar tus datos de este dispositivo?</strong></p>
        <p id="clear-d">Se borran tu explotación, todas tus conversaciones, las ayudas encontradas y tus preferencias de voz. No se puede deshacer.</p>
        <div className="btn-row">
          <button type="button" className="btn btn-danger" onClick={onConfirm}>Sí, borrar mis datos</button>
          <button type="button" className="btn btn-secondary" onClick={onBack}>Cancelar</button>
        </div>
      </div>
    </Page>
  );
}

export default function Settings({ page, setPage, summary, voiceSettings, setVoiceSettings, speaker, health, isMock, onGo, onAsk, onClear }) {
  const back = () => setPage(null);
  if (page === 'voz') {
    return (
      <Page title="Voz" onBack={back}>
        <VoiceSettings settings={voiceSettings} setSettings={setVoiceSettings} speaker={speaker} />
      </Page>
    );
  }
  if (page === 'cobertura') return <Coverage onBack={back} health={health} isMock={isMock} />;
  if (page === 'ayuda') return <Help onBack={back} onAsk={onAsk} onGo={onGo} />;
  if (page === 'terminos') return <Terms onBack={back} />;
  if (page === 'borrar') return <ClearData onBack={back} onConfirm={onClear} />;

  return (
    <HubTitle>
      <Group label="Tu explotación">
        <Row icon="farm" title="Mi explotación" subtitle={summary} onClick={() => onGo('explotacion')} />
        <Row icon="voice" title="Voz" subtitle={voiceSettings.micEnabled ? 'Hablar y escuchar las respuestas' : 'Desactivada'} onClick={() => setPage('voz')} />
        <Row icon="map" title="Cobertura" subtitle="Qué ayudas buscamos hoy" onClick={() => setPage('cobertura')} />
      </Group>
      <Group label="Ayuda y legal">
        <Row icon="help" title="Ayuda" subtitle="Preguntas frecuentes y guías rápidas" onClick={() => setPage('ayuda')} />
        <Row icon="doc" title="Términos y condiciones" subtitle="Uso, privacidad y aviso legal" onClick={() => setPage('terminos')} />
      </Group>
      <Group label="Tus datos">
        <Row icon="trash" title="Borrar mis datos" subtitle="Se guardan solo en este dispositivo" onClick={() => setPage('borrar')} danger />
      </Group>
      <p className="support settings-version">Versión 0.1 · {APP_NAME}</p>
    </HubTitle>
  );
}

function HubTitle({ children }) {
  const h = useRef(null);
  useEffect(() => { h.current?.focus(); }, []);
  return (
    <div className="settings">
      <h2 ref={h} tabIndex={-1}>Ajustes</h2>
      {children}
    </div>
  );
}
