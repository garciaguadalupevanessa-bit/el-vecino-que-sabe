import { useEffect, useState } from "react";
import { fetchReviewCoverage, ReviewApiError } from "../lib/reviewApi.js";

const ACTIVITY_NAMES = {
  agriculture: "Agricultura",
  livestock: "Ganadería",
  mixed: "Mixta",
  unclassified: "Sin clasificar",
  unknown: "Sin asignar",
};
const TERRITORY_STATUS = {
  not_checked: "Sin consultar",
  indexed_in_bounded_query: "Registros indexados en consulta limitada",
  candidates_not_indexed: "Candidatas sin indexar",
  no_candidates_in_bounded_query: "Sin resultados en consulta limitada",
};
const CATEGORY_NAMES = {
  pac_direct: "PAC directa", pac_coupled: "Pagos asociados", young_farmer_startup: "Incorporación de jóvenes",
  farm_modernisation: "Modernización", agro_environment_organic: "Agroambiental/ecológica",
  agricultural_insurance: "Seguro agrario", animal_health: "Sanidad animal", extensive_livestock: "Ganadería extensiva",
  native_breeds: "Razas autóctonas", investment: "Inversión", emergency_aid: "Ayuda de emergencia",
};

function Metric({ label, value }) {
  return <div className="coverage-metric"><span>{label}</span><strong>{value}</strong></div>;
}

export default function CoverageReport({ token }) {
  const [report, setReport] = useState(null);
  const [classificationRegionId, setClassificationRegionId] = useState("21");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      setReport(await fetchReviewCoverage(token));
    } catch (caught) {
      setError(caught instanceof ReviewApiError ? caught.message : "No se pudo cargar el informe de cobertura.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, [token]);

  if (loading && !report) return <p className="help" role="status">Cargando cobertura…</p>;
  if (error && !report) return <p className="review-error" role="alert">{error}</p>;
  if (!report) return null;

  const lastRun = report.last_import_run;
  const unqueried = report.gaps?.territories_not_checked || [];
  const noMatches = report.gaps?.territories_without_candidates_in_latest_bounded_query || [];
  const campaignGaps = report.gaps?.unclassified_campaign_calls || 0;
  const classificationGaps = report.classification_gaps || [];
  const classificationRegions = [...new Map(classificationGaps.map((item) => [item.region_id, item.territory])).entries()]
    .map(([region_id, territory]) => ({ region_id, territory }));
  const activeClassificationRegion = classificationRegions.find((item) => String(item.region_id) === classificationRegionId)
    || classificationRegions.find((item) => item.region_id === 21)
    || classificationRegions[0];
  const activeClassificationRows = activeClassificationRegion
    ? classificationGaps.filter((item) => item.region_id === activeClassificationRegion.region_id)
    : [];

  return (
    <section className="coverage-report" aria-label="Cobertura de importación BDNS">
      <div className="coverage-heading">
        <div><h2>Seguimiento de cobertura BDNS</h2><p>Estado del índice y de las consultas registradas.</p></div>
        <button className="secondary" onClick={refresh} disabled={loading}>{loading ? "Actualizando…" : "Actualizar"}</button>
      </div>
      {error && <p className="review-error" role="alert">{error}</p>}
      <p className="review-warning" role="note">Una consulta limitada sin resultados no demuestra que no existan ayudas. La clasificación de actividad, categoría y campaña depende de datos de origen o revisión; no se deduce solo por el título.</p>

      <div className="coverage-metrics">
        <Metric label="Convocatorias indexadas" value={report.indexed_call_count ?? 0} />
        <Metric label="Territorios BDNS sin consultar" value={unqueried.length} />
        <Metric label="Convocatorias con actividad sin clasificar" value={report.gaps?.unclassified_farm_activity_calls ?? 0} />
        <Metric label="Aptas para extracción sin clasificación confirmada" value={report.gaps?.accepted_candidates_without_current_classification ?? 0} />
        <Metric label="Convocatorias con campaña sin clasificar" value={campaignGaps} />
      </div>

      <section className="panel coverage-section">
        <h3>Última importación</h3>
        {lastRun ? <>
          <p>Inicio: {new Date(lastRun.started_at).toLocaleString("es-ES")} · Estado: {lastRun.status} · {lastRun.indexed_call_count} convocatorias indexadas · {lastRun.max_pages} páginas como máximo, {lastRun.page_size} por página.</p>
          <p>Territorios solicitados: {(lastRun.region_ids || []).join(", ") || "Ninguno"} · Términos: {(lastRun.search_terms || []).join(", ") || "Ninguno"}</p>
          {lastRun.error_summary && <p className="review-error">{lastRun.error_summary}</p>}
          {lastRun.queries?.length ? <div className="coverage-table-wrap"><table className="coverage-table">
            <thead><tr><th>Territorio</th><th>Término de búsqueda</th><th>Ámbito del término</th><th>Candidatas</th><th>Indexadas</th><th>Límite alcanzado</th></tr></thead>
            <tbody>{lastRun.queries.map((query) => <tr key={`${query.region_id}-${query.search_term}`}>
              <td>{query.territory}</td><td>{query.search_term}</td><td>{ACTIVITY_NAMES[query.activity_scope] || query.activity_scope}</td>
              <td>{query.candidate_count}</td><td>{query.indexed_call_count}</td><td>{query.page_limit_reached ? "Sí; puede estar truncada" : "No detectado"}</td>
            </tr>)}</tbody>
          </table></div> : <p>No hay consultas registradas para esta importación.</p>}
        </> : <p>Aún no hay importaciones registradas con seguimiento de cobertura.</p>}
      </section>

      <section className="panel coverage-section">
        <h3>Territorios del catálogo BDNS</h3>
        {unqueried.length > 0 && <p><strong>Pendientes de consultar:</strong> {unqueried.join(", ")}</p>}
        {noMatches.length > 0 && <p><strong>Sin candidatas en la última consulta limitada:</strong> {noMatches.join(", ")}</p>}
        <div className="coverage-table-wrap"><table className="coverage-table">
          <thead><tr><th>Territorio</th><th>Código NUTS</th><th>Estado</th><th>Candidatas última consulta</th><th>Indexadas</th></tr></thead>
          <tbody>{(report.territories || []).map((region) => <tr key={region.region_id}>
            <td>{"  ".repeat(region.depth || 0)}{region.territory}</td><td>{region.nuts_code || "—"}</td>
            <td>{TERRITORY_STATUS[region.status] || region.status}</td><td>{region.last_candidate_count}</td><td>{region.last_indexed_call_count}</td>
          </tr>)}</tbody>
        </table></div>
      </section>

      <section className="coverage-grid">
        <div className="panel coverage-section"><h3>Actividad agraria</h3><ul>{(report.activities || []).map((item) => <li key={item.activity}>{ACTIVITY_NAMES[item.activity] || item.activity}: {item.indexed_call_count} indexadas</li>)}</ul></div>
        <div className="panel coverage-section"><h3>Campañas</h3><ul>{(report.campaigns || []).map((item) => <li key={`${item.year}-${item.label}`}>{item.year}{item.label ? ` · ${item.label}` : ""}: {item.indexed_call_count} convocatorias</li>)}</ul></div>
      </section>

      <section className="panel coverage-section"><h3>Categorías y finalidad según BDNS</h3>
        <p>Son etiquetas originales de la fuente; todavía no equivalen a una clasificación normalizada de ayudas agrarias.</p>
        {report.gaps?.controlled_aid_category_mapping === "not_implemented" && <p className="coverage-gap">Las etiquetas originales y las sugerencias automáticas no sustituyen una clasificación confirmada; las asignaciones revisadas se muestran abajo.</p>}
        <h4>Finalidad</h4><ul>{(report.source_categories?.purposes || []).map((item) => <li key={item.label}>{item.label}: {item.indexed_call_count}</li>)}</ul>
        <h4>Sectores económicos</h4><ul>{(report.source_categories?.economic_sectors || []).map((item) => <li key={item.label}>{item.label}: {item.indexed_call_count}</li>)}</ul>
        <h4>Personas beneficiarias</h4><ul>{(report.source_categories?.beneficiary_categories || []).map((item) => <li key={item.label}>{item.label}: {item.indexed_call_count}</li>)}</ul>
        <h4>Sectores de productos</h4><ul>{(report.source_categories?.product_sectors || []).map((item) => <li key={item.label}>{item.label}: {item.indexed_call_count}</li>)}</ul>
      </section>

      <section className="panel coverage-section"><h3>Clasificaciones confirmadas por revisión</h3>
        <p>Incluye solo clasificaciones vigentes con cita oficial. Una convocatoria con varias categorías aparece en cada combinación correspondiente; esto no equivale a verificar elegibilidad.</p>
        {report.confirmed_classifications?.length ? <div className="coverage-table-wrap"><table className="coverage-table">
          <thead><tr><th>Territorio consultado</th><th>Actividad</th><th>Categoría</th><th>Campaña</th><th>Convocatorias</th></tr></thead>
          <tbody>{report.confirmed_classifications.map((item) => <tr key={`${item.region_id}-${item.activity}-${item.category}-${item.campaign_year}-${item.campaign_label}`}>
            <td>{item.territory}</td><td>{ACTIVITY_NAMES[item.activity] || item.activity}</td><td>{CATEGORY_NAMES[item.category] || item.category}</td>
            <td>{item.campaign_year || "Sin clasificar"}{item.campaign_label ? ` · ${item.campaign_label}` : ""}</td><td>{item.call_count}</td>
          </tr>)}</tbody>
        </table></div> : <p>Aún no hay clasificaciones confirmadas con cita.</p>}
      </section>

      <section className="panel coverage-section"><h3>Actividad y categorías pendientes de clasificar</h3>
        <p>Una fila pendiente indica que no hay una clasificación confirmada con cita para esa combinación. No significa que no existan ayudas. El territorio es el ámbito de la consulta BDNS.</p>
        {classificationRegions.length ? <>
          <label htmlFor="classification-coverage-region">Territorio consultado</label>
          <select id="classification-coverage-region" value={activeClassificationRegion?.region_id ?? ""} onChange={(event) => setClassificationRegionId(event.target.value)}>
            {classificationRegions.map((region) => <option key={region.region_id} value={region.region_id}>{region.territory}</option>)}
          </select>
          {activeClassificationRows[0]?.last_run_id && <p>Última consulta registrada: run {activeClassificationRows[0].last_run_id}.</p>}
          <div className="coverage-table-wrap"><table className="coverage-table">
            <thead><tr><th>Actividad</th><th>Categoría prioritaria</th><th>Convocatorias clasificadas</th><th>Campaña sin clasificar</th><th>Estado</th></tr></thead>
            <tbody>{activeClassificationRows.map((item) => <tr key={`${item.activity}-${item.category}`}>
              <td>{ACTIVITY_NAMES[item.activity] || item.activity}</td><td>{CATEGORY_NAMES[item.category] || item.category}</td>
              <td>{item.classified_call_count}</td><td>{item.campaign_unclassified_count}</td>
              <td>{item.status === "classified" ? "Clasificación confirmada" : "Pendiente de clasificación"}</td>
            </tr>)}</tbody>
          </table></div>
        </> : <p>Aún no hay consultas territoriales que mostrar.</p>}
      </section>
    </section>
  );
}
