import { useState } from 'react';
import { EligibilityBadge, ReliabilityBadge, ExampleBadge, RequirementList, SourceLine, Facts } from './Badges.jsx';
import { shortReason, requirementCounts, formatArgs, formatDate, RELIABILITY } from '../lib/aids.js';

export function CoverageNote() {
  return (
    <p className="notice notice-info">
      Hoy buscamos en ayudas estatales de la PAC y en las de la comunidad que tenemos cargada. Puede haber otras ayudas que aún no tenemos.
    </p>
  );
}

function FeaturedAid({ aid, onOpen, onAlternatives, onAnswerMissing }) {
  const c = requirementCounts(aid);
  return (
    <article className="card card-featured aid-card" aria-labelledby={`aid-${aid.id}`}>
      <div className="badges"><EligibilityBadge value={aid.resultado} />{aid.es_ejemplo && <ExampleBadge />}</div>
      <h3 id={`aid-${aid.id}`}>{aid.nombre}</h3>
      {aid.organismo && <p className="aid-meta">Organismo: {aid.organismo}</p>}
      <h4>¿Por qué puede encajar contigo?</h4>
      <RequirementList requisitos={aid.requisitos} limit={5} />
      <Facts aid={aid} />
      <SourceLine aid={aid} />
      <div className="btn-row">
        <button type="button" className="btn" onClick={() => onOpen(aid.id)}>Ver detalle</button>
        {c.por_confirmar > 0 && aid.resultado !== 'no_elegible' && (
          <button type="button" className="btn btn-secondary" onClick={() => onAnswerMissing(aid)}>Responder lo que falta ({c.por_confirmar})</button>
        )}
        {aid.resultado === 'no_elegible' && <button type="button" className="btn btn-secondary" onClick={() => onAlternatives(aid.id)}>Ver alternativas</button>}
      </div>
    </article>
  );
}

function CompactAid({ aid, onOpen, onAlternatives }) {
  return (
    <article className="card aid-card aid-compact" aria-labelledby={`aid-${aid.id}`}>
      <div className="badges"><EligibilityBadge value={aid.resultado} />{aid.es_ejemplo && <ExampleBadge />}</div>
      <h3 id={`aid-${aid.id}`}>{aid.nombre}</h3>
      <p>{shortReason(aid)}</p>
      <div className="badges"><ReliabilityBadge value={aid.fiabilidad} /></div>
      <div className="btn-row">
        <button type="button" className="btn btn-secondary" onClick={() => onOpen(aid.id)}>Ver detalle</button>
        {aid.resultado === 'no_elegible' && <button type="button" className="btn btn-ghost" onClick={() => onAlternatives(aid.id)}>Ver alternativas</button>}
      </div>
    </article>
  );
}

export function TraceList({ trace }) {
  if (!trace?.length) return <p className="support">En esta respuesta el asistente no ha usado herramientas.</p>;
  return (
    <ol className="trace-list">
      {trace.map((t, i) => (
        <li key={i}>
          <span className="trace-tool">{t.tool}</span>{' '}
          <span className={t.ok ? 'trace-ok' : 'trace-fail'}>{t.ok ? '✓ ok' : '✕ error'}</span>
          <br /><code>{formatArgs(t.args) || 'sin parámetros'}</code>
          {!t.ok && t.error && <><br /><span className="support">{String(t.error)}</span></>}
        </li>
      ))}
    </ol>
  );
}

/** "Cómo hemos comprobado esta información" — the jury/transparency panel. */
export function HowWeChecked({ trace, aid, sources }) {
  const [advanced, setAdvanced] = useState(false);
  const c = aid ? requirementCounts(aid) : null;
  const searched = trace?.find((t) => t.tool === 'search_aids');
  return (
    <details className="collapsible">
      <summary>Cómo hemos comprobado esta información</summary>
      <div className="collapsible-body">
        {searched && <p>Buscamos ayudas con: <code>{formatArgs(searched.args) || 'tu perfil'}</code>.</p>}
        {aid && (
          <>
            <p>Fuente: {aid.host_fuente ?? 'sin enlace verificado'}{aid.fecha_verificacion ? `, comprobada el ${formatDate(aid.fecha_verificacion)}` : ''}.</p>
            <p>Estado: {RELIABILITY[aid.fiabilidad].label}{aid.verificado_por && aid.fiabilidad === 'verificada' ? ' por una segunda persona del equipo' : ''}.</p>
            {c.total > 0 && <p>Requisitos revisados: {c.total} · {c.cumple} encajan, {c.por_confirmar} pendientes, {c.no_cumple} no se cumplen.</p>}
          </>
        )}
        {!aid && sources?.length > 0 && (
          <ul>
            {sources.map((s) => (
              <li key={s.url}>
                <a href={s.url} target="_blank" rel="noopener noreferrer">{s.nombre}</a>
                {s.fecha_verificacion && <span className="support"> · comprobada el {formatDate(s.fecha_verificacion)}</span>}
              </li>
            ))}
          </ul>
        )}
        <p><strong>Los requisitos se comprueban con reglas fijas a partir de tus datos; la IA solo los explica.</strong></p>
        <label className="switch">
          <input type="checkbox" checked={advanced} onChange={(e) => setAdvanced(e.target.checked)} />
          Mostrar vista avanzada
        </label>
        {advanced && (
          <div>
            <h4>Vista avanzada · para el equipo y el jurado</h4>
            <TraceList trace={trace} />
            <p className="support">Del campo «trace» de la respuesta de la API.</p>
          </div>
        )}
      </div>
    </details>
  );
}

export default function AidsPanel({ results, profileSummary, onOpen, onAlternatives, onAnswerMissing, onAskAbout, onStateOnly }) {
  const aids = results?.aids ?? [];
  return (
    <section aria-labelledby="aids-title">
      <h2 id="aids-title">Ayudas encontradas{aids.length ? ` · ${aids.length}` : ''}</h2>
      {!results && (
        <div className="card">
          <p>Cuando me cuentes cómo es tu explotación, aquí verás las ayudas que pueden encajar, la mejor primero.</p>
          <p className="support">Cada ayuda muestra su fuente oficial, el organismo responsable y la fecha en que la comprobamos.</p>
        </div>
      )}
      {results && aids.length === 0 && (
        <div className="card">
          <h3>No he encontrado ayudas con estos datos</h3>
          <p>No es que no existan: es que todavía no las tenemos en nuestra base. Prueba con otra actividad o mira solo las ayudas estatales.</p>
          <div className="btn-row">
            <button type="button" className="btn btn-secondary" onClick={onStateOnly}>Ver solo ayudas estatales</button>
            <a className="btn btn-ghost" href="https://www.mapa.gob.es/es/agricultura/" target="_blank" rel="noopener noreferrer">Buscar en el Ministerio de Agricultura ↗</a>
          </div>
          <p className="support">Tu oficina comarcal agraria también puede orientarte sobre ayudas de tu comunidad.</p>
        </div>
      )}
      {aids.length > 0 && (
        <>
          <p>Con lo que me has contado{profileSummary && profileSummary !== 'Sin datos todavía' ? ` (${profileSummary})` : ''} he encontrado {aids.length === 1 ? '1 ayuda' : `${aids.length} ayudas`}. Te pongo primero la que mejor encaja.</p>
          <button type="button" className="btn btn-ghost" onClick={onAskAbout}>Preguntar sobre estas ayudas</button>
          <p className="eyebrow">La que mejor encaja</p>
          <FeaturedAid aid={aids[0]} onOpen={onOpen} onAlternatives={onAlternatives} onAnswerMissing={onAnswerMissing} />
          {aids.length > 1 && <p className="eyebrow">Otras ayudas</p>}
          {aids.slice(1).map((a) => <CompactAid key={a.id || a.nombre} aid={a} onOpen={onOpen} onAlternatives={onAlternatives} />)}
        </>
      )}
      {results && <HowWeChecked trace={results.trace} sources={results.sources} />}
      {results?.coverage?.map((note) => <p key={note} className="notice notice-warning">{note}</p>)}
      <CoverageNote />
    </section>
  );
}
