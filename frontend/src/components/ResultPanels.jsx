import { safeUrl } from "../lib/url.js";

const ELIGIBILITY = {
  met: { text: "Cumple las condiciones comprobadas", cls: "ok", icon: "✅" },
  unknown: { text: "Falta información o confirmar la fuente", cls: "warn", icon: "⚠️" },
  not_met: { text: "No cumple una condición comprobada", cls: "bad", icon: "❌" },
};
const REQUIREMENT = {
  met: { text: "Cumple", cls: "ok" },
  unknown: { text: "Por confirmar", cls: "warn" },
  not_met: { text: "No cumple", cls: "bad" },
};
const RELIABILITY = {
  verified: "Revisada con fuente oficial",
  extracted: "Datos extraídos; pendientes de revisión",
  metadata_only: "Ficha básica; requisitos no comprobados",
};
const AID_STATUS = {
  active: "Activa según la ficha",
  upcoming: "Próxima según la ficha",
  closed: "Cerrada según la ficha",
  withdrawn: "Retirada según la ficha",
  unknown: "Estado no indicado",
};
const TOOL_LABELS = {
  search_aids: ["Búsqueda", "He buscado en el catálogo con los datos disponibles."],
  check_eligibility: ["Revisión de requisitos", "He comparado el perfil con las condiciones registradas."],
  get_application_guide: ["Guía de solicitud", "He consultado los pasos que constan como revisados."],
  find_alternatives: ["Alternativas", "He comprobado si el catálogo contiene otras ayudas relacionadas."],
};

function Panel({ title, open = false, emptyText, items, children }) {
  return (
    <details className="results" open={open}>
      <summary>{title}</summary>
      {items.length === 0 ? <div className="empty">{emptyText}</div> : <ul className="list">{children}</ul>}
    </details>
  );
}

function locations(aid) {
  const names = (aid.territories || []).map((item) => typeof item === "string" ? item : item?.name).filter(Boolean);
  if (names.length) return names.join(", ");
  if (aid.scope === "national") return "Ámbito nacional";
  return aid.scope || "No indicado";
}

function campaignLine(values) {
  return values?.length ? values.join(", ") : "No indicada en la ficha";
}

function AidItem({ aid }) {
  const result = aid.overall_result ? ELIGIBILITY[aid.overall_result] : null;
  const href = safeUrl(aid.source_url);
  return (
    <li className="item aid-result">
      <strong>{aid.name ?? "Ayuda"}</strong>
      <div className="aid-badges">
        {result ? <span className={`badge ${result.cls}`}>{result.icon} {result.text}</span> :
          <span className="badge warn">ℹ️ Requisitos aún no evaluados</span>}
        {aid.reliability && <span className="reliability-label">{aid.reliability === "verified" && aid.verification_method === "agent" ? "Verificada automáticamente con agente y fuente oficial" : RELIABILITY[aid.reliability] ?? "Fiabilidad no indicada"}</span>}
      </div>
      <dl className="aid-facts">
        <div><dt>Territorio</dt><dd>{locations(aid)}</dd></div>
        <div><dt>Campaña</dt><dd>{campaignLine(aid.campaigns)}</dd></div>
        <div><dt>Estado registrado</dt><dd>{AID_STATUS[aid.status] ?? "Estado no indicado"}</dd></div>
        {aid.last_checked_on && <div><dt>Última comprobación registrada</dt><dd>{aid.last_checked_on}</dd></div>}
      </dl>
      {href && <a href={href} target="_blank" rel="noopener noreferrer">
        {aid.reliability === "verified" ? "Consultar fuente oficial verificada" : "Abrir enlace registrado (sin verificar)"}
      </a>}
      {aid.requirements?.length > 0 && (
        <ul className="requirement-list" aria-label="Condiciones revisadas">
          {aid.requirements.map((requirement, index) => {
            const status = REQUIREMENT[requirement.status] ?? REQUIREMENT.unknown;
            return (
              <li key={`${requirement.description ?? "condicion"}-${index}`}>
                <span className={`requirement-status ${status.cls}`}>{status.text}</span>
                <span>{requirement.description || "Condición de la ayuda"}</span>
                {requirement.explanation_es && <small>{requirement.explanation_es}</small>}
              </li>
            );
          })}
        </ul>
      )}
    </li>
  );
}

export default function ResultPanels({ aids, sources, trace, coverage_notes = [] }) {
  return (
    <>
      {coverage_notes.length > 0 && (
        <Panel title="Alcance de la búsqueda" open emptyText="" items={coverage_notes}>
          {coverage_notes.map((note, index) => (
            <li className="item coverage-note" key={`${note.message}-${index}`}>{note.message}</li>
          ))}
        </Panel>
      )}

      <Panel title="Ayudas consultadas" open emptyText="Aún no se han consultado ayudas." items={aids}>
        {aids.map((aid) => <AidItem key={aid.id} aid={aid} />)}
      </Panel>

      <Panel title="Fuentes y enlaces registrados" open emptyText="Las fuentes aparecerán aquí." items={sources}>
        {sources.map((source) => {
          const href = safeUrl(source.url);
          return (
            <li key={source.url} className="item">
              {href ? <a href={href} target="_blank" rel="noopener noreferrer">{source.name ?? "Abrir enlace registrado"}</a> :
                <span>Fuente sin enlace válido</span>}
              {source.reliability && <div className="meta">{RELIABILITY[source.reliability] ?? "Fiabilidad no indicada"}</div>}
              {source.campaigns?.length > 0 && <div className="meta">Campaña: {campaignLine(source.campaigns)}</div>}
              {source.territories?.length > 0 && <div className="meta">Territorio: {source.territories.join(", ")}</div>}
              {source.last_checked_on && <div className="meta">Última comprobación registrada: {source.last_checked_on}</div>}
            </li>
          );
        })}
      </Panel>

      <Panel title="Comprobaciones realizadas" emptyText="Aquí aparecerán las consultas realizadas." items={trace}>
        {trace.map((item, index) => {
          const [title, description] = TOOL_LABELS[item.tool] ?? ["Consulta", "Se ha revisado la información disponible."];
          return (
            <li key={`${item.tool}-${index}`} className="item">
              <strong>{title}</strong>
              <span className="meta">{item.ok ? " · completada" : " · no completada"}</span>
              <p className="meta">{description}</p>
            </li>
          );
        })}
      </Panel>
    </>
  );
}
