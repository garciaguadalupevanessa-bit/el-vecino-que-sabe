param([switch]$Refresh)

$ErrorActionPreference = "Stop"

$base = "https://www.infosubvenciones.es/bdnstrans/api"
$sampleDir = Join-Path (Get-Location) "docs\samples"
$auditPath = Join-Path $sampleDir "agricultural-search-audit.json"
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$latin1 = [System.Text.Encoding]::GetEncoding(28591)
$utf8 = [System.Text.Encoding]::UTF8
$mojibakeMarkers = [char[]]@([char]0x00C3, [char]0x00C2, [char]0x00E2)
$acuteI = [char]0x00ED

function Repair-TextEncoding {
    param([Parameter(Mandatory = $false)]$Value)

    if ($null -eq $Value) {
        return $null
    }
    if ($Value -is [string]) {
        if ($Value.IndexOfAny($mojibakeMarkers) -ge 0) {
            return $utf8.GetString($latin1.GetBytes($Value))
        }
        return $Value
    }
    if ($Value -is [System.Array]) {
        $items = foreach ($item in $Value) {
            Repair-TextEncoding -Value $item
        }
        return ,@($items)
    }
    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        foreach ($property in $Value.PSObject.Properties) {
            $property.Value = Repair-TextEncoding -Value $property.Value
        }
    }
    return $Value
}

function Save-JsonSample {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Value
    )

    $normalized = Repair-TextEncoding -Value $Value
    $json = $normalized | ConvertTo-Json -Depth 30
    [System.IO.File]::WriteAllText((Join-Path $sampleDir $Name), $json, $utf8NoBom)
    return $normalized
}

function Get-ApiJsonSample {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Uri
    )

    $path = Join-Path $sampleDir $Name
    if (!$Refresh -and (Test-Path -LiteralPath $path)) {
        return (Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json)
    }
    return (Invoke-RestMethod -Uri $Uri -TimeoutSec 30)
}

if (!(Test-Path -LiteralPath $auditPath)) {
    throw "Run probe-agricultural-search-coverage.ps1 first; audit file not found: $auditPath"
}

$audit = Get-Content -LiteralPath $auditPath -Raw -Encoding UTF8 | ConvertFrom-Json
$audit = Repair-TextEncoding -Value $audit
$catalog = Get-ApiJsonSample -Name "bdns-finalities.json" -Uri "$base/finalidades?vpd=GE"
$catalog = Save-JsonSample -Name "bdns-finalities.json" -Value $catalog
$agriculturePurpose = @($catalog | Where-Object { $_.descripcion -like "AGRICULTURA, PESCA Y ALIMENTACI*" })
if ($agriculturePurpose.Count -ne 1) {
    throw "Expected one agriculture purpose in the BDNS catalog; found $($agriculturePurpose.Count)."
}
$purposeId = $agriculturePurpose[0].id

$purposeResponse = Get-ApiJsonSample -Name "agricultural-purpose-search.json" -Uri "$base/convocatorias/busqueda?page=0&pageSize=10&finalidad=$purposeId&vpd=GE"
$purposeResponse = Save-JsonSample -Name "agricultural-purpose-search.json" -Value $purposeResponse

$fruitTerm = "frut${acuteI}cola"
$encodedFruitTerm = [uri]::EscapeDataString($fruitTerm)
$fruitResponse = Get-ApiJsonSample -Name "crop-fruticola-search.json" -Uri "$base/convocatorias/busqueda?page=0&pageSize=10&descripcion=$encodedFruitTerm&descripcionTipoBusqueda=2&vpd=GE"
$fruitResponse = Save-JsonSample -Name "crop-fruticola-search.json" -Value $fruitResponse

# Exclude the unverified purpose=11 results and the misspelled zero-result term from the active candidate set.
$cleanCandidates = foreach ($candidate in $audit.Candidates) {
    $cleanTags = @($candidate.MatchedQueries | Where-Object {
        $_ -ne "purpose:finalidad=11" -and $_ -ne "purpose:finalidad=$purposeId" -and -not ($_.StartsWith("crop:frut") -and $_ -ne "crop:frutal")
    })
    if ($cleanTags.Count -gt 0) {
        $candidate.MatchedQueries = $cleanTags
        $candidate
    }
}
$audit.Candidates = @($cleanCandidates)

$oldPurposeQuery = $audit.Queries | Where-Object { $_.Term -eq "finalidad=11" } | Select-Object -First 1
if ($oldPurposeQuery) {
    $oldPurposeQuery.Status = "SUPERSEDED: not the agriculture category; excluded from candidate set"
}
$oldMisspelledTerm = $audit.Queries | Where-Object {
    $_.Activity -eq "crop" -and $_.Term.StartsWith("frut") -and $_.TotalMatches -eq 0
} | Select-Object -First 1
if ($oldMisspelledTerm) {
    $oldMisspelledTerm.Status = "SUPERSEDED: misspelled term; corrected query saved separately"
}
$audit.Queries = @($audit.Queries | Where-Object { $_.Term -ne "finalidad=$purposeId" -and $_.Term -ne $fruitTerm })

$newQueryData = @(
    [pscustomobject]@{
        Activity = "purpose"
        Term = "finalidad=$purposeId"
        Response = $purposeResponse
        MatchedQuery = "purpose:finalidad=$purposeId"
    },
    [pscustomobject]@{
        Activity = "crop"
        Term = $fruitTerm
        Response = $fruitResponse
        MatchedQuery = "crop:$fruitTerm"
    }
)

foreach ($query in $newQueryData) {
    $response = $query.Response
    $audit.Queries += [pscustomobject]@{
        Activity = $query.Activity
        Term = $query.Term
        Status = "OK"
        ResultsOnPage = $response.numberOfElements
        TotalMatches = $response.totalElements
        PageSize = $response.size
        Truncated = ($response.totalElements -gt $response.size)
    }

    foreach ($call in $response.content) {
        $code = [string]$call.numeroConvocatoria
        $existing = @($audit.Candidates | Where-Object { $_.Code -eq $code }) | Select-Object -First 1
        if ($existing) {
            $existing.MatchedQueries = @($existing.MatchedQueries + $query.MatchedQuery | Sort-Object -Unique)
        }
        else {
            $audit.Candidates = @($audit.Candidates) + [pscustomobject]@{
                Code = $call.numeroConvocatoria
                InternalId = $call.id
                ReceivedDate = $call.fechaRecepcion
                Administration = $call.nivel1
                TerritoryOrBody = $call.nivel2
                Title = ([string]$call.descripcion).Substring(0, [Math]::Min(140, ([string]$call.descripcion).Length))
                MatchedQueries = @($query.MatchedQuery)
            }
        }
    }
}

$audit.QueryCount = $audit.Queries.Count
$audit | Add-Member -MemberType NoteProperty -Name ActiveSearchCount -Value @($audit.Queries | Where-Object { $_.Status -eq "OK" }).Count -Force
$audit | Add-Member -MemberType NoteProperty -Name CatalogRequestCount -Value 1 -Force
$audit | Add-Member -MemberType NoteProperty -Name TotalApiRequestCount -Value ($audit.QueryCount + 1) -Force
$audit | Add-Member -MemberType NoteProperty -Name AgriculturePurposeId -Value $purposeId -Force
$audit.CandidateCount = $audit.Candidates.Count
$noteOne = "The finality catalog identifies agriculture as ID $purposeId. The earlier finalidad=11 query and misspelled fruit term are retained in query history as superseded and excluded from active candidates."
$noteTwo = "The corrected agriculture-purpose and fruticola responses were captured with pageSize=10; candidate results remain first-page-only and are not a recall denominator."
if ($audit.Notes -notcontains $noteOne) { $audit.Notes += $noteOne }
if ($audit.Notes -notcontains $noteTwo) { $audit.Notes += $noteTwo }
$audit = Save-JsonSample -Name "agricultural-search-audit.json" -Value $audit

@(
    [pscustomobject]@{ Query = "finalidad=$purposeId"; ResultsOnPage = $purposeResponse.numberOfElements; TotalMatches = $purposeResponse.totalElements; Truncated = ($purposeResponse.totalElements -gt $purposeResponse.size) },
    [pscustomobject]@{ Query = $fruitTerm; ResultsOnPage = $fruitResponse.numberOfElements; TotalMatches = $fruitResponse.totalElements; Truncated = ($fruitResponse.totalElements -gt $fruitResponse.size) }
) | Format-Table -AutoSize
"Agriculture purpose ID: $purposeId"
"Active candidates after correction: $($audit.CandidateCount)"
"Saved corrected audit: $auditPath"
