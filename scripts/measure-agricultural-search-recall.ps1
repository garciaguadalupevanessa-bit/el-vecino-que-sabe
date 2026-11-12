param(
    [string]$AuditPath = "docs/samples/agricultural-search-audit.json",
    [string]$PanelPath = "docs/samples/agricultural-recall-seed-panel.json",
    [string]$ReportPath = "docs/samples/agricultural-recall-report.md"
)

$ErrorActionPreference = "Stop"
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$audit = Get-Content -LiteralPath $AuditPath -Raw -Encoding UTF8 | ConvertFrom-Json
$panel = Get-Content -LiteralPath $PanelPath -Raw -Encoding UTF8 | ConvertFrom-Json
$candidatesByCode = @{}
foreach ($candidate in $audit.Candidates) {
    $candidatesByCode[[string]$candidate.Code] = $candidate
}

$measured = foreach ($record in $panel.records) {
    $code = [string]$record.bdnsCode
    $candidate = $candidatesByCode[$code]
    [pscustomobject]@{
        Code = $code
        Group = [string]$record.group
        Title = [string]$record.title
        Recovered = ($null -ne $candidate)
        MatchedQueries = if ($candidate) { @($candidate.MatchedQueries) } else { @() }
        SourceUrl = [string]$record.bdnsUrl
    }
}

$groups = @("crop_only", "livestock_only", "mixed")
$groupSummary = foreach ($group in $groups) {
    $items = @($measured | Where-Object { $_.Group -eq $group })
    $hits = @($items | Where-Object Recovered).Count
    [pscustomobject]@{
        Group = $group
        Recovered = $hits
        Total = $items.Count
        Rate = if ($items.Count -gt 0) { [math]::Round(100 * $hits / $items.Count, 1) } else { 0 }
    }
}
$allHits = @($measured | Where-Object Recovered).Count
$retrievedAt = [string]$audit.RetrievedAt
$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("# Agricultural search recall diagnostic")
$lines.Add("")
$lines.Add("- Measured: $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))")
$lines.Add("- Audit snapshot: $retrievedAt; $($audit.CandidateCount) deduplicated candidates from the captured first pages of $($audit.ActiveSearchCount) active searches.")
$lines.Add("- Panel: $($panel.panelVersion), $($panel.records.Count) positive examples located through official BDNS detail pages after the initial audit.")
$lines.Add("- Overall first-page recovery: $allHits/$($measured.Count) ($([math]::Round(100 * $allHits / $measured.Count, 1))%).")
$lines.Add("")
$lines.Add("This purposive panel was assembled after the audit and intentionally includes recovered and missed records, so its rate is selection-biased. It is a descriptive diagnostic, not an independent blind benchmark or statistically representative estimate. The audit captured page 0 only, so a missing code means it was not in the captured first-page union; it does not prove the call is absent from later BDNS search pages. Open-call availability is separate from discovery relevance.")
$lines.Add("")
$lines.Add("## Recovery by holding type")
$lines.Add("")
$lines.Add("| Type | Recovered | Panel | First-page recovery |")
$lines.Add("|---|---:|---:|---:|")
foreach ($row in $groupSummary) {
    $label = switch ($row.Group) {
        "crop_only" { "Crop-only" }
        "livestock_only" { "Livestock-only" }
        "mixed" { "Mixed" }
    }
    $lines.Add("| $label | $($row.Recovered) | $($row.Total) | $($row.Rate)% |")
}
$lines.Add("")
$lines.Add("## Seed results")
$lines.Add("")
$lines.Add("| BDNS | Type | Recovered | Query route(s) | Call | Official record |")
$lines.Add("|---|---|---|---|---|---|")
foreach ($row in $measured) {
    $matched = if ($row.Recovered) { ($row.MatchedQueries -join ", ").Replace('|', '\|') } else { "—" }
    $title = $row.Title.Replace('|', '\|')
    $status = if ($row.Recovered) { "Yes" } else { "No" }
    $lines.Add("| $($row.Code) | $($row.Group) | $status | $matched | $title | [BDNS]($($row.SourceUrl)) |")
}
$lines.Add("")
$lines.Add("## Interpretation")
$lines.Add("")
$lines.Add("The misses show that the current first-page keyword audit is not sufficient as a nationwide collection strategy. Search result truncation and ordering hide relevant calls; relevant older calls may be pushed beyond page 0. The next experiment should paginate or partition by registration date, administration and territory, then run this fixed panel again. A production collector should not treat title-term hits or the agriculture-purpose filter as a complete record of farm aid.")
$lines.Add("")
$lines.Add("Panel selection rules and excluded title-based false positives are documented in [agricultural-recall-seed-panel.json](agricultural-recall-seed-panel.json).")
[System.IO.File]::WriteAllText($ReportPath, ($lines -join "`n") + "`n", $utf8NoBom)

$groupSummary | Format-Table Group, Recovered, Total, Rate -AutoSize
"Overall first-page recovery: $allHits/$($measured.Count) ($([math]::Round(100 * $allHits / $measured.Count, 1))%)"
"Saved report: $ReportPath"
