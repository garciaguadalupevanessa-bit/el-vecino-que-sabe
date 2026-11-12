import { useEffect, useState } from "react";
import { fetchReviewFilterOptions, fetchReviewQueue, finalizeWithAI, processAIReviewQueue, requestAIReview, ReviewApiError, saveReviewClassification, saveReviewDecision } from "../lib/reviewApi.js";
import CoverageReport from "./CoverageReport.jsx";
import ExtractionReviewQueue from "./ExtractionReviewQueue.jsx";

const PAGE_SIZE = 50;

const STATUS_LABELS = {
  pending_review: "Pendiente de revisión",
  review_required: "Revisión necesaria por cambios",
  accepted_for_extraction: "Revisada para extracción",
  out_of_scope: "Fuera de alcance",
  reviewed: "Revisada",
};
const RELIABILITY_LABELS = {
  metadata_only: "Solo metadatos",
  extracted: "Información extraída, pendiente de verificar",
  verified: "Verificada",
};
const ACTIVITY_LABELS = {
  agriculture: "Agricultura",
  livestock: "Ganadería",
  mixed: "Agricultura y ganadería",
  unclassified: "Sin clasificar",
  out_of_scope: "Fuera de alcance",
};
const CATEGORY_LABELS = {
  pac_direct: "PAC directa",
  pac_coupled: "Pagos asociados",
  young_farmer_startup: "Incorporación de jóvenes",
  farm_modernisation: "Modernización",
  agro_environment_organic: "Agroambiental/ecológica",
  agricultural_insurance: "Seguro agrario",
  animal_health: "Sanidad animal",
  extensive_livestock: "Ganadería extensiva",
  native_breeds: "Razas autóctonas",
  investment: "Inversión",
  emergency_aid: "Ayuda de emergencia",
};
const TRIAGE_LABELS = {
  prioritize: "Priorizar revisión",
  check_beneficiaries: "Comprobar beneficiarios",
  low_signal: "Pocas señales agrarias en metadatos",
};
const AI_RELEVANCE_LABELS = {
  prioritize: "Parece prioritaria",
  check_beneficiaries: "Comprobar quién puede recibirla",
  low_signal: "Pocas señales agrarias",
  insufficient_evidence: "Faltan pruebas para orientarse",
};
const AI_CONFIDENCE_LABELS = { low: "baja", medium: "media", high: "alta" };
const CATEGORIES = Object.keys(CATEGORY_LABELS);
const ACTIVITIES = ["agriculture", "livestock", "mixed"];

function SourceLink({ href, children }) {
  if (!href) return null;
  return <a href={href} target="_blank" rel="noreferrer noopener">{children || href}</a>;
}

function ClassificationEditor({ item, reviewer, token, onSaved, aiPreReview }) {
  const triage = item.automated_triage || {};
  const ai = aiPreReview?.result || {};
  const current = item.confirmed_classification?.is_active ? item.confirmed_classification : null;
  const [categories, setCategories] = useState(() => current?.categories || ai.categories?.map((item) => item.value) || (triage.category_suggestions || []).map((suggestion) => suggestion.category));
  const [activities, setActivities] = useState(() => current?.activities || ai.activities?.map((item) => item.value) || Object.keys(triage.activity_suggestions || {}));
  const aiCampaignYear = ai.campaign_year;
  const suggestedCampaignYear = aiCampaignYear || triage.campaign_suggestion?.year;
  const [campaignYear, setCampaignYear] = useState(() => current?.campaign_year || suggestedCampaignYear || "");
  const [campaignLabel, setCampaignLabel] = useState(() => current?.campaign_label || "");
  const [sourceUrl, setSourceUrl] = useState(() => current?.evidence?.[0]?.source_url || item.sources?.regulatory_bases?.url || item.detail_url || "");
  const [evidenceLocator, setEvidenceLocator] = useState(() => current?.evidence?.[0]?.locator || "");
  const [evidenceQuote, setEvidenceQuote] = useState(() => current?.evidence?.[0]?.quote || "");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const suggestedCategories = new Set((triage.category_suggestions || []).map((suggestion) => suggestion.category));
  const suggestedActivities = new Set(Object.keys(triage.activity_suggestions || {}));
  for (const suggestion of ai.categories || []) suggestedCategories.add(suggestion.value);
  for (const suggestion of ai.activities || []) suggestedActivities.add(suggestion.value);
  const requiresManualEvidence = categories.some((category) => !suggestedCategories.has(category))
    || activities.some((activity) => !suggestedActivities.has(activity))
    || Boolean(campaignLabel.trim())
    || (campaignYear && Number(campaignYear) !== suggestedCampaignYear);
  const hasManualEvidence = Boolean(evidenceLocator.trim() && evidenceQuote.trim() && sourceUrl.trim());
  const missingRequirements = [
    !reviewer.trim() && "escribe tu nombre en el campo superior",
    !categories.length && "selecciona al menos una categoría",
    !activities.length && "selecciona al menos una actividad",
    !notes.trim() && "completa Notas de clasificación",
    !buildEvidence().length && "añade una cita que respalde la clasificación",
    requiresManualEvidence && !hasManualEvidence && "completa URL oficial, localizador y texto citado",
  ].filter(Boolean);

  useEffect(() => {
    if (current || !aiPreReview?.suggestion_id) return;
    const result = aiPreReview.result || {};
    setCategories((result.categories || []).map((entry) => entry.value));
    setActivities((result.activities || []).map((entry) => entry.value));
    setCampaignYear(result.campaign_year || "");
  }, [aiPreReview?.suggestion_id]);

  function toggle(setter, currentValues, value) {
    setter(currentValues.includes(value) ? currentValues.filter((itemValue) => itemValue !== value) : [...currentValues, value]);
  }

  function toggleActivity(activity) {
    setActivities((currentValues) => {
      if (currentValues.includes(activity)) return currentValues.filter((itemValue) => itemValue !== activity);
      if (activity === "mixed") return ["mixed"];
      return [...currentValues.filter((itemValue) => itemValue !== "mixed"), activity];
    });
  }

  function buildEvidence() {
    const evidence = [];
    for (const suggestion of triage.category_suggestions || []) {
      if (!categories.includes(suggestion.category)) continue;
      for (const itemEvidence of suggestion.evidence || []) {
        evidence.push({ source_url: item.detail_url, locator: itemEvidence.field, quote: itemEvidence.value });
      }
    }
    for (const activity of activities) {
      for (const itemEvidence of triage.activity_suggestions?.[activity] || []) {
        evidence.push({ source_url: item.detail_url, locator: itemEvidence.field, quote: itemEvidence.value });
      }
    }
    if (campaignYear && Number(campaignYear) === triage.campaign_suggestion?.year) {
      evidence.push({ source_url: item.detail_url, locator: "call.title", quote: item.title || `Campaña ${campaignYear}` });
    }
    const aiEvidence = new Map((ai.evidence || []).map((candidate) => [candidate.id, candidate]));
    for (const suggestion of [...(ai.categories || []), ...(ai.activities || [])]) {
      if (!categories.includes(suggestion.value) && !activities.includes(suggestion.value)) continue;
      for (const evidenceId of suggestion.evidence_ids || []) {
        const candidate = aiEvidence.get(evidenceId);
        if (candidate) evidence.push({
          source_url: candidate.source_url, locator: candidate.locator, quote: candidate.quote,
        });
      }
    }
    if (campaignYear && Number(campaignYear) === aiCampaignYear) {
      for (const evidenceId of ai.campaign_evidence_ids || []) {
        const candidate = aiEvidence.get(evidenceId);
        if (candidate) evidence.push({
          source_url: candidate.source_url, locator: candidate.locator, quote: candidate.quote,
        });
      }
    }
    if (evidenceQuote.trim() && evidenceLocator.trim() && sourceUrl.trim()) {
      evidence.push({ source_url: sourceUrl.trim(), locator: evidenceLocator.trim(), quote: evidenceQuote.trim() });
    }
    const unique = new Map();
    for (const itemEvidence of evidence) {
      if (!itemEvidence.source_url || !itemEvidence.locator || !itemEvidence.quote) continue;
      unique.set(`${itemEvidence.source_url}|${itemEvidence.locator}|${itemEvidence.quote}`, itemEvidence);
    }
    return [...unique.values()].slice(0, 30);
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      const result = await saveReviewClassification(token, item.bdns_code, {
        expected_payload_sha256: item.payload_sha256,
        reviewer: reviewer.trim(),
        categories,
        activities,
        campaign_year: campaignYear ? Number(campaignYear) : null,
        campaign_label: campaignLabel.trim() || null,
        evidence: buildEvidence(),
        notes: notes.trim(),
      });
      await onSaved(result.message);
    } catch (caught) {
      setError(caught instanceof ReviewApiError ? caught.message : "No se pudo guardar la clasificación.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="classification-editor" aria-label="Confirmar clasificación de ayuda">
      {item.confirmed_classification && !item.confirmed_classification.is_active && <p className="review-warning">{item.confirmed_classification.is_current ? "La convocatoria ya no está aceptada para extracción; esta clasificación no cuenta para cobertura." : "La fuente cambió desde la clasificación anterior. Confirma la clasificación de nuevo."}</p>}
      {current && <div className="classification-current"><strong>Clasificación confirmada</strong>
        <p>{current.categories.map((category) => CATEGORY_LABELS[category] || category).join(", ")} · {current.activities.map((activity) => ACTIVITY_LABELS[activity] || activity).join(", ")}{current.campaign_year ? ` · campaña ${current.campaign_year}` : ""}</p>
        <p className="help">Revisó {current.reviewer} el {new Date(current.created_at).toLocaleDateString("es-ES")}.</p>
        <ul>{(current.evidence || []).map((evidence, index) => <li key={`${evidence.locator}-${index}`}><SourceLink href={evidence.source_url}>{evidence.locator}</SourceLink>: “{evidence.quote}”</li>)}</ul>
      </div>}
      {item.review_status === "accepted_for_extraction" ? <>
        <h3>Confirmar actividad, categoría y campaña</h3>
        <p className="help">Las sugerencias automáticas pueden aparecer preseleccionadas. Comprueba las citas y corrige lo que indiquen las fuentes oficiales. Guardar esta clasificación no verifica elegibilidad.</p>
        <fieldset><legend>Categorías</legend><div className="classification-checks">
          {CATEGORIES.map((category) => <label key={category}><input type="checkbox" checked={categories.includes(category)} onChange={() => toggle(setCategories, categories, category)} />{CATEGORY_LABELS[category]}</label>)}
        </div></fieldset>
        <fieldset><legend>Actividad</legend><div className="classification-checks">
          {ACTIVITIES.map((activity) => <label key={activity}><input type="checkbox" checked={activities.includes(activity)} onChange={() => toggleActivity(activity)} />{ACTIVITY_LABELS[activity]}</label>)}
        </div></fieldset>
        <div className="classification-fields">
          <div><label htmlFor={`classification-year-${item.bdns_code}`}>Campaña (año, si consta)</label><input id={`classification-year-${item.bdns_code}`} type="number" min="1900" max="2200" value={campaignYear} onChange={(event) => setCampaignYear(event.target.value)} /></div>
          <div><label htmlFor={`classification-label-${item.bdns_code}`}>Etiqueta de campaña</label><input id={`classification-label-${item.bdns_code}`} value={campaignLabel} onChange={(event) => setCampaignLabel(event.target.value)} maxLength={120} /></div>
        </div>
        <details className="classification-citation" open={requiresManualEvidence}><summary>Añadir una cita oficial manual (obligatoria si corriges o añades una sugerencia)</summary>
          <label htmlFor={`classification-url-${item.bdns_code}`}>URL oficial</label><input id={`classification-url-${item.bdns_code}`} type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} />
          <label htmlFor={`classification-locator-${item.bdns_code}`}>Apartado, página o campo BDNS</label><input id={`classification-locator-${item.bdns_code}`} value={evidenceLocator} onChange={(event) => setEvidenceLocator(event.target.value)} maxLength={240} />
          <label htmlFor={`classification-quote-${item.bdns_code}`}>Texto que justifica la clasificación</label><textarea id={`classification-quote-${item.bdns_code}`} value={evidenceQuote} onChange={(event) => setEvidenceQuote(event.target.value)} maxLength={1200} rows={2} />
          {(campaignYear && Number(campaignYear) !== triage.campaign_suggestion?.year || campaignLabel.trim()) && <p className="help">La cita debe mencionar explícitamente el año o etiqueta de campaña.</p>}
        </details>
        <label htmlFor={`classification-notes-${item.bdns_code}`}>Notas de clasificación</label>
        <textarea id={`classification-notes-${item.bdns_code}`} value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={2000} rows={2} placeholder="Indica qué comprobaste en la fuente." />
        {error && <p className="review-error" role="alert">{error}</p>}
        <div className="review-actions"><button className="secondary" disabled={saving || !reviewer.trim() || !categories.length || !activities.length || !notes.trim() || !buildEvidence().length || (requiresManualEvidence && !hasManualEvidence)} onClick={save}>{saving ? "Guardando…" : current ? "Actualizar clasificación" : "Guardar clasificación citada"}</button></div>
        {missingRequirements.length > 0 && <p className="help" role="status">Para habilitar el botón: {missingRequirements.join("; ")}.</p>}
      </> : <p className="help">Marca primero la convocatoria como apta para extracción para confirmar su clasificación.</p>}
    </section>
  );
}

function ReviewItem({ item, reviewer, token, onSaved }) {
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [finalizing, setFinalizing] = useState(false);
  const [finalizationResult, setFinalizationResult] = useState(null);
  const [aiPreReview, setAiPreReview] = useState(item.ai_pre_review || null);
  const [error, setError] = useState("");
  const call = item.call || {};
  const body = call.granting_body || {};
  const classification = call.farm_activity_classification || {};
  const bases = item.sources?.regulatory_bases || {};
  const triage = item.automated_triage || {};
  const sectors = (call.economic_sectors || []).map((sector) => sector.label).filter(Boolean).join(", ");
  const beneficiaries = (call.beneficiary_categories || []).map((category) => category.label).filter(Boolean).join(", ");

  useEffect(() => {
    setAiPreReview(item.ai_pre_review || null);
  }, [item.ai_pre_review?.suggestion_id]);

  async function requestPreReview() {
    setAiLoading(true);
    setAiError("");
    try {
      const result = await requestAIReview(token, item.bdns_code);
      setAiPreReview(result);
      if (result.applied_decision) {
        await onSaved(result.applied_decision === "accepted_for_extraction"
          ? "El agente aceptó la convocatoria para extracción con evidencia citada."
          : "El agente marcó la convocatoria fuera de alcance con evidencia citada.");
      }
    } catch (caught) {
      setAiError(caught instanceof ReviewApiError ? caught.message : "No se pudo generar el preanálisis.");
    } finally {
      setAiLoading(false);
    }
  }

  async function finalizeAid() {
    setFinalizing(true);
    setFinalizationResult(null);
    setError("");
    try {
      const result = await finalizeWithAI(token, item.bdns_code);
      setFinalizationResult(result);
      if (result.status === "published") {
        await onSaved(`El agente verificó y publicó ${result.aid_id} con ${result.rule_count} reglas citadas.`);
      }
    } catch (caught) {
      setError(caught instanceof ReviewApiError ? caught.message : "No se pudo finalizar la ficha con el agente.");
    } finally {
      setFinalizing(false);
    }
  }

  async function decide(decision) {
    setSaving(true);
    setError("");
    try {
      const result = await saveReviewDecision(token, item.bdns_code, {
        expected_payload_sha256: item.payload_sha256,
        reviewer: reviewer.trim(),
        decision,
        notes: notes.trim(),
      });
      await onSaved(result.message);
    } catch (caught) {
      setError(caught instanceof ReviewApiError ? caught.message : "No se pudo guardar la decisión.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="review-card">
      <div className="review-card-title">
        <div>
          <p className="review-kicker">BDNS {item.bdns_code}</p>
          <h2>{item.title || "Convocatoria sin título"}</h2>
        </div>
        <span className={`review-status ${item.review_status === "review_required" ? "attention" : ""}`}>
          {STATUS_LABELS[item.review_status] || item.review_status}
        </span>
      </div>

      <dl className="review-facts">
        <div><dt>Organismo</dt><dd>{body.level_1 || body.administration_level || "No indicado"}</dd></div>
        <div><dt>Territorio</dt><dd>{(call.territories || []).map((region) => region.source_label).filter(Boolean).join(", ") || body.level_1 || "No indicado"}</dd></div>
        <div><dt>Finalidad declarada</dt><dd>{call.purpose?.label || "No indicada"}</dd></div>
        <div><dt>Sector económico</dt><dd>{sectors || "No indicado"}</dd></div>
        <div><dt>Personas beneficiarias</dt><dd>{beneficiaries || "No indicadas"}</dd></div>
        <div><dt>Clasificación de actividad</dt><dd>{ACTIVITY_LABELS[classification.status] || "Sin clasificar"}</dd></div>
        <div><dt>Fiabilidad</dt><dd>{item.reliability === "verified" ? `Fuente oficial verificada (${item.verified_by || "revisión registrada"})` : `${RELIABILITY_LABELS[item.reliability] || "Solo metadatos"} · aún no es una ayuda verificada`}</dd></div>
        <div><dt>Última consulta</dt><dd>{item.last_seen_at ? new Date(item.last_seen_at).toLocaleString("es-ES") : "No disponible"}</dd></div>
        <div><dt>Plazo indicado por la fuente</dt><dd>{item.application?.start_text || item.application?.end_text || "Sin plazo indicado"}</dd></div>
      </dl>

      <section className="automated-triage" aria-label="Sugerencias automáticas de relevancia">
        <strong>Orientación automática · requiere confirmación</strong>
        <p><b>{TRIAGE_LABELS[triage.relevance_suggestion] || "Sin sugerencia"}</b> — {triage.explanation || "No disponible."}</p>
        {triage.category_suggestions?.length > 0 && <p><b>Categorías posibles:</b> {triage.category_suggestions.map((suggestion) => `${CATEGORY_LABELS[suggestion.category] || suggestion.category} (${suggestion.priority})`).join(", ")}</p>}
        {Object.keys(triage.activity_suggestions || {}).length > 0 && <p><b>Actividades posibles:</b> {Object.keys(triage.activity_suggestions).map((activity) => ACTIVITY_LABELS[activity] || activity).join(", ")}</p>}
        {triage.campaign_suggestion && <p><b>Campaña posible:</b> {triage.campaign_suggestion.year}, detectada explícitamente en el título.</p>}
        {triage.institutional_beneficiary_terms?.length > 0 && <p><b>Destinatarios institucionales detectados:</b> {triage.institutional_beneficiary_terms.join(", ")}.</p>}
        {[...(triage.category_suggestions || []).flatMap((suggestion) => suggestion.evidence || []), ...Object.values(triage.activity_suggestions || {}).flat()].slice(0, 4).map((evidence, index) => (
          <p className="automated-triage-evidence" key={`${evidence.field}-${index}`}><code>{evidence.field}</code>: {evidence.matched_terms?.join(", ") || evidence.matched_term} — “{evidence.value}”</p>
        ))}
      </section>

      <section className="ai-pre-review" aria-label="Preanálisis asistido por inteligencia artificial">
        <div className="ai-pre-review-heading">
          <div><strong>Revisión con agente</strong><p className="help">Resuelve casos claros con citas y deja los dudosos para revisión humana. No verifica elegibilidad ni publica ayudas.</p></div>
          <button className="secondary" onClick={requestPreReview} disabled={aiLoading}>
            {aiLoading ? "Analizando fuentes…" : aiPreReview ? "Volver a analizar" : "Analizar con agente"}
          </button>
        </div>
        {item.review_status === "accepted_for_extraction" && <div className="review-actions"><button onClick={finalizeAid} disabled={finalizing}>{finalizing ? "Comprobando reglas y publicando…" : "Verificar reglas y publicar con agente"}</button></div>}
        {finalizationResult?.status === "needs_human_review" && <p className="review-warning" role="status">El agente dejó la ficha para revisión: {finalizationResult.reason}</p>}
        {aiError && <p className="review-error" role="alert">{aiError}</p>}
        {aiPreReview?.result && (() => {
          const result = aiPreReview.result;
          const evidenceById = new Map((result.evidence || []).map((evidence) => [evidence.id, evidence]));
          const citedIds = new Set([
            ...(result.categories || []).flatMap((item) => item.evidence_ids || []),
            ...(result.activities || []).flatMap((item) => item.evidence_ids || []),
            ...(result.campaign_evidence_ids || []),
          ]);
          return <div className="ai-pre-review-result">
            {aiPreReview.applied_decision && <p className="review-success"><b>Decisión automática registrada:</b> {aiPreReview.applied_decision === "accepted_for_extraction" ? "apta para extracción" : "fuera de alcance"}. {aiPreReview.decision_reason || result.auto_decision_reason}</p>}
            <p><b>{AI_RELEVANCE_LABELS[result.relevance] || "Orientación no disponible"}</b> · confianza declarada {AI_CONFIDENCE_LABELS[result.confidence] || "no indicada"}</p>
            <p>{result.summary}</p>
            {(result.categories?.length > 0) && <p><b>Categorías sugeridas:</b> {result.categories.map((entry) => CATEGORY_LABELS[entry.value] || entry.value).join(", ")}</p>}
            {(result.activities?.length > 0) && <p><b>Actividades sugeridas:</b> {result.activities.map((entry) => ACTIVITY_LABELS[entry.value] || entry.value).join(", ")}</p>}
            {result.campaign_year && <p><b>Campaña sugerida:</b> {result.campaign_year} · cita explícita</p>}
            {result.auto_decision_evidence?.length > 0 && <div><b>Pruebas usadas para la decisión automática:</b><ul>{result.auto_decision_evidence.map((evidence, index) => <li key={`${evidence.id || evidence.field}-${index}`}><SourceLink href={evidence.source_url}>{evidence.locator || evidence.field}</SourceLink>: “{evidence.quote}”</li>)}</ul></div>}
            {result.questions?.length > 0 && <div><b>Aspectos que faltan comprobar:</b><ul>{result.questions.map((question, index) => <li key={index}>{question}</li>)}</ul></div>}
            {citedIds.size > 0 && <div><b>Evidencias citadas por el agente:</b><ul>{[...citedIds].map((id) => {
              const evidence = evidenceById.get(id);
              return evidence ? <li key={id}><SourceLink href={evidence.source_url}>{evidence.locator || evidence.field}</SourceLink>: “{evidence.quote}”</li> : null;
            })}</ul></div>}
            <p className="help">Modelo: {aiPreReview.model} · {aiPreReview.created_at ? new Date(aiPreReview.created_at).toLocaleString("es-ES") : "recién generado"}. La confianza es orientativa, no una probabilidad. Confirma cada cita en la fuente original.</p>
          </div>;
        })()}
      </section>

      <div className="review-sources">
        <strong>Fuentes oficiales</strong>
        <ul>
          <li><SourceLink href={item.detail_url}>Ficha BDNS</SourceLink></li>
          {bases.url && <li><SourceLink href={bases.url}>{bases.title || "Bases reguladoras"}</SourceLink></li>}
          {item.application?.application_portal_url && <li><SourceLink href={item.application.application_portal_url}>Portal de solicitud</SourceLink></li>}
          {(item.sources?.documents || []).map((document) => (
            <li key={document.bdns_document_id || document.filename}>
              <SourceLink href={document.download_url}>{document.filename || document.description || "Documento BDNS"}</SourceLink>
              {document.size_bytes ? ` (${document.size_bytes.toLocaleString("es-ES")} bytes)` : ""}
            </li>
          ))}
        </ul>
      </div>

      <ClassificationEditor item={item} reviewer={reviewer} token={token} onSaved={onSaved} aiPreReview={aiPreReview} />

      <label htmlFor={`review-notes-${item.bdns_code}`}>Notas de revisión</label>
      <textarea
        id={`review-notes-${item.bdns_code}`}
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
        maxLength={2000}
        rows={3}
        placeholder="Resume qué fuentes consultaste y el motivo de la decisión."
      />
      {error && <p className="review-error" role="alert">{error}</p>}
      <div className="review-actions">
        <button disabled={saving || !reviewer.trim() || !notes.trim()} onClick={() => decide("accepted_for_extraction")}>
          {saving ? "Guardando…" : "Apta para extracción"}
        </button>
        <button className="secondary" disabled={saving || !reviewer.trim() || !notes.trim()} onClick={() => decide("out_of_scope")}>
          Marcar fuera de alcance
        </button>
      </div>
    </article>
  );
}

export default function ReviewQueue() {
  const [tokenInput, setTokenInput] = useState("");
  const [token, setToken] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [status, setStatus] = useState("");
  const [runId, setRunId] = useState("");
  const [regionId, setRegionId] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [filterOptions, setFilterOptions] = useState({ runs: [], regions: [] });
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [aiBatchLoading, setAiBatchLoading] = useState(false);
  const [view, setView] = useState("review");

  async function loadQueue(
    candidateToken = token, candidateStatus = status, candidateOffset = 0, append = false,
    filters = { runId, regionId, query: searchQuery },
  ) {
    setLoading(true);
    setError("");
    try {
      const response = await fetchReviewQueue(candidateToken, candidateStatus, candidateOffset, filters);
      setItems((current) => append ? [...current, ...(response.items || [])] : (response.items || []));
      setTotal(response.total || 0);
      setOffset(candidateOffset);
      setToken(candidateToken);
    } catch (caught) {
      setItems([]);
      setError(caught instanceof ReviewApiError ? caught.message : "No se pudo cargar la bandeja.");
      throw caught;
    } finally {
      setLoading(false);
    }
  }

  async function connect(event) {
    event.preventDefault();
    setNotice("");
    try {
      await loadQueue(tokenInput.trim(), status);
      setFilterOptions(await fetchReviewFilterOptions(tokenInput.trim()));
    } catch {
      // The request already displayed a safe message.
    }
  }

  async function changeStatus(event) {
    const next = event.target.value;
    setStatus(next);
    if (token) {
      try { await loadQueue(token, next); } catch { /* Error is shown in the page. */ }
    }
  }

  async function applyFilters() {
    try { await loadQueue(token, status, 0, false, { runId, regionId, query: searchQuery }); }
    catch { /* Error is shown in the page. */ }
  }

  async function clearFilters() {
    setRunId("");
    setRegionId("");
    setSearchQuery("");
    try { await loadQueue(token, status, 0, false, { runId: "", regionId: "", query: "" }); }
    catch { /* Error is shown in the page. */ }
  }

  async function refreshQueueAndFilters() {
    try {
      await loadQueue();
      setFilterOptions(await fetchReviewFilterOptions(token));
    } catch { /* Error is shown in the page. */ }
  }

  async function onSaved(message) {
    setNotice(message);
    await loadQueue();
  }

  async function processPendingWithAgent() {
    setAiBatchLoading(true);
    setError("");
    setNotice("");
    const filters = { runId, regionId, query: searchQuery };
    try {
      const result = await processAIReviewQueue(token, filters, 10);
      const counts = result.counts || {};
      const errorDetails = [...new Set((result.results || []).filter((item) => item.result === "error" && item.error).map((item) => item.error))].slice(0, 3);
      const detailText = errorDetails.length ? ` Motivo: ${errorDetails.join("; ")}` : "";
      setNotice(`Agente: ${counts.accepted_for_extraction || 0} aptas para extracción, ${counts.out_of_scope || 0} fuera de alcance, ${counts.needs_human_review || 0} quedan para revisión humana y ${counts.errors || 0} con error. Procesadas: ${result.processed || 0}.${detailText}`);
      await loadQueue(token, status, 0, false, filters);
    } catch (caught) {
      setError(caught instanceof ReviewApiError ? caught.message : "No se pudo procesar la bandeja con el agente.");
    } finally {
      setAiBatchLoading(false);
    }
  }

  async function loadNextPage() {
    try { await loadQueue(token, status, offset + PAGE_SIZE, true); } catch { /* Error is shown in the page. */ }
  }

  return (
    <main className="review-page">
      <header className="review-header">
        <div><p className="review-kicker">Espacio interno</p><h1>Revisión de convocatorias</h1></div>
        <a href="/">Volver a la aplicación</a>
      </header>
      <p className="review-warning" role="note">
        El agente puede resolver automáticamente los casos claros y conserva evidencia de su decisión. <strong>Los casos dudosos quedan pendientes; ninguna decisión verifica elegibilidad ni publica la convocatoria en el catálogo.</strong>
      </p>

      {!token ? (
        <form className="panel review-login" onSubmit={connect}>
          <h2>Acceso de revisión</h2>
          <p className="help">Introduce la clave interna habilitada por el administrador. Se mantiene solo en esta sesión del navegador.</p>
          <label htmlFor="review-token">Clave de acceso</label>
          <input id="review-token" type="password" autoComplete="current-password" value={tokenInput} onChange={(event) => setTokenInput(event.target.value)} required />
          {error && <p className="review-error" role="alert">{error}</p>}
          <div className="review-actions"><button disabled={loading}>{loading ? "Comprobando…" : "Entrar"}</button></div>
        </form>
      ) : (
        <>
          <div className="panel review-toolbar">
            <div className="review-toolbar-fields">
              {view !== "coverage" && <div><label htmlFor="reviewer-name">Nombre de quien revisa</label><input id="reviewer-name" value={reviewer} onChange={(event) => setReviewer(event.target.value)} minLength={2} maxLength={120} /></div>}
              {view === "review" && <div><label htmlFor="review-status">Mostrar</label><select id="review-status" value={status} onChange={changeStatus}>
                <option value="">Pendientes y cambios por revisar</option>
                <option value="accepted_for_extraction">Aptas para extracción</option>
                <option value="out_of_scope">Fuera de alcance</option>
                <option value="all">Todas</option>
              </select></div>}
              {view === "review" && <div><label htmlFor="review-run">Ejecución de importación</label><select id="review-run" value={runId} onChange={(event) => setRunId(event.target.value)}>
                <option value="">Todas las ejecuciones</option>
                {filterOptions.runs.map((run) => <option key={run.run_id} value={run.run_id} disabled={run.record_count === 0}>Run {run.run_id} · {new Date(run.started_at).toLocaleDateString("es-ES")}{run.record_count === 0 ? " · anterior al filtro; repetir importación" : ` · ${run.record_count} convocatorias`}</option>)}
              </select></div>}
              {view === "review" && <div><label htmlFor="review-region">Territorio consultado</label><select id="review-region" value={regionId} onChange={(event) => setRegionId(event.target.value)}>
                <option value="">Todos los territorios</option>
                {filterOptions.regions.map((region) => <option key={region.region_id} value={region.region_id}>{region.territory}</option>)}
              </select></div>}
              {view === "review" && <div><label htmlFor="review-search">Título o código BDNS</label><input id="review-search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} maxLength={200} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); applyFilters(); } }} /></div>}
            </div>
            <div className="review-toolbar-actions">
              {view === "review" && <>
                <button className="secondary" onClick={applyFilters}>Filtrar</button>
                <button className="secondary" onClick={clearFilters}>Limpiar filtros</button>
                <button onClick={processPendingWithAgent} disabled={aiBatchLoading || loading || status !== ""} title={status ? "El procesamiento automático usa la bandeja de pendientes" : "Procesa hasta 10 convocatorias del filtro actual"}>{aiBatchLoading ? "Procesando con agente…" : "Procesar hasta 10 con agente"}</button>
              </>}
              <button className={view === "review" ? "" : "secondary"} onClick={() => setView("review")}>Convocatorias</button>
              <button className={view === "extractions" ? "" : "secondary"} onClick={() => setView("extractions")}>Extracciones</button>
              <button className={view === "coverage" ? "" : "secondary"} onClick={() => setView("coverage")}>Cobertura</button>
              {view === "review" && <button className="secondary" onClick={refreshQueueAndFilters}>Actualizar</button>}
              <button className="secondary" onClick={() => { setToken(""); setTokenInput(""); setItems([]); setView("review"); }}>Cerrar sesión</button>
            </div>
          </div>
          {view === "coverage" ? <CoverageReport token={token} /> : view === "extractions" ? <ExtractionReviewQueue token={token} reviewer={reviewer} /> : <>
            {notice && <p className="review-success" role="status">{notice}</p>}
            {error && <p className="review-error" role="alert">{error}</p>}
            {loading ? <p className="help" role="status">Cargando convocatorias…</p> : items.length ? (
              <section className="review-list" aria-label="Convocatorias">
                {items.map((item) => <ReviewItem key={item.bdns_code} item={item} reviewer={reviewer} token={token} onSaved={onSaved} />)}
                {items.length < total && <button className="secondary review-more" disabled={loading} onClick={loadNextPage}>Ver más convocatorias ({items.length} de {total})</button>}
              </section>
            ) : <p className="panel review-empty">No hay convocatorias en este filtro.</p>}
          </>}
        </>
      )}
    </main>
  );
}
