import { useEffect, useRef } from 'react';
import { EligibilityBadge, ReliabilityBadge, ExampleBadge, RequirementList, SourceLine, Facts } from './Badges.jsx';
import { HowWeChecked } from './AidsPanel.jsx';
import { requirementCounts, shortReason, RELIABILITY } from '../lib/aids.js';
import { quickRepliesFor } from '../lib/quickReplies.js';

function useFocusHeading(dep) {
  const ref = useRef(null);
  useEffect(() => { ref.current?.focus(); }, [dep]);
  return ref;
}

function Back({ onClick, children }) {
  return <button type="button" className="btn btn-ghost back" onClick={onClick}>← {children}</button>;
}

function LoadingNote({ status }) {
  if (status === 'loading') return <p className="support" role="status">Cargando la ficha completa…</p>;
  if (status === 'error') return <p className="notice notice-warning">No hemos podido cargar la ficha completa. Te mostramos lo que ya sabemos.</p>;
  return null;
}

const MISSING_QUESTIONS = {
  agricultor_activo: '¿Estás dado de alta como agricultor activo?',
  inscrita_rega: '¿Tu explotación está inscrita en el REGA?',
};

export function AidDetail({ aid, status, trace, onBack, onGuide, onAlternatives, onAsk, onQuickReply }) {
  const h = useFocusHeading(aid?.id);
  if (!aid) return <div className="detail"><Back onClick={onBack}>Volver a la conversación</Back><p>No hemos encontrado esa ayuda.</p></div>;
  const c = requirementCounts(aid);
  const missingField = ['agricultor_activo', 'inscrita_rega'].find((f) => aid.datos_faltantes.includes(f));
  const question = missingField ? MISSING_QUESTIONS[missingField] : null;

  return (
    <article className="detail card">
      <Back onClick={onBack}>Volver a la conversación</Back>
      <LoadingNote status={status} />
      <div className="aid-card badges"><EligibilityBadge value={aid.resultado} />{aid.es_ejemplo && <ExampleBadge />}</div>
      <h2 ref={h} tabIndex={-1}>{aid.nombre}</h2>
      <p className="aid-meta">
        {aid.organismo && <>Organismo: {aid.organismo}</>}
        {aid.organismo && aid.ambito && ' · '}
        {aid.ambito && <>Ámbito: {aid.ambito}</>}
      </p>

      {aid.descripcion && <section><h3>En pocas palabras</h3><p>{aid.descripcion}</p></section>}

      <section>
        <h3>¿Por qué puede encajar contigo?</h3>
        <RequirementList requisitos={aid.requisitos} />
        {aid.resultado === 'condicional' && c.por_confirmar > 0 && (
          <p><strong>Siguiente paso:</strong> confirma {c.por_confirmar === 1 ? 'el dato que falta' : `los ${c.por_confirmar} datos que faltan`} para saber si encaja del todo.</p>
        )}
        {question && (
          <div className="notice notice-warning">
            <p><strong>{c.por_confirmar > 1 ? `Faltan ${c.por_confirmar} datos` : 'Falta 1 dato'}</strong></p>
            <p>{question}</p>
            <div className="chips">
              {quickRepliesFor(question).slice(0, 4).map((chip) => (
                <button key={chip.label} type="button" className="chip" onClick={() => onQuickReply(chip, question)}>{chip.label}</button>
              ))}
            </div>
          </div>
        )}
      </section>

      <section>
        <Facts aid={aid} />
        <h3>Documentación</h3>
        {aid.documentacion.length
          ? <><p className="support">Según la ficha oficial:</p><ul>{aid.documentacion.map((d) => <li key={d}>{d}</li>)}</ul></>
          : <p className="support">La ficha no detalla la documentación. Pregunta en tu oficina comarcal.</p>}
        {aid.pasos.length > 0 && <><h3>Cómo se pide</h3><p>{aid.pasos.length === 1 ? aid.pasos[0] : `En ${aid.pasos.length} pasos. Ábrelos en «Ver cómo solicitarla».`}</p></>}
      </section>

      <div className="btn-row">
        <button type="button" className="btn" onClick={() => onGuide(aid.id)}>Ver cómo solicitarla</button>
        <button type="button" className="btn btn-secondary" onClick={() => onAlternatives(aid.id)}>Ver alternativas</button>
        <button type="button" className="btn btn-ghost" onClick={() => onAsk(`Tengo una duda sobre la ayuda «${aid.nombre}».`)}>Preguntar una duda</button>
      </div>

      <section>
        <h3>Fuentes oficiales</h3>
        <SourceLine aid={aid} />
        <p className="support">{RELIABILITY[aid.fiabilidad].help}</p>
        {aid.notas && <p className="support">{aid.notas}</p>}
      </section>
      <HowWeChecked trace={trace} aid={aid} />
    </article>
  );
}

export function ApplicationGuide({ aid, status, trace, onBack, onAsk }) {
  const h = useFocusHeading(aid?.id);
  if (!aid) return <div className="detail"><Back onClick={onBack}>Volver al detalle</Back><p>No hemos encontrado esa ayuda.</p></div>;
  const steps = aid.pasos;
  return (
    <article className="detail card">
      <Back onClick={onBack}>Volver al detalle</Back>
      <LoadingNote status={status} />
      {aid.es_ejemplo && <ExampleBadge />}
      <h2 ref={h} tabIndex={-1}>Cómo solicitar: {aid.nombre}</h2>
      <ReliabilityBadge value={aid.fiabilidad} />
      {aid.fiabilidad !== 'verificada' && <p className="notice notice-warning">Algunos pasos pueden estar por confirmar: la ficha no siempre los detalla.</p>}
      <dl className="facts">
        <div className="fact"><dt>Plazo</dt>{aid.plazo ? <dd>{aid.plazo}</dd> : <dd className="unverified">Sin dato verificado · consulta la fuente oficial</dd>}</div>
        <div className="fact"><dt>Quién la tramita</dt><dd>{aid.organismo ?? 'Por confirmar'}</dd></div>
      </dl>

      {steps.length > 0 ? (
        <ol className="guide-steps">
          {steps.map((s, i) => <li key={i}><p className="support">Según la ficha oficial</p><p>{s}</p></li>)}
        </ol>
      ) : (
        <div className="notice notice-info">
          <p>La ficha que tenemos no detalla los pasos. Puedo pedirle al asistente que te explique lo que se sabe.</p>
          <button type="button" className="btn" onClick={() => onAsk(`¿Cómo solicito la ayuda «${aid.nombre}»?`)}>Preguntar cómo solicitarla</button>
        </div>
      )}

      {aid.documentacion.length > 0 && <><h3>Documentos</h3><ul>{aid.documentacion.map((d) => <li key={d}>{d}</li>)}</ul></>}

      <p className="notice notice-disclaimer">Antes de presentar nada, confirma condiciones y plazos en la ficha oficial o en tu oficina comarcal.</p>
      <div className="btn-row">
        {aid.url_fuente && <a className="btn" href={aid.url_fuente} target="_blank" rel="noopener noreferrer">Abrir la ficha oficial ↗</a>}
        <button type="button" className="btn btn-secondary" onClick={() => onAsk(`Tengo una duda sobre cómo solicitar «${aid.nombre}».`)}>Preguntar una duda</button>
      </div>
      <HowWeChecked trace={trace} aid={aid} />
    </article>
  );
}

export function Alternatives({ aid, alternatives, status, onBack, onOpen, onAsk }) {
  const h = useFocusHeading(aid?.id);
  if (!aid) return <div className="detail"><Back onClick={onBack}>Volver a resultados</Back><p>No hemos encontrado esa ayuda.</p></div>;
  const failed = aid.requisitos.filter((r) => r.estado === 'no_cumple');
  return (
    <article className="detail card">
      <Back onClick={onBack}>Volver a resultados</Back>
      <div className="badges"><EligibilityBadge value={aid.resultado} />{aid.es_ejemplo && <ExampleBadge />}</div>
      <h2 ref={h} tabIndex={-1}>{aid.nombre}</h2>
      {failed.length > 0 && <p><strong>Lo que no encaja:</strong> {failed.map((r) => r.descripcion).join('; ')}. Según tus datos, no se cumple.</p>}
      {aid.cambio_sugerido && <p><strong>Qué lo cambiaría:</strong> {aid.cambio_sugerido}</p>}

      <h3>Ayudas que pueden encajarte mejor</h3>
      {status === 'loading' && <p className="support" role="status">Buscando alternativas…</p>}
      {status !== 'loading' && alternatives.length === 0 && (
        <div className="notice notice-info">
          <p>No tenemos alternativas guardadas para esta ayuda. Puedo pedirle al asistente que busque otras que encajen con tu explotación.</p>
          <button type="button" className="btn" onClick={() => onAsk(`No cumplo «${aid.nombre}». ¿Qué alternativas tengo?`)}>Buscar alternativas</button>
        </div>
      )}
      {alternatives.map((a) => (
        <div key={a.id} className="card aid-card">
          <div className="badges"><EligibilityBadge value={a.resultado} />{a.es_ejemplo && <ExampleBadge />}</div>
          <h4>{a.nombre}</h4>
          <p>{a.cambio_sugerido ? `Por qué puede ir mejor: ${a.cambio_sugerido}` : shortReason(a)}</p>
          <div className="badges"><ReliabilityBadge value={a.fiabilidad} /></div>
          <div className="btn-row"><button type="button" className="btn btn-secondary" onClick={() => onOpen(a.id)}>Ver detalle</button></div>
        </div>
      ))}
      {alternatives.length > 1 && (
        <div className="btn-row">
          <button type="button" className="btn btn-ghost" onClick={() => onAsk(`Explícame la diferencia entre ${alternatives.map((a) => `«${a.nombre}»`).join(' y ')}.`)}>¿Te explico la diferencia entre estas ayudas?</button>
        </div>
      )}
    </article>
  );
}
