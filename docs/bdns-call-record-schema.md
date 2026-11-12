# BDNS call record schema (design)

## Purpose and boundary

This schema defines the ingestion record for one BDNS `convocatoria`. It is separate from the existing `Aid` model: `Aid` is the user-facing concept/rule set, while a BDNS call is a source record for one registered call or campaign. One aid programme can have several BDNS calls across campaigns, and one call can contain several interventions. Keep those records linked rather than flattening them into one eligibility object.

Every imported call starts at `metadata_only`. Discovery or machine extraction does not verify eligibility. Only a reviewed and approved rule set may be linked to a `verified` user-facing aid. Never import or retain BDNS concession/award recipient records for this feature.

## Canonical record

```json
{
  "schema_version": "1.0",
  "source_identity": {
    "system": "BDNS",
    "bdns_code": "920758",
    "bdns_internal_id": 1122319,
    "detail_url": "https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/920758"
  },
  "source_state": {
    "first_seen_at": "2026-11-10T23:00:00Z",
    "last_seen_at": "2026-11-10T23:00:00Z",
    "retrieved_at": "2026-11-10T23:00:00Z",
    "payload_sha256": null,
    "snapshot_id": null
  },
  "call": {
    "title": "Source title as registered in BDNS",
    "title_co_official": null,
    "received_date": "2026-07-22",
    "call_type": "Concesión directa - instrumental",
    "budget_eur": 200000,
    "mrr": false,
    "purpose": {"code": null, "label": "Agricultura, Pesca y Alimentación"},
    "instruments": ["SUBVENCIÓN Y ENTREGA DINERARIA SIN CONTRAPRESTACIÓN"],
    "economic_sectors": [{"code": "A", "label": "AGRICULTURA, GANADERÍA, SILVICULTURA Y PESCA"}],
    "beneficiary_categories": [{"code": null, "label": "PERSONAS JURÍDICAS QUE NO DESARROLLAN ACTIVIDAD ECONÓMICA"}],
    "funds": [],
    "state_aid": {"number": null, "url": null, "regulation": null},
    "product_sectors": [],
    "objectives": [],
    "granting_body": {
      "administration_level": "AUTONOMICA",
      "level_1": "ARAGÓN",
      "level_2": "DIRECCIÓN GENERAL DE CALIDAD Y SEGURIDAD ALIMENTARIA",
      "level_3": null
    },
    "territories": [{"source_label": "ES24 - ARAGON", "code": "ES24", "level": "autonomous_community"}],
    "farm_activity_classification": {
      "activities": [],
      "status": "unclassified",
      "evidence": []
    },
    "campaign": {"year": null, "label": null, "evidence": null}
  },
  "application": {
    "application_portal_url": "https://www.aragon.es/tramites",
    "start_date": null,
    "end_date": null,
    "start_text": "Sin plazo de solicitud",
    "end_text": "Sin plazo de solicitud",
    "open_ended": false,
    "status": "unknown",
    "status_evidence": null,
    "official_gazette_extract_expected": false
  },
  "sources": {
    "regulatory_bases": {
      "title": "Decreto Legislativo 2/2023, de 3 de mayo...",
      "url": "https://www.boe.es/buscar/pdf/2023/BOE-A-2023-12919-consolidado.pdf"
    },
    "announcements": [],
    "documents": [
      {
        "bdns_document_id": 1515086,
        "filename": "CSV7G6HPQH2KB1M0XFIL 14030_ORDEN Lab EET_UZ_2026.pdf",
        "description": "Documento de la convocatoria en español",
        "size_bytes": 515337,
        "published_at": "2026-09-01",
        "source_modified_at": "2026-09-01",
        "download_url": "https://www.infosubvenciones.es/bdnstrans/api/convocatorias/documentos?idDocumento=1515086",
        "content_sha256": null,
        "stored_object_uri": null
      }
    ]
  },
  "quality": {
    "reliability": "metadata_only",
    "eligibility_status": "not_assessed",
    "reviewed_by": null,
    "reviewed_at": null,
    "review_notes": null
  }
}
```

The example uses the real Aragón detail shape to show mapping only. It is an instrumental University of Zaragoza food-safety grant, not direct farm aid. Its agriculture-related sector code must not automatically classify it as farm-eligible.

## Field rules

| Group | Required fields | Rules |
|---|---|---|
| Source identity | `system`, `bdns_code`, `detail_url` | Use the BDNS code as the stable unique source key. Keep the internal numeric ID as a source attribute. Never deduplicate on title. |
| Source state | `retrieved_at`, `payload_sha256`, `snapshot_id` | Store each fetched JSON payload as an immutable snapshot; hash its deterministic canonical JSON representation so key order and whitespace do not create false changes. The decoded client does not retain original wire formatting. `first_seen_at` and `last_seen_at` belong to the local index. |
| Call metadata | title, received date, type, body, territory, purpose, sector, beneficiary categories | Preserve source wording and source codes. Nullable/missing values stay null; don't invent dates, campaign, region codes or beneficiary rules. |
| Farm activity | activities, status, evidence | Use controlled values `agriculture`, `livestock`, `mixed`; also allow `unclassified` and `out_of_scope`. Record the title/sector/document evidence for a classification. BDNS sector A or agriculture purpose alone is insufficient. |
| Application | ISO dates plus original date text, `open_ended`, separate `status` | Keep `fechaInicioSolicitud`, `fechaFinSolicitud`, `textInicio`, `textFin`, and BDNS `abierto` separately. `abierto` means an indefinite application is possible; it is not the same as currently open. If the source is ambiguous, status is `unknown`. |
| Sources | bases URL, each announcement, each document | Keep multiple announcements and documents as separate records, with BDNS ID, CVE, publication date, source URL and document metadata. Binary content is stored separately with a content hash. |
| Quality | reliability and review fields | Imported raw metadata starts `metadata_only`. `extracted` means machine-extracted facts are present but not approved. `verified` requires a named reviewer, review time and cited official text. |

Recommended controlled values:

- `application.status`: `unknown`, `not_announced`, `upcoming`, `open`, `closed`, `indefinite`, `not_applicable`.
- `quality.reliability`: `metadata_only`, `extracted`, `verified`.
- `quality.eligibility_status`: `not_assessed`, `conditional`, `reviewed`.
- Farm activity and campaign classifications are internal values; always keep the raw BDNS fields alongside them.

## Mapping from BDNS detail fields

| BDNS field | Canonical field |
|---|---|
| `codigoBDNS` | `source_identity.bdns_code` |
| `id` | `source_identity.bdns_internal_id` |
| Detail page | `source_identity.detail_url` (constructed from known portal locale and code) |
| `fechaRecepcion` | `call.received_date` |
| `descripcion`, `descripcionLeng` | `call.title`, `call.title_co_official` |
| `tipoConvocatoria`, `presupuestoTotal`, `mrr` | matching `call` fields |
| `instrumentos[]` | `call.instruments[]` |
| `organo.nivel1..nivel3` | `call.granting_body` |
| `regiones[]` | `call.territories[]`; preserve label and map code/level through the official region catalog |
| `sectores[]` | `call.economic_sectors[]` |
| `tiposBeneficiarios[]` | `call.beneficiary_categories[]` |
| `descripcionFinalidad` | `call.purpose.label`; map `code` from the official catalog if captured |
| `fondos[]`, `ayudaEstado`, `urlAyudaEstado`, `reglamento`, `sectoresProductos[]`, `objetivos[]` | matching `call` metadata; preserve source text and nullable codes |
| `fechaInicioSolicitud`, `fechaFinSolicitud`, `textInicio`, `textFin`, `abierto` | matching `application` fields; derive current status only with explicit evidence |
| `sePublicaDiarioOficial` | `application.official_gazette_extract_expected` (preserve raw boolean; it does not mean the extract already exists) |
| `sedeElectronica` | `application.application_portal_url` |
| `urlBasesReguladoras`, `descripcionBasesReguladoras` | `sources.regulatory_bases` |
| `anuncios[]` | `sources.announcements[]` |
| `documentos[]` | `sources.documents[]` |
| Full API response | immutable source snapshot; keep `advertencia` and unrecognized fields in raw payload |

## Persistence and migration direction

The current implementation stores the canonical record as JSONB keyed by `bdns_code`, plus immutable call snapshots keyed by `(bdns_code, payload_sha256)` and change events with changed field paths. It maintains a separate current document inventory keyed by `(bdns_code, bdns_document_id)` and append-only content-version rows keyed by `(bdns_code, bdns_document_id, content_sha256)`; binaries use content-addressed paths. Official links have a current status and retain removed URL records. A changed call reopens its source review state; it does not modify user-facing aid rules. The `Aid` model now carries normalized territories and campaign-specific BDNS references with documents, versions, citations, status and review history. PostgreSQL migrations add queryable `aid_territories`, `aid_bdns_calls` and append-only `aid_review_events`; raw BDNS payload remains in the source-record tables. A link does not promote an aid or source call to verified.

The idempotent schema and versioning policy are implemented in task 2.5; live repeat-import and link-check validation is documented separately.
