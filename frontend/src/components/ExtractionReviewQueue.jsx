import { useEffect, useState } from "react";
import { downloadExtractionDocument, fetchExtractionReviewQueue, processSimpleExtractionTasks, ReviewApiError, saveExtractionReviewDecision } from "../lib/reviewApi.js";

const TYPE_LABELS = {
  missing_data: "Dato ausente",
  ambiguous_data: "Dato ambiguo",
  conflicting_data: "Datos en conflicto",
  quality_finding: "Control de calidad",
  source_changed: "Fuente modificada",
};

function Citation({ citation, documentId, token, bdnsCode }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  if (!citation) return null;
  async function download() {
    setDownloading(true);
    setError("");
    try { await downloadExtractionDocument(token, bdnsCode, documentId); }
    catch (caught) { setError(caught.message || "No se pudo descargar el documento."); }
    finally { setDownloading(false); }
  }
  return <small className="extraction-citation">
    {citation.page && documentId
      ? <button type="button" className="citation-download" disabled={downloading} onClick={download}>{downloading ? "Descargando…" : "Descargar documento oficial (.pdf)"}</button>
      : citation.url && <a href={citation.url} target="_blank" rel="noreferrer noopener">Abrir ficha oficial</a>}
    {citation.page ? ` · página ${citation.page}` : ""}{citation.section ? ` · ${citation.section}` : ""}
    {error && <span className="review-error" role="alert"> {error}</span>}
  </small>;
}

function TaskCard({ item, token, reviewer, onSaved }) {
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const candidates = item.details?.candidates || [];
  async function decide(decision) {
    setBusy(true); setError("");
    try {
      const result = await saveExtractionReviewDecision(token, item.task_id, {
        expected_payload_sha256: item.payload_sha256,
        expected_extraction_fingerprint: item.extraction_fingerprint || "",
        reviewer: reviewer.trim(), decision, notes: notes.trim(),
      });
      await onSaved(result.message);
    } catch (caught) {
      setError(caught instanceof ReviewApiError ? caught.message : "No se pudo guardar la revisión.");
    } finally { setBusy(false); }
  }
  return <article className="review-card">
    <div className="review-card-title"><div><p className="review-kicker">BDNS {item.bdns_code} · {TYPE_LABELS[item.issue_type] || item.issue_type}</p>
      <h2>{item.title || "Convocatoria sin título"}</h2></div><span className="review-status attention">{item.field || "Revisar"}</span></div>
    <p>{item.summary}</p>
    {item.detail_url && <p><a href={item.detail_url} target="_blank" rel="noreferrer noopener">Abrir ficha oficial BDNS</a></p>}
    {candidates.length > 0 && <div className="extraction-candidates"><strong>Textos candidatos encontrados</strong><ul>
      {candidates.map((candidate, index) => <li key={`${index}-${candidate.value}`}><p>{candidate.value}</p><Citation citation={candidate.citation} documentId={candidate.document_id} token={token} bdnsCode={item.bdns_code} /></li>)}
    </ul>{item.details?.truncated && <small>Se muestran solo algunos candidatos.</small>}</div>}
    {item.details?.finding?.details && <details><summary>Detalles del control automático</summary><pre>{JSON.stringify(item.details.finding.details, null, 2)}</pre></details>}
    <p className="extraction-reliability">Estado: {item.reliability === "extracted" ? "información extraída, pendiente de verificar" : "solo metadatos"}.</p>
    <label htmlFor={`extraction-note-${item.task_id}`}>Notas de revisión</label>
    <textarea id={`extraction-note-${item.task_id}`} value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={2000} rows={2} placeholder="Indica qué fuente o dato has revisado." />
    {error && <p role="alert" className="review-error">{error}</p>}
    <div className="review-actions">
      <button disabled={busy || !reviewer.trim() || !notes.trim()} onClick={() => decide("reviewed_candidate")}>{busy ? "Guardando…" : "Revisada como candidata"}</button>
      <button className="secondary" disabled={busy || !reviewer.trim() || !notes.trim()} onClick={() => decide("needs_correction")}>Necesita corrección</button>
    </div>
  </article>;
}

export default function ExtractionReviewQueue({ token, reviewer }) {
  const [status, setStatus] = useState("open");
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [agentLoading, setAgentLoading] = useState(false);
  async function load(nextStatus = status) {
    setLoading(true); setError("");
    try { const result = await fetchExtractionReviewQueue(token, nextStatus); setItems(result.items || []); setTotal(result.total || 0); }
    catch (caught) { setItems([]); setError(caught.message || "No se pudo cargar la bandeja."); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [token, status]);
  async function onSaved(message) { setNotice(message); await load(); }
  async function processSimpleTasks() {
    setAgentLoading(true); setError(""); setNotice("");
    try {
      const result = await processSimpleExtractionTasks(token);
      setNotice(`Agente: ${result.processed} tareas sencillas revisadas con cita; ${result.left_for_human} quedan para revisión humana.`);
      await load();
    } catch (caught) { setError(caught instanceof ReviewApiError ? caught.message : "No se pudieron procesar las tareas."); }
    finally { setAgentLoading(false); }
  }
  return <section className="extraction-review">
    <div className="panel extraction-toolbar"><div><h2>Revisión de extracciones</h2><p className="help">Los candidatos revisados siguen siendo información extraída. Esta decisión no verifica requisitos ni elegibilidad.</p></div>
      <label>Mostrar <select value={status} onChange={(event) => setStatus(event.target.value)}><option value="open">Pendientes</option><option value="needs_correction">Necesitan corrección</option><option value="reviewed_candidate">Revisadas</option><option value="all">Todas</option></select></label>
      {status === "open" && <button onClick={processSimpleTasks} disabled={loading || agentLoading}>{agentLoading ? "Revisando tareas…" : "Revisar automáticamente las tareas claras"}</button>}
      <button className="secondary" disabled={loading} onClick={() => load()}>{loading ? "Actualizando…" : "Actualizar"}</button>
    </div>
    {notice && <p className="review-success" role="status">{notice}</p>}{error && <p className="review-error" role="alert">{error}</p>}
    {loading ? <p className="help">Cargando tareas…</p> : items.length ? <div className="review-list">{items.map((item) => <TaskCard key={item.task_id} item={item} token={token} reviewer={reviewer} onSaved={onSaved} />)}</div> : <p className="panel review-empty">No hay tareas en este filtro ({total}).</p>}
  </section>;
}
