# Aid data correction process

This procedure is for maintainers reviewing a reported issue with an aid, source link, territory, campaign or application deadline.

## Intake

Before public launch, publish one monitored email address, form or issue channel on the service status page. Until then, accept reports only through an explicitly maintained project channel; do not expose a placeholder address.

Ask the reporter for the BDNS code or aid name, the field that appears wrong, the official source URL and (if available) a short explanation. Do not request national ID, bank details, farm account credentials or copies of personal applications.

## Review and correction

1. Record the report date, affected aid/BDNS code, reported field, official source, reviewer and current status in the team's private correction log.
2. Verify the report against the current official source. If the source is unavailable or conflicting, mark the issue pending and do not guess a replacement value.
3. For BDNS source metadata, run the bounded importer and inspect the changed source record. For user-facing requirements, deadlines or steps, require a current official citation and the normal reviewer approval flow.
4. Re-run relevant source quality checks and update the catalog/status page last-updated date.
5. Reply with the decision, the source used and the date. If rejected, explain why plainly and let the reporter provide further evidence.
6. Keep an audit trail of the original value, correction, evidence, reviewer and date. Avoid storing personal data unrelated to the correction.

Suggested statuses: `received`, `under_review`, `corrected`, `not_confirmed`, `declined`.
