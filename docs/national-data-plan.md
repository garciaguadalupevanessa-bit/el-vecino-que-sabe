# Nationwide agricultural aid data plan

## Agreed product scope

The product covers all of Spain: national, autonomous-community, autonomous-city and relevant local calls for agricultural, livestock and mixed farms. Aragón is an initial end-to-end validation case only; it is not the launch boundary. The product must show users how complete and recently checked coverage is for their territory.

## Source and automation

Use BDNS/SNPSAP as the primary nationwide discovery and ingestion source. Its public API supports searching convocatorias and retrieving their documents. Use the BDNS identifier to track the call and its revisions. Download the call text and linked bases, annexes and amendments when available.

Automation should:

1. Query and classify calls across national, regional and local authorities, using sector, purpose, region, beneficiary and text fields where available.
2. Save the BDNS record, stable identifier, timestamps, source URLs, and document inventory.
3. Extract candidate eligibility criteria, application dates, beneficiary categories and procedure links from the registered metadata and documents. Keep the page or document references for every extracted fact.
4. Check that links resolve, files are readable, required fields are present, dates are well formed, and document versions or hashes have changed.
5. Recheck indexed records on a schedule and mark changed, expired or incomplete records for review.

Automated extraction is a proposal, not a verification result. A deterministic eligibility result can be definitive only after the source text has been reviewed or a rigorously validated rule set has been approved. Human review should focus on ambiguous rules, missing or conflicting documents and high-impact changes rather than rechecking every unchanged field manually.

## When another public page is needed

Do not duplicate every regional catalog. Follow BDNS links to the official gazette or agency only when a document is missing, a linked file is inaccessible, an amendment needs confirmation, the application channel is unclear, or the record conflicts with the source text. For canonical calls, preserve the official-gazette publication reference. Instrumental/direct-aid calls may rely on their legal instrument rather than a published extract.

## Initial nationwide categories

- CAP direct payments and coupled support for eligible crops and livestock.
- Young farmer establishment and farm modernization.
- Agro-environment, organic production and natural-constraint measures.
- Agricultural insurance.
- Livestock health, extensive systems and native breeds.
- Regional or local emergency aid and farm investment calls.

These are discovery categories, not a claim that every region has equal coverage or that every listed call is currently open.

## Record and coverage fields

The canonical BDNS `convocatoria` record, mapping and reliability rules are defined in [`bdns-call-record-schema.md`](bdns-call-record-schema.md). It remains a separate source record, linked to user-facing aids through campaign-specific BDNS references. Aid records can carry several territories, source documents and versions, citations, status and review history; the database keeps the territory/source links and review events queryable.

For each call, capture: BDNS identifier; official name; administration and granting body; territory (national, autonomous community, province or municipality); activity (agriculture, livestock or both); aid category; campaign; beneficiary types; requirements with document/page references; documents; application channel; opening and closing dates; status; official source URLs; retrieval time; last-change time; reliability; reviewer and review date.

Measure coverage separately by autonomous community, province, activity and aid category. Publish “coverage not yet checked” where indexing has not been audited. Do not infer nationwide completeness from the fact that BDNS is a national registry.

The initial operational matrix is [`national-coverage-matrix.csv`](national-coverage-matrix.csv), with its status definitions and reconciliation guidance in [`national-coverage-matrix.md`](national-coverage-matrix.md). It includes all 17 autonomous communities, both autonomous cities, the 50 provinces and national scope. Relevant municipalities are added as they are identified from official calls; their absence from the initial register does not mean they have been checked.

## Quality states

- `metadata_only`: source identity and basic call metadata only; do not evaluate requirements.
- `extracted`: facts were automatically extracted but have not passed substantive review; eligibility stays unknown.
- `verified`: official text was checked, a named reviewer approved the rules, and the review date is recorded. Relevant document changes invalidate or reopen that review.

Phase 1 verified the documented search parameters, pagination, detail/document shape and bounded live endpoint behavior. The importer still needs to implement and validate its own retry, overlap, idempotency and change-detection behavior; these checks do not establish complete nationwide coverage or a published request quota. No production live integration is claimed yet.
