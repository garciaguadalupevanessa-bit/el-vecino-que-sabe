import { ELIGIBILITY, RELIABILITY, REQUIREMENT, NO_VERIFIED, formatDate } from '../lib/aids.js';

export function EligibilityBadge({ value }) {
  const e = ELIGIBILITY[value] ?? ELIGIBILITY.desconocido;
  return (
    <span className={`badge tone-${e.tone}`}>
      <span className="badge-icon" aria-hidden="true"><span>{e.icon}</span></span>
      {e.label}
    </span>
  );
}

export function ReliabilityBadge({ value, withHelp = false }) {
  const r = RELIABILITY[value] ?? RELIABILITY.solo_metadatos;
  return (
    <>
      <span className="badge badge-reliability" title={r.help}>{r.label}</span>
      {withHelp && <p className="support">{r.help}</p>}
    </>
  );
}

export function ExampleBadge() {
  return <span className="badge badge-example">Ejemplo ilustrativo · no es una ayuda real</span>;
}

export function RequirementList({ requisitos, limit }) {
  if (!requisitos?.length) {
    return <p className="support">Todavía no hemos comprobado los requisitos de esta ayuda con tus datos.</p>;
  }
  const shown = limit ? requisitos.slice(0, limit) : requisitos;
  return (
    <ul className="req-list">
      {shown.map((r, i) => {
        const s = REQUIREMENT[r.estado];
        return (
          <li key={`${r.descripcion}-${i}`}>
            <span className={`req-icon tone-${s.tone}`} aria-hidden="true">{s.icon}</span>
            <span>
              {r.descripcion}: <strong>{s.label}</strong>
              {r.detalle && <span className="req-detail">{r.detalle}</span>}
            </span>
          </li>
        );
      })}
      {limit && requisitos.length > limit && <li className="support">y {requisitos.length - limit} más…</li>}
    </ul>
  );
}

export function SourceLine({ aid }) {
  return (
    <div className="source">
      {aid.url_fuente ? (
        <p>
          Fuente oficial:{' '}
          <a href={aid.url_fuente} target="_blank" rel="noopener noreferrer">
            {aid.host_fuente}<span className="visually-hidden"> (se abre en una pestaña nueva)</span> ↗
          </a>
        </p>
      ) : (
        <p>Fuente oficial: sin enlace verificado. Pregunta en tu oficina comarcal.</p>
      )}
      {aid.organismo && <p>{aid.organismo}</p>}
      <p className="muted">
        {aid.fecha_verificacion ? `Comprobado el ${formatDate(aid.fecha_verificacion)}` : 'Fecha de comprobación no disponible'}
        {' · '}<ReliabilityBadge value={aid.fiabilidad} />
      </p>
    </div>
  );
}

export function Facts({ aid }) {
  const value = (v) => (v ? <dd>{v}</dd> : <dd className="unverified">{NO_VERIFIED}</dd>);
  const verified = aid.fiabilidad === 'verificada';
  return (
    <dl className="facts">
      <div className="fact"><dt>Importe</dt>{value(verified || aid.importe ? aid.importe : null)}</div>
      <div className="fact">
        <dt>Plazo</dt>
        {value(aid.plazo ?? (aid.abierta === true ? 'Convocatoria abierta' : aid.abierta === false ? 'Convocatoria cerrada' : null))}
      </div>
    </dl>
  );
}
