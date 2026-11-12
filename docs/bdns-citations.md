# BDNS task 3.2 — Per-fact citations

Every candidate emitted by extractor version `1.1` includes a `citation` object stored with that fact in the append-only `bdns_extractions.data` JSONB record.

```json
{
  "url": "https://www.infosubvenciones.es/bdnstrans/api/convocatorias/documentos?idDocumento=1512984",
  "page": 7,
  "section": null,
  "quote": "...texto literal de contexto..."
}
```

PDF-derived candidates cite the official BDNS document download URL, a one-based page number and the bounded extracted excerpt. Metadata-derived candidates cite the official BDNS call detail URL and a stable canonical field path, such as `application.end_date` or `call.beneficiary_categories[0]`. Their `page` is null and the `quote` contains the cited source value.

The document URL is a file-download endpoint. BDNS may serve it as `application/octet-stream`, so a browser can download the file instead of displaying it inline. The reviewer interface labels this action as a document download; the neighboring call-detail link opens the human-readable BDNS record. For call `923754`, document `1512984` was read as a 42-page PDF by the extractor, so the direct endpoint's download behavior does not mean the stored source was empty.

In `/review` → **Extracciones**, PDF citations now use the protected backend download route instead of navigating directly to BDNS. The backend confirms the document ID is listed on the referenced call, fetches it through the bounded BDNS client (which checks the PDF signature and size limit), and responds as `application/pdf` with a `.pdf` attachment filename. The browser client saves it as `bdns-<call>-<document>.pdf`. Metadata citations continue to open the human-readable call detail page.

The extractor omits a candidate if it cannot provide a valid HTTP(S) source URL and a page or section locator. PDF text extraction also requires the document's official download URL. This keeps uncited values out of the extracted-facts store. These references support traceability; they do not establish that the candidate was interpreted correctly or that the aid is verified.

The citation is stored inside each fact rather than in a separate table, so it is returned with the fact by the protected endpoint `GET /api/admin/bdns/extractions/{bdns_code}`. Extractor version `1.1` also changes the source fingerprint; prior version `1.0` outputs remain intact, and rerunning the extractor creates a new immutable result with citations.

To inspect or audit citation completeness in Postgres:

```sql
WITH latest AS (
  SELECT data FROM bdns_extractions
  WHERE bdns_code = '923754'
  ORDER BY created_at DESC, source_fingerprint DESC
  LIMIT 1
)
SELECT field.key AS field, count(*) AS facts,
       count(*) FILTER (WHERE fact.value ? 'citation'
                         AND fact.value->'citation'->>'url' IS NOT NULL
                         AND (fact.value->'citation'->>'page' IS NOT NULL
                              OR fact.value->'citation'->>'section' IS NOT NULL)) AS cited
FROM latest e
CROSS JOIN LATERAL jsonb_each(e.data->'facts') AS field(key, value)
CROSS JOIN LATERAL jsonb_array_elements(field.value) AS fact(value)
GROUP BY field.key
ORDER BY field.key;
```

## Validation

From `backend`:

```powershell
python -m pytest -q tests\test_bdns_extraction.py tests\test_review_api.py
```

After rebuilding the backend, rerun a previously accepted call such as `923754` to write version `1.1` output. Confirm that the protected extraction endpoint returns citations and that each stored fact has a URL plus page or section. The existing source call must remain `metadata_only`.

**Validation completed:** focused Docker tests passed (11 passed, one cache-permission warning). The user reran extraction version `1.1` for call `923754`; the database audit reported matching fact/citation counts for application route (10), beneficiaries (10), deadlines (19), documents (15), purpose (24) and requirements (22). The source call remained `metadata_only`.
