# AI verification and publication — Manual validation

This flow requires PostgreSQL, `BDNS_REVIEW_TOKEN`, and a configured LLM key. Run from PowerShell in the repository root:

```powershell
docker compose up -d --build backend frontend
```

Open `http://localhost:3000/review`, sign in, and select **Convocatorias**.

1. Select **Aptas para extracción** and choose a call that has a current extraction and a passing quality report.
2. If its extraction queue contains straightforward tasks, open **Extracciones** and press **Revisar automáticamente las tareas claras**. Only a single candidate with a current official citation should close; missing, multiple, conflicting, stale and quality tasks stay open.
3. Return to the accepted call and press **Verificar reglas y publicar con agente**.
4. For a fully cited and machine-evaluable rule set, confirm the response says `published`, names a `bdns_<code>` aid, and reports the rule count. In the result panel, the aid must appear with the label **Verificada automáticamente con agente y fuente oficial**. `check_eligibility` may return `met`, `not_met` or `unknown` by comparing the profile with those exact rules; it must not guarantee a grant.
5. For an incomplete extraction, unsupported profile rule, stale source, unpassed quality report or open task, confirm the agent returns `needs_human_review`, gives a reason, and publishes nothing.
6. Confirm generated aid status, deadline, amount and application steps remain unknown or empty when absent from the official source. Check that its cited rule text links to the official document and page/section.
7. Re-import a changed BDNS source or update a document hash. The automatic verification must reopen, and the published aid must return to extracted/unverified until reprocessed. A subsequent chat request should reflect the database change without restarting the backend.

The finalization history is append-only in `bdns_ai_finalization_events`; verified rules remain in `bdns_call_verification_events`. Do not run PostgreSQL integration tests against the application database: their fixture truncates tables.
