$ErrorActionPreference = "Stop"

$base = "https://www.infosubvenciones.es/bdnstrans/api"
$sampleDir = Join-Path (Get-Location) "docs\samples"
$outputPath = Join-Path $sampleDir "agricultural-search-audit.json"
$pageSize = 10
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$acuteI = [char]0x00ED
$acuteO = [char]0x00F3
$enye = [char]0x00F1

$terms = @(
    [pscustomobject]@{ Activity = "crop"; Term = "agricultura" },
    [pscustomobject]@{ Activity = "crop"; Term = "agr${acuteI}cola" },
    [pscustomobject]@{ Activity = "crop"; Term = "agraria" },
    [pscustomobject]@{ Activity = "crop"; Term = "agricultor" },
    [pscustomobject]@{ Activity = "crop"; Term = "cultivo" },
    [pscustomobject]@{ Activity = "crop"; Term = "PAC" },
    [pscustomobject]@{ Activity = "crop"; Term = "regad${acuteI}o" },
    [pscustomobject]@{ Activity = "crop"; Term = "vi${enye}edo" },
    [pscustomobject]@{ Activity = "crop"; Term = "hort${acuteI}cola" },
    [pscustomobject]@{ Activity = "crop"; Term = "cereal" },
    [pscustomobject]@{ Activity = "crop"; Term = "frutal" },
    [pscustomobject]@{ Activity = "crop"; Term = "olivar" },
    [pscustomobject]@{ Activity = "crop"; Term = "invernadero" },
    [pscustomobject]@{ Activity = "crop"; Term = "ecol${acuteO}gica" },
    [pscustomobject]@{ Activity = "livestock"; Term = "ganader${acuteI}a" },
    [pscustomobject]@{ Activity = "livestock"; Term = "ganadero" },
    [pscustomobject]@{ Activity = "livestock"; Term = "vacuno" },
    [pscustomobject]@{ Activity = "livestock"; Term = "bovino" },
    [pscustomobject]@{ Activity = "livestock"; Term = "ovino" },
    [pscustomobject]@{ Activity = "livestock"; Term = "caprino" },
    [pscustomobject]@{ Activity = "livestock"; Term = "porcino" },
    [pscustomobject]@{ Activity = "livestock"; Term = "ap${acuteI}cola" },
    [pscustomobject]@{ Activity = "livestock"; Term = "av${acuteI}cola" },
    [pscustomobject]@{ Activity = "livestock"; Term = "equino" },
    [pscustomobject]@{ Activity = "livestock"; Term = "pastos" },
    [pscustomobject]@{ Activity = "livestock"; Term = "extensiva" },
    [pscustomobject]@{ Activity = "livestock"; Term = "raza" },
    [pscustomobject]@{ Activity = "livestock"; Term = "sanidad" },
    [pscustomobject]@{ Activity = "livestock"; Term = "bienestar" },
    [pscustomobject]@{ Activity = "livestock"; Term = "leche" },
    [pscustomobject]@{ Activity = "crop"; Term = "frut${acuteI}cola" }
)

New-Item -ItemType Directory -Force -Path $sampleDir | Out-Null
$purposeCatalog = Invoke-RestMethod -Uri "$base/finalidades?vpd=GE" -TimeoutSec 30
$purposeCatalog | ConvertTo-Json -Depth 10 | ForEach-Object { [System.IO.File]::WriteAllText((Join-Path $sampleDir "bdns-finalities.json"), $_, $utf8NoBom) }
$agriculturePurposes = @($purposeCatalog | Where-Object { $_.descripcion -like "AGRICULTURA, PESCA Y ALIMENTACI*" })
if ($agriculturePurposes.Count -ne 1) {
    throw "Expected one agriculture purpose in the BDNS finality catalog; found $($agriculturePurposes.Count)."
}
$agriculturePurposeId = $agriculturePurposes[0].id
$queryResults = @()
$candidateRows = @()
$queryIndex = 1
$queryCount = $terms.Count + 1

foreach ($term in $terms) {
    if ($queryIndex -gt 0) {
        Start-Sleep -Seconds 1
    }
    $queryIndex++

    $encodedTerm = [uri]::EscapeDataString($term.Term)
    $url = "$base/convocatorias/busqueda?page=0&pageSize=$pageSize&descripcion=$encodedTerm&descripcionTipoBusqueda=2&vpd=GE"
    try {
        $response = Invoke-RestMethod -Uri $url -TimeoutSec 30
        $queryResults += [pscustomobject]@{
            Activity = $term.Activity
            Term = $term.Term
            Status = "OK"
            ResultsOnPage = $response.numberOfElements
            TotalMatches = $response.totalElements
            PageSize = $response.size
            Truncated = ($response.totalElements -gt $response.size)
        }

        foreach ($call in $response.content) {
            $code = [string]$call.numeroConvocatoria
            $key = if ($code) { "BDNS:$code" } else { "ID:$($call.id)" }
            $candidateRows += [pscustomobject]@{
                Key = $key
                Code = $call.numeroConvocatoria
                InternalId = $call.id
                ReceivedDate = $call.fechaRecepcion
                Administration = $call.nivel1
                TerritoryOrBody = $call.nivel2
                Title = ([string]$call.descripcion).Substring(0, [Math]::Min(140, ([string]$call.descripcion).Length))
                Activity = $term.Activity
                MatchedTerm = $term.Term
            }
        }
    }
    catch {
        $queryResults += [pscustomobject]@{
            Activity = $term.Activity
            Term = $term.Term
            Status = "ERROR: $($_.Exception.Message)"
            ResultsOnPage = $null
            TotalMatches = $null
            PageSize = $pageSize
            Truncated = $null
        }
    }
}

Start-Sleep -Seconds 1
$purposeUrl = "$base/convocatorias/busqueda?page=0&pageSize=$pageSize&finalidad=$agriculturePurposeId&vpd=GE"
try {
    $response = Invoke-RestMethod -Uri $purposeUrl -TimeoutSec 30
    $queryResults += [pscustomobject]@{
        Activity = "purpose"
        Term = "finalidad=$agriculturePurposeId"
        Status = "OK"
        ResultsOnPage = $response.numberOfElements
        TotalMatches = $response.totalElements
        PageSize = $response.size
        Truncated = ($response.totalElements -gt $response.size)
    }

    foreach ($call in $response.content) {
        $code = [string]$call.numeroConvocatoria
        $key = if ($code) { "BDNS:$code" } else { "ID:$($call.id)" }
        $candidateRows += [pscustomobject]@{
            Key = $key
            Code = $call.numeroConvocatoria
            InternalId = $call.id
            ReceivedDate = $call.fechaRecepcion
            Administration = $call.nivel1
            TerritoryOrBody = $call.nivel2
            Title = ([string]$call.descripcion).Substring(0, [Math]::Min(140, ([string]$call.descripcion).Length))
            Activity = "purpose"
            MatchedTerm = "finalidad=$agriculturePurposeId"
        }
    }
}
catch {
    $queryResults += [pscustomobject]@{
        Activity = "purpose"
        Term = "finalidad=$agriculturePurposeId"
        Status = "ERROR: $($_.Exception.Message)"
        ResultsOnPage = $null
        TotalMatches = $null
        PageSize = $pageSize
        Truncated = $null
    }
}

$candidates = @(
    $candidateRows |
        Group-Object Key |
        ForEach-Object {
            $first = $_.Group[0]
            [pscustomobject]@{
                Code = $first.Code
                InternalId = $first.InternalId
                ReceivedDate = $first.ReceivedDate
                Administration = $first.Administration
                TerritoryOrBody = $first.TerritoryOrBody
                Title = $first.Title
                MatchedQueries = @($_.Group | ForEach-Object { "$($_.Activity):$($_.MatchedTerm)" } | Sort-Object -Unique)
            }
        }
)

$audit = [pscustomobject]@{
    RetrievedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    Endpoint = "$base/convocatorias/busqueda"
    PageSize = $pageSize
    SearchScope = "Nationwide; no territory or administration filter"
    QueryCount = $queryCount
    CatalogRequestCount = 1
    TotalApiRequestCount = ($queryCount + 1)
    AgriculturePurposeId = $agriculturePurposeId
    Notes = @(
        "The endpoint has no direct sector filter; titles and the purpose filter are discovery routes, not an agricultural gold standard.",
        "Only page 0 is captured for each query. Truncated queries require more pages for candidate collection.",
        "Review candidate details and create a manually checked positive seed panel before calculating recall."
    )
    Queries = $queryResults
    CandidateCount = $candidates.Count
    Candidates = $candidates
}

$json = $audit | ConvertTo-Json -Depth 12
[System.IO.File]::WriteAllText($outputPath, $json, $utf8NoBom)

$queryResults | Format-Table Activity, Term, Status, ResultsOnPage, TotalMatches, Truncated -AutoSize
"Unique candidates on captured first pages: $($candidates.Count)"
"Saved: $outputPath"
