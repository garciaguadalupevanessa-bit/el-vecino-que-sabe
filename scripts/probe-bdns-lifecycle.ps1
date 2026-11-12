param(
    [string]$OutputPath = "docs/samples/bdns-lifecycle-probe.json",
    [string]$ReportPath = "docs/bdns-lifecycle-probe.md"
)

$ErrorActionPreference = "Stop"
$base = "https://www.infosubvenciones.es/bdnstrans/api"
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$latin1 = [System.Text.Encoding]::GetEncoding(28591)
$utf8 = [System.Text.Encoding]::UTF8
$encodingMarkers = [char[]]@([char]0x00C3, [char]0x00C2, [char]0x00E2)
$outputDirectory = Split-Path -Parent $OutputPath
if ($outputDirectory) { New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null }
$reportDirectory = Split-Path -Parent $ReportPath
if ($reportDirectory) { New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null }

function Get-Detail {
    param([Parameter(Mandatory = $true)][string]$Code)
    $value = Invoke-RestMethod -Uri "$base/convocatorias?numConv=$Code&vpd=GE" -TimeoutSec 30
    Repair-ApiEncoding -Value $value
}

function Get-CallCodeFromSearch {
    param(
        [Parameter(Mandatory = $true)][string]$Code,
        [Parameter(Mandatory = $true)][string]$From,
        [Parameter(Mandatory = $true)][string]$To
    )
    $fromEncoded = [uri]::EscapeDataString($From)
    $toEncoded = [uri]::EscapeDataString($To)
    $uri = "$base/convocatorias/busqueda?page=0&pageSize=50&numeroConvocatoria=$Code&fechaDesde=$fromEncoded&fechaHasta=$toEncoded&vpd=GE"
    $value = Invoke-RestMethod -Uri $uri -TimeoutSec 30
    Repair-ApiEncoding -Value $value
}

function Repair-ApiEncoding {
    param($Value)
    if ($null -eq $Value) { return $null }
    if ($Value -is [string]) {
        $text = $Value
        for ($attempt = 0; $attempt -lt 2 -and $text.IndexOfAny($encodingMarkers) -ge 0; $attempt++) {
            $text = $utf8.GetString($latin1.GetBytes($text))
        }
        return $text
    }
    if ($Value -is [System.Array]) {
        $items = foreach ($item in $Value) { Repair-ApiEncoding -Value $item }
        return ,@($items)
    }
    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        foreach ($property in $Value.PSObject.Properties) {
            $property.Value = Repair-ApiEncoding -Value $property.Value
        }
    }
    return $Value
}

function Save-Json {
    param([string]$Path, $Value)
    $normalized = Repair-ApiEncoding -Value $Value
    $json = $normalized | ConvertTo-Json -Depth 30
    [System.IO.File]::WriteAllText((Join-Path (Get-Location) $Path), $json, $utf8NoBom)
}

function Get-CollectionCount {
    param($Value)
    if ($null -eq $Value) { return 0 }
    return @($Value).Count
}

# The Aragón detail sample reports fechaRecepcion 2026-07-22. The exact-day and
# next-day queries isolate whether the API date window includes that receipt date.
$dateSource = Get-Content -LiteralPath "docs/samples/aragon-detail.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$code = [string]$dateSource.codigoBDNS
$receiptDate = [datetime]::ParseExact([string]$dateSource.fechaRecepcion, "yyyy-MM-dd", [Globalization.CultureInfo]::InvariantCulture)
$expectedDay = $receiptDate.ToString("dd/MM/yyyy", [Globalization.CultureInfo]::InvariantCulture)
$nextDay = $receiptDate.AddDays(1).ToString("dd/MM/yyyy", [Globalization.CultureInfo]::InvariantCulture)

$sameDay = Get-CallCodeFromSearch -Code $code -From $expectedDay -To $expectedDay
Start-Sleep -Seconds 1
$nextDayOnly = Get-CallCodeFromSearch -Code $code -From $nextDay -To $nextDay
$sameDayCodes = @($sameDay.content | ForEach-Object { [string]$_.numeroConvocatoria })
$nextDayCodes = @($nextDayOnly.content | ForEach-Object { [string]$_.numeroConvocatoria })

$details = @()
foreach ($callCode in @("811615", "938663", "909993", $code)) {
    Start-Sleep -Seconds 1
    $details += Get-Detail -Code $callCode
}
$amendmentCall = @($details | Where-Object { [string]$_.codigoBDNS -eq "811615" })[0]
$noBulletinCalls = @($details | Where-Object { $_.sePublicaDiarioOficial -eq $false -or (Get-CollectionCount $_.anuncios) -eq 0 })

$knownOfficialHosts = @("doe.juntaex.es", "dogv.gva.es", "www.boe.es", "boe.es")
$links = @()
foreach ($detail in $details) {
    if ($detail.urlBasesReguladoras) {
        $links += [pscustomobject]@{ CallCode = [string]$detail.codigoBDNS; Kind = "regulatory_bases"; Url = [string]$detail.urlBasesReguladoras }
    }
    foreach ($announcement in @($detail.anuncios)) {
        if ($announcement.url) {
            $links += [pscustomobject]@{ CallCode = [string]$detail.codigoBDNS; Kind = "official_gazette_announcement"; Url = [string]$announcement.url }
        }
    }
}
$uniqueLinks = @($links | Sort-Object Url -Unique)
$linkChecks = @()
foreach ($link in $uniqueLinks) {
    $uri = $null
    $absolute = [uri]::TryCreate($link.Url, [UriKind]::Absolute, [ref]$uri)
    $hostAllowed = $absolute -and ($knownOfficialHosts -contains $uri.Host.ToLowerInvariant())
    $statusCode = $null
    $statusText = if (!$absolute) { "invalid_or_relative_url" } elseif (!$hostAllowed) { "host_not_in_probe_allowlist" } else { "not_checked" }
    if ($hostAllowed) {
        try {
            $response = Invoke-WebRequest -Uri $link.Url -Method Head -TimeoutSec 25 -UseBasicParsing
            $statusCode = [int]$response.StatusCode
            $statusText = "HEAD succeeded"
        }
        catch {
            if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
                $statusCode = [int]$_.Exception.Response.StatusCode
                $statusText = "HEAD returned HTTP error"
            }
            else {
                $statusText = "HEAD failed: $($_.Exception.Message)"
            }
        }
    }
    $linkChecks += [pscustomobject]@{
        CallCode = $link.CallCode
        Kind = $link.Kind
        Url = $link.Url
        Host = if ($absolute) { $uri.Host } else { $null }
        Absolute = $absolute
        HostInAllowlist = $hostAllowed
        HttpStatus = $statusCode
        Check = $statusText
    }
    Start-Sleep -Seconds 1
}

$amendmentItems = @($amendmentCall.anuncios | Where-Object { ("$($_.titulo) $($_.textoLeng) $($_.desDiarioOficial)") -match "(?i)modific|ampl[ií]|pr[oó]rrog" })
$amendmentTitle = if ($amendmentItems.Count -gt 0) { [string]$amendmentItems[0].titulo } else { "No amendment title matched the review terms." }
$amendmentDate = if ($amendmentItems.Count -gt 0) { [string]$amendmentItems[0].datPublicacion } else { "unknown" }
$summary = [pscustomobject]@{
    RetrievedAtUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    ApiBase = $base
    DateFilterProbe = [pscustomobject]@{
        CallCode = $code
        DetailReceiptDate = [string]$dateSource.fechaRecepcion
        SameDayRange = $expectedDay
        SameDayReturnedCall = ($sameDayCodes -contains $code)
        SameDayTotalElements = $sameDay.totalElements
        NextDayRange = $nextDay
        NextDayReturnedCall = ($nextDayCodes -contains $code)
        NextDayTotalElements = $nextDayOnly.totalElements
        Interpretation = "A same-day hit and next-day miss support that fechaDesde/fechaHasta filter the call's BDNS receipt/registration date for this record; they do not establish semantics for all records or time boundaries."
    }
    AmendmentProbe = [pscustomobject]@{
        CallCode = [string]$amendmentCall.codigoBDNS
        Title = [string]$amendmentCall.descripcion
        AnnouncementCount = (Get-CollectionCount $amendmentCall.anuncios)
        MatchingAmendmentAnnouncements = $amendmentItems
        Documents = @($amendmentCall.documentos | Select-Object id,nombreFic,descripcion,long,datPublicacion,datMod)
    }
    NoBulletinProbe = @($noBulletinCalls | ForEach-Object {
        [pscustomobject]@{
            CallCode = [string]$_.codigoBDNS
            Title = [string]$_.descripcion
            SaysOfficialExtract = $_.sePublicaDiarioOficial
            AnnouncementCount = (Get-CollectionCount $_.anuncios)
            BasesUrl = $_.urlBasesReguladoras
            DocumentCount = (Get-CollectionCount $_.documentos)
        }
    })
    SourceLinks = $linkChecks
    DetailSnapshots = $details
}

Save-Json -Path $OutputPath -Value $summary

$report = [System.Collections.Generic.List[string]]::new()
$report.Add("# BDNS date, amendment and source-link probe")
$report.Add("")
$report.Add("Captured: $($summary.RetrievedAtUtc)")
$report.Add("")
$report.Add("## Date-window result")
$report.Add("")
$report.Add("- BDNS $code has fechaRecepcion=$($dateSource.fechaRecepcion) in the saved detail sample.")
$report.Add("- Exact same-day range ($expectedDay) returned the call: $($summary.DateFilterProbe.SameDayReturnedCall) (total $($sameDay.totalElements)).")
$report.Add("- Next-day-only range ($nextDay) returned the call: $($summary.DateFilterProbe.NextDayReturnedCall) (total $($nextDayOnly.totalElements)).")
$report.Add("- This is a single-record semantics probe, not proof of every edge case. Keep both the original date text and parsed date; do not interpret it as an application deadline.")
$report.Add("")
$report.Add("## Amendments and no-extract calls")
$report.Add("")
$report.Add("- BDNS 811615 returned $($summary.AmendmentProbe.AnnouncementCount) official announcement records. The amendment search found $($amendmentItems.Count) record(s); publication date: $amendmentDate. Title: $amendmentTitle")
$report.Add("- Inspect the saved announcement text and linked gazette notice for the legal change and effective deadline; do not infer those details from the title alone.")
$report.Add("- The no-bulletin probe found $($summary.NoBulletinProbe.Count) detail records with sePublicaDiarioOficial=false or no announcement records. Such a record can still include bases or documents; absence of an extract must not be represented as an open call.")
$report.Add("- A direct source link is evidence to inspect the underlying text; it is not, by itself, proof of current availability or eligibility.")
$report.Add("")
$report.Add("## Official source-link checks")
$report.Add("")
$report.Add("| BDNS | Link type | Host | Absolute URL | HTTP HEAD | URL |")
$report.Add("|---|---|---|---|---|---|")
foreach ($link in $linkChecks) {
    $safeUrl = $link.Url.Replace('|', '\|')
    $report.Add("| $($link.CallCode) | $($link.Kind) | $($link.Host) | $($link.Absolute) | $($link.Check) | $safeUrl |")
}
$report.Add("")
$report.Add("All requests are HEAD checks against the explicit allowlist. HEAD failures can reflect server policy; confirm a failing link in a browser or with a bounded GET before treating it as broken.")
[System.IO.File]::WriteAllText((Join-Path (Get-Location) $ReportPath), ($report -join "`n") + "`n", $utf8NoBom)

[pscustomobject]@{ Probe = "same day"; CodeReturned = $summary.DateFilterProbe.SameDayReturnedCall; Total = $sameDay.totalElements },
[pscustomobject]@{ Probe = "next day only"; CodeReturned = $summary.DateFilterProbe.NextDayReturnedCall; Total = $nextDayOnly.totalElements },
[pscustomobject]@{ Probe = "amendment matches"; CodeReturned = ($amendmentItems.Count -gt 0); Total = $amendmentItems.Count },
[pscustomobject]@{ Probe = "no-extract detail records"; CodeReturned = ($noBulletinCalls.Count -gt 0); Total = $noBulletinCalls.Count } | Format-Table -AutoSize
"Saved JSON: $OutputPath"
"Saved report: $ReportPath"
