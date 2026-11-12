# AI review agent — Manual validation

Run from PowerShell in the project root. The reviewer token and LLM key must already be configured in `.env`; never paste either secret into chat or the validation notes.

```powershell
docker compose up -d --build backend frontend
```

Then open `http://localhost:3000/review`, enter the review token and reviewer name, and filter to an existing run/territory such as run 10 and Aragón.

1. Filter the queue to run 10 and Aragón (or another small set) and note the status and reliability of the first pending records.
2. Click **Procesar hasta 10 con agente**. It makes at most ten LLM requests for that filtered batch; it does not import BDNS data or download new PDFs.
3. Check the summary: clear cases may move to **Aptas para extracción** or **Fuera de alcance**; uncertain cases stay visible for human review; errors are counted separately.
4. Open the cited BDNS fields/documents for the automatically decided cases and check the proposed activity/category evidence. Confidence is informational and is not used as the automatic threshold.
5. Confirm that an accepted call is visible in **Extracciones** as awaiting extraction, and that every automatic result has its citations and reason on its latest AI review record.
6. Confirm the uncertain records remain pending, reliability stays `metadata_only`, no human review is falsely recorded, no confirmed-classification coverage is added automatically, and no public aid is created.
7. Refresh the queue. A changed source hash must invalidate the prior suggestion/decision for current status purposes. Eligibility rules still require their separate verification workflow.

If the BDNS source changes and is re-imported, the old suggestion must no longer appear as current. If the LLM key is missing or provider call fails, the UI should show a safe error and leave that record's review state untouched.
