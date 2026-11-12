import logging
import hmac
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from app.agent.agent import LLMError, run_agent
from app.core import config
from app.data.loader import AIDS, AIDS_BY_ID, DATA_SOURCE
from app.models.api import ChatRequest, ChatResponse
from app.models.review import (
    BDNSReviewSubmission, BDNSExtractionReviewSubmission, BDNSVerificationSubmission,
    BDNSClassificationSubmission,
)
from app.db import database as db
from app.bdns import BDNSClient, BDNSClientError
from app.bdns.ai_review import AIReviewError, analyze_bdns_call
from app.bdns.ai_finalization import AIFinalizationError, analyze_finalization

logging.basicConfig(level=logging.INFO)

app = FastAPI(title=f"{config.APP_NAME} API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "aids_loaded": len(AIDS), "data_source": DATA_SOURCE,
            "llm_configured": bool(config.LLM_API_KEY)}


@app.get("/api/aids/{aid_id}")
def aid_detail(aid_id: str):
    from app.data import loader
    loader.refresh_from_database()
    aid = AIDS_BY_ID.get(aid_id)
    if not aid:
        raise HTTPException(status_code=404, detail="Aid not found.")
    return aid


def require_bdns_reviewer(authorization: str | None = Header(default=None)) -> None:
    configured = config.BDNS_REVIEW_TOKEN
    if not configured:
        raise HTTPException(status_code=404, detail="La revisión interna no está habilitada.")
    scheme, separator, supplied = (authorization or "").partition(" ")
    if not separator or scheme.lower() != "bearer" or not hmac.compare_digest(supplied, configured):
        raise HTTPException(
            status_code=401,
            detail="Se requiere una clave de revisión válida.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _review_database_url() -> str:
    if not config.DATABASE_URL:
        raise HTTPException(status_code=503, detail="La bandeja de revisión requiere la base de datos.")
    return config.DATABASE_URL


ReviewQueueStatus = Literal[
    "pending_review", "review_required", "reviewed",
    "accepted_for_extraction", "out_of_scope", "all",
]
ExtractionReviewStatus = Literal["open", "needs_correction", "reviewed_candidate", "stale", "all"]


@app.get("/api/admin/bdns/verification/{bdns_code}")
def bdns_verification_state(
    bdns_code: str,
    _: None = Depends(require_bdns_reviewer),
):
    with db.connect(_review_database_url()) as conn:
        state = db.read_bdns_verification_state(conn, bdns_code)
    if state is None:
        raise HTTPException(status_code=404, detail="No se encontró la convocatoria BDNS.")
    return state


@app.post("/api/admin/bdns/verification/{bdns_code}")
def submit_bdns_verification(
    bdns_code: str, submission: BDNSVerificationSubmission,
    _: None = Depends(require_bdns_reviewer),
):
    with db.connect(_review_database_url()) as conn:
        outcome = db.verify_bdns_call(
            conn, bdns_code, submission.expected_payload_sha256,
            submission.expected_extraction_fingerprint, submission.reviewer,
            submission.notes, [rule.model_dump(mode="json") for rule in submission.approved_rules],
        )
        state = db.read_bdns_verification_state(conn, bdns_code) if outcome == "verified" else None
    if outcome == "not_found":
        raise HTTPException(status_code=404, detail="No se encontró la convocatoria BDNS.")
    if outcome == "stale":
        raise HTTPException(status_code=409, detail="La fuente cambió. Actualiza la verificación antes de aprobarla.")
    if outcome == "not_ready":
        raise HTTPException(status_code=409, detail="La convocatoria necesita una extracción actual, revisión de tareas pendientes y un control de calidad aprobado.")
    if outcome == "invalid_citation":
        raise HTTPException(status_code=422, detail="Cada regla debe citar una fuente oficial asociada a esta convocatoria.")
    return {"status": outcome, "reliability": "verified", "verification": state}


@app.post("/api/admin/bdns/finalize/{bdns_code}")
def finalize_bdns_with_agent(
    bdns_code: str,
    _: None = Depends(require_bdns_reviewer),
):
    """Verify cited, machine-evaluable rules and publish a catalog aid when all gates pass."""
    if not config.LLM_API_KEY:
        raise HTTPException(status_code=503, detail="El agente de verificación no está configurado.")
    with db.connect(_review_database_url()) as conn:
        records = db.read_bdns_calls(conn, bdns_code)
        if not records:
            raise HTTPException(status_code=404, detail="No se encontró la convocatoria BDNS.")
        record = records[0]
        extraction = db.read_latest_bdns_extraction(conn, bdns_code)
        state = db.read_bdns_verification_state(conn, bdns_code)
        payload_hash = record.get("source_state", {}).get("payload_sha256", "")
        extraction_fingerprint = (extraction or {}).get("source_fingerprint", "")
        if not state["eligible_to_verify"]:
            gates = []
            if state["review_status"] != "accepted_for_extraction": gates.append("convocatoria no aceptada para extracción")
            if not state["extraction_current"]: gates.append("extracción ausente o desactualizada")
            if state["pending_extraction_tasks"]: gates.append(f"{state['pending_extraction_tasks']} tareas pendientes")
            if not state["quality_current"]: gates.append("control de calidad no aprobado para la versión actual")
            detail = {"reason": "; ".join(gates), "verification_state": state}
            db.record_bdns_ai_finalization_event(
                conn, bdns_code=bdns_code, payload_sha256=payload_hash,
                extraction_fingerprint=extraction_fingerprint, model=config.LLM_MODEL,
                outcome="needs_human_review", details=detail,
            )
            return {"status": "needs_human_review", **detail}
        existing = conn.execute(
            "SELECT aid_id FROM aid_bdns_calls WHERE bdns_code = %s LIMIT 1", (bdns_code,),
        ).fetchone()
        if existing:
            detail = {"reason": f"La convocatoria ya está vinculada a la ficha {existing[0]}; no se sobrescribe automáticamente."}
            db.record_bdns_ai_finalization_event(
                conn, bdns_code=bdns_code, payload_sha256=payload_hash,
                extraction_fingerprint=extraction_fingerprint, model=config.LLM_MODEL,
                outcome="needs_human_review", details=detail,
            )
            return {"status": "needs_human_review", **detail}

    try:
        result = analyze_finalization(record, extraction)
    except AIFinalizationError as exc:
        with db.connect(_review_database_url()) as conn:
            db.record_bdns_ai_finalization_event(
                conn, bdns_code=bdns_code, payload_sha256=payload_hash,
                extraction_fingerprint=extraction_fingerprint, model=config.LLM_MODEL,
                outcome="needs_human_review", details={"reason": str(exc)},
            )
        return {"status": "needs_human_review", "reason": str(exc)}

    if result["status"] != "ready_to_publish":
        with db.connect(_review_database_url()) as conn:
            db.record_bdns_ai_finalization_event(
                conn, bdns_code=bdns_code, payload_sha256=payload_hash,
                extraction_fingerprint=extraction_fingerprint, model=config.LLM_MODEL,
                outcome="needs_human_review", details=result,
            )
        return result

    notes = "Verificación automática: reglas normalizadas y citadas desde la extracción oficial actual; ficha publicada por el agente."
    with db.connect(_review_database_url()) as conn:
        outcome = db.verify_bdns_call(
            conn, bdns_code, payload_hash, extraction_fingerprint,
            "Agente IA BDNS", notes, result["approved_rules"],
        )
        if outcome != "verified":
            detail = {"reason": "La fuente o sus controles cambiaron durante la verificación; vuelve a procesarla.", "gate": outcome}
            db.record_bdns_ai_finalization_event(
                conn, bdns_code=bdns_code, payload_sha256=payload_hash,
                extraction_fingerprint=extraction_fingerprint, model=config.LLM_MODEL,
                outcome="needs_human_review", details=detail,
            )
            return {"status": "needs_human_review", **detail}
        db.upsert_aids(conn, [result["aid"]])
        event_id = db.record_bdns_ai_finalization_event(
            conn, bdns_code=bdns_code, payload_sha256=payload_hash,
            extraction_fingerprint=extraction_fingerprint, model=config.LLM_MODEL,
            outcome="published", details={
                "aid_id": result["aid"]["id"], "rule_count": len(result["rules"]),
                "evidence_count": result["evidence_count"],
            },
        )
        verification_state = db.read_bdns_verification_state(conn, bdns_code)
        conn.commit()

    try:
        from app.data import loader
        loader.refresh_from_database()
    except Exception as exc:  # noqa: BLE001
        logging.exception("Published BDNS aid %s but failed to refresh the in-memory catalog", result["aid"]["id"])
        raise HTTPException(status_code=500, detail="La ficha se publicó en la base de datos, pero el catálogo requiere reiniciar el backend.") from exc
    return {
        "status": "published", "event_id": event_id, "aid_id": result["aid"]["id"],
        "reliability": "verified", "verification_method": "agent",
        "rule_count": len(result["rules"]), "verification": verification_state,
    }


@app.get("/api/admin/bdns/extraction-review")
def bdns_extraction_review_queue(
    status: ExtractionReviewStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: None = Depends(require_bdns_reviewer),
):
    with db.connect(_review_database_url()) as conn:
        items = db.read_bdns_extraction_review_queue(conn, status=status, limit=limit, offset=offset)
        total = db.count_bdns_extraction_review_queue(conn, status=status)
    return {"items": items, "count": len(items), "total": total, "limit": limit, "offset": offset}


@app.post("/api/admin/bdns/extraction-review/ai-process")
def process_simple_extraction_tasks(
    limit: int = Query(default=50, ge=1, le=100),
    _: None = Depends(require_bdns_reviewer),
):
    """Close only single-candidate tasks with a current citation to a registered official source."""
    processed = 0
    left_for_human = 0
    skipped = []
    with db.connect(_review_database_url()) as conn:
        tasks = db.read_bdns_extraction_review_queue(conn, status="open", limit=limit)
        for task in tasks:
            candidates = task.get("details", {}).get("candidates", [])
            candidate = candidates[0] if len(candidates) == 1 else None
            raw = db.read_bdns_calls(conn, task["bdns_code"])
            record = raw[0] if raw else {}
            citation = (candidate or {}).get("citation") or {}
            url = citation.get("url")
            sources = record.get("sources", {})
            allowed_urls = {record.get("source_identity", {}).get("detail_url")}
            allowed_urls.add((sources.get("regulatory_bases") or {}).get("url"))
            allowed_urls.update(item.get("download_url") for item in sources.get("documents", []) if isinstance(item, dict))
            allowed_urls.update(item.get("url") for item in sources.get("announcements", []) if isinstance(item, dict))
            cite_ok = (
                candidate and isinstance(candidate.get("value"), str) and candidate["value"].strip()
                and isinstance(url, str) and url in allowed_urls
                and bool(citation.get("page") or citation.get("section"))
                and isinstance(citation.get("quote"), str) and citation["quote"].strip()
            )
            if not cite_ok:
                left_for_human += 1
                skipped.append({"task_id": task["task_id"], "bdns_code": task["bdns_code"],
                                "reason": "Falta una única cita oficial completa para cerrar esta tarea."})
                continue
            outcome = db.review_bdns_extraction_task(
                conn, task["task_id"], task["payload_sha256"],
                task.get("extraction_fingerprint", ""), "Agente IA BDNS", "reviewed_candidate",
                "Validación automática: candidato único con cita, localizador y huella de extracción actuales.",
            )
            if outcome == "reviewed_candidate":
                processed += 1
            else:
                left_for_human += 1
                skipped.append({"task_id": task["task_id"], "bdns_code": task["bdns_code"],
                                "reason": "La tarea cambió o no pudo cerrarse con la versión actual."})
    return {"processed": processed, "left_for_human": left_for_human, "skipped": skipped}


@app.post("/api/admin/bdns/extraction-review/{task_id}")
def submit_bdns_extraction_review(
    task_id: int, submission: BDNSExtractionReviewSubmission,
    _: None = Depends(require_bdns_reviewer),
):
    with db.connect(_review_database_url()) as conn:
        outcome = db.review_bdns_extraction_task(
            conn, task_id, submission.expected_payload_sha256,
            submission.expected_extraction_fingerprint, submission.reviewer,
            submission.decision, submission.notes,
        )
    if outcome == "not_found":
        raise HTTPException(status_code=404, detail="No se encontró la tarea de revisión.")
    if outcome == "stale":
        raise HTTPException(status_code=409, detail="La fuente cambió. Actualiza la bandeja antes de revisar.")
    if outcome == "invalid_state":
        raise HTTPException(status_code=409, detail="La tarea ya no está pendiente de revisión.")
    return {
        "task_id": task_id, "status": outcome, "reliability": "extracted",
        "message": ("Candidato revisado. Sigue siendo información extraída y no verificada."
                    if outcome == "reviewed_candidate" else
                    "Se ha marcado para corrección; la información sigue sin verificar."),
    }


@app.get("/api/admin/bdns/review")
def bdns_review_queue(
    status: ReviewQueueStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    run_id: int | None = Query(default=None, ge=1),
    region_id: int | None = Query(default=None, ge=0),
    q: str | None = Query(default=None, max_length=200),
    _: None = Depends(require_bdns_reviewer),
):
    with db.connect(_review_database_url()) as conn:
        filters = {"run_id": run_id, "region_id": region_id, "query": q}
        if any(value is not None and value != "" for value in filters.values()):
            items = db.read_bdns_review_queue(
                conn, status=status, limit=limit, offset=offset, **filters
            )
            total = db.count_bdns_review_queue(conn, status=status, **filters)
        else:
            items = db.read_bdns_review_queue(conn, status=status, limit=limit, offset=offset)
            total = db.count_bdns_review_queue(conn, status=status)
    return {"items": items, "count": len(items), "total": total, "limit": limit, "offset": offset}


@app.get("/api/admin/bdns/review/filters")
def bdns_review_filter_options(_: None = Depends(require_bdns_reviewer)):
    with db.connect(_review_database_url()) as conn:
        return db.read_bdns_review_filter_options(conn)


@app.get("/api/admin/bdns/review/{bdns_code}/history")
def bdns_review_history(
    bdns_code: str,
    limit: int = Query(default=50, ge=1, le=100),
    _: None = Depends(require_bdns_reviewer),
):
    with db.connect(_review_database_url()) as conn:
        items = db.read_bdns_call_reviews(conn, bdns_code, limit=limit)
    return {"items": items, "count": len(items)}


@app.get("/api/admin/bdns/coverage")
def bdns_import_coverage(
    run_limit: int = Query(default=20, ge=1, le=100),
    _: None = Depends(require_bdns_reviewer),
):
    with db.connect(_review_database_url()) as conn:
        return db.read_bdns_coverage(conn, run_limit=run_limit)


@app.post("/api/admin/bdns/ai-review/{bdns_code}")
def bdns_ai_pre_review(
    bdns_code: str,
    _: None = Depends(require_bdns_reviewer),
):
    if not config.LLM_API_KEY:
        raise HTTPException(status_code=503, detail="El preanálisis con IA no está configurado.")
    with db.connect(_review_database_url()) as conn:
        records = db.read_bdns_calls(conn, bdns_code)
        extraction = db.read_latest_bdns_extraction(conn, bdns_code)
    if not records:
        raise HTTPException(status_code=404, detail="No se encontró la convocatoria BDNS.")

    record = records[0]
    fingerprint = (record.get("source_state") or {}).get("payload_sha256")
    if not fingerprint:
        raise HTTPException(status_code=409, detail="La convocatoria no tiene una huella de fuente actual.")
    try:
        suggestion = analyze_bdns_call(record, extraction)
    except AIReviewError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    with db.connect(_review_database_url()) as conn:
        saved = db.record_bdns_ai_review_suggestion(
            conn, bdns_code, fingerprint, config.LLM_MODEL, suggestion,
        )
    if saved == "not_found":
        raise HTTPException(status_code=404, detail="No se encontró la convocatoria BDNS.")
    if saved == "stale":
        raise HTTPException(status_code=409, detail="La fuente cambió durante el preanálisis. Actualiza la bandeja y vuelve a intentarlo.")
    return {
        "bdns_code": bdns_code,
        "suggestion_id": saved["suggestion_id"],
        "created_at": saved["created_at"],
        "model": config.LLM_MODEL,
        "result": suggestion,
        "review_status_changed": bool(saved.get("applied_decision")),
        "applied_decision": saved.get("applied_decision"),
        "reliability_changed": False,
    }


@app.post("/api/admin/bdns/ai-review")
def bdns_ai_pre_review_batch(
    limit: int = Query(default=10, ge=1, le=10),
    run_id: int | None = Query(default=None, ge=1),
    region_id: int | None = Query(default=None, ge=1),
    q: str | None = Query(default=None, max_length=200),
    _: None = Depends(require_bdns_reviewer),
):
    """Process a bounded slice of the current filtered queue; uncertain calls stay pending."""
    if not config.LLM_API_KEY:
        raise HTTPException(status_code=503, detail="El agente de revisión no está configurado.")
    with db.connect(_review_database_url()) as conn:
        items = db.read_bdns_review_queue(
            conn, limit=limit, run_id=run_id, region_id=region_id, query=q, ai_unreviewed_only=True,
        )
        source_records = {}
        extractions = {}
        for item in items:
            code = item["bdns_code"]
            raw_records = db.read_bdns_calls(conn, code)
            if raw_records:
                source_records[code] = raw_records[0]
                extractions[code] = db.read_latest_bdns_extraction(conn, code)

    counts = {"accepted_for_extraction": 0, "out_of_scope": 0, "needs_human_review": 0, "errors": 0}
    results = []
    for record in items:
        code = record["bdns_code"]
        fingerprint = record.get("payload_sha256")
        try:
            source_record = source_records.get(code)
            if not source_record:
                counts["errors"] += 1
                results.append({"bdns_code": code, "result": "not_found"})
                continue
            suggestion = analyze_bdns_call(source_record, extractions.get(code))
            with db.connect(_review_database_url()) as conn:
                saved = db.record_bdns_ai_review_suggestion(
                    conn, code, fingerprint, config.LLM_MODEL, suggestion,
                )
            if isinstance(saved, str) and saved in {"not_found", "stale"}:
                counts["errors"] += 1
                results.append({"bdns_code": code, "result": saved})
                continue
            decision = saved.get("applied_decision")
            bucket = decision or "needs_human_review"
            counts[bucket] += 1
            results.append({"bdns_code": code, "result": bucket, "suggestion_id": saved["suggestion_id"]})
        except AIReviewError as exc:
            logging.warning("AI pre-review skipped BDNS %s: %s", code, exc)
            counts["errors"] += 1
            results.append({"bdns_code": code, "result": "error", "error": str(exc)})
    return {"processed": len(items), "counts": counts, "results": results}


@app.get("/api/admin/bdns/extractions/{bdns_code}")
def bdns_extraction(
    bdns_code: str,
    _: None = Depends(require_bdns_reviewer),
):
    with db.connect(_review_database_url()) as conn:
        extraction = db.read_latest_bdns_extraction(conn, bdns_code)
    if extraction is None:
        raise HTTPException(status_code=404, detail="No hay extracción para esta convocatoria BDNS.")
    return extraction


@app.get("/api/admin/bdns/calls/{bdns_code}/documents/{document_id}")
def download_bdns_source_document(
    bdns_code: str,
    document_id: int,
    _: None = Depends(require_bdns_reviewer),
):
    if document_id < 1:
        raise HTTPException(status_code=404, detail="No se encontró el documento BDNS.")
    with db.connect(_review_database_url()) as conn:
        records = db.read_bdns_calls(conn, bdns_code)
    if not records:
        raise HTTPException(status_code=404, detail="No se encontró la convocatoria BDNS.")
    documents = records[0].get("sources", {}).get("documents", [])
    if not any(
        isinstance(document, dict)
        and document.get("bdns_document_id") == document_id
        for document in documents
    ):
        raise HTTPException(status_code=404, detail="El documento no pertenece a esta convocatoria.")
    try:
        with BDNSClient.from_config() as client:
            content, _ = client.download_document(
                document_id, max_bytes=config.BDNS_DOCUMENT_MAX_BYTES
            )
    except BDNSClientError as exc:
        logging.warning("BDNS document %s download failed: %s", document_id, exc)
        raise HTTPException(status_code=502, detail="BDNS no pudo entregar el documento PDF.") from exc
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="bdns-document-{document_id}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/api/admin/bdns/quality/{bdns_code}")
def bdns_quality_check(
    bdns_code: str,
    _: None = Depends(require_bdns_reviewer),
):
    with db.connect(_review_database_url()) as conn:
        report = db.read_latest_bdns_quality_check(conn, bdns_code)
    if report is None:
        raise HTTPException(status_code=404, detail="No hay comprobación de calidad para esta convocatoria BDNS.")
    return report


@app.post("/api/admin/bdns/review/{bdns_code}")
def submit_bdns_review(
    bdns_code: str,
    submission: BDNSReviewSubmission,
    _: None = Depends(require_bdns_reviewer),
):
    with db.connect(_review_database_url()) as conn:
        outcome = db.review_bdns_call(
            conn,
            bdns_code=bdns_code,
            expected_payload_sha256=submission.expected_payload_sha256,
            reviewer=submission.reviewer,
            decision=submission.decision,
            notes=submission.notes,
        )
    if outcome == "not_found":
        raise HTTPException(status_code=404, detail="No se encontró la convocatoria BDNS.")
    if outcome == "stale":
        raise HTTPException(
            status_code=409,
            detail="La convocatoria cambió desde que se abrió. Recarga la bandeja antes de revisarla.",
        )
    return {
        "bdns_code": bdns_code,
        "review_status": outcome,
        "reliability": "metadata_only",
        "message": "Decisión guardada. La convocatoria sigue sin estar verificada ni publicada como ayuda.",
    }


@app.post("/api/admin/bdns/classification/{bdns_code}")
def submit_bdns_classification(
    bdns_code: str,
    submission: BDNSClassificationSubmission,
    _: None = Depends(require_bdns_reviewer),
):
    with db.connect(_review_database_url()) as conn:
        outcome = db.record_bdns_classification(
            conn,
            bdns_code=bdns_code,
            expected_payload_sha256=submission.expected_payload_sha256,
            reviewer=submission.reviewer,
            categories=submission.categories,
            activities=submission.activities,
            campaign_year=submission.campaign_year,
            campaign_label=submission.campaign_label,
            evidence=[item.model_dump(mode="json") for item in submission.evidence],
            notes=submission.notes,
        )
    if outcome == "not_found":
        raise HTTPException(status_code=404, detail="No se encontró la convocatoria BDNS.")
    if outcome == "stale":
        raise HTTPException(status_code=409, detail="La fuente cambió. Recarga la bandeja antes de clasificar.")
    if outcome == "invalid_state":
        raise HTTPException(
            status_code=409,
            detail="Primero marca la convocatoria como apta para extracción antes de clasificarla.",
        )
    return {
        "bdns_code": bdns_code,
        "status": "classification_saved",
        "reliability": "metadata_only",
        "message": "Clasificación guardada con cita. No verifica elegibilidad ni publica la ayuda.",
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    profile = req.profile.model_dump(exclude_none=True) if req.profile else {}
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    try:
        from app.data import loader
        loader.refresh_from_database()
        return run_agent(messages, profile)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
