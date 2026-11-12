$ErrorActionPreference = "Stop"

$base = "https://www.infosubvenciones.es/bdnstrans/api"
$sampleDir = Join-Path (Get-Location) "docs\samples"
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
New-Item -ItemType Directory -Force -Path $sampleDir | Out-Null

function Save-JsonSample {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Value
    )

    $path = Join-Path $sampleDir $Name
    $json = $Value | ConvertTo-Json -Depth 30
    [System.IO.File]::WriteAllText($path, $json, $utf8NoBom)
}

$queries = @(
    [pscustomobject]@{
        Name = "comma-separated"
        File = "aragon-regions-comma.json"
        Url = "$base/convocatorias/busqueda?page=0&pageSize=2&descripcion=agricultura&descripcionTipoBusqueda=2&regiones=22,23&vpd=GE"
    },
    [pscustomobject]@{
        Name = "repeated-parameter"
        File = "aragon-regions-repeated.json"
        Url = "$base/convocatorias/busqueda?page=0&pageSize=2&descripcion=agricultura&descripcionTipoBusqueda=2&regiones=22&regiones=23&vpd=GE"
    }
)

$results = @()
for ($index = 0; $index -lt $queries.Count; $index++) {
    if ($index -gt 0) {
        Start-Sleep -Seconds 1
    }

    $query = $queries[$index]
    try {
        $response = Invoke-RestMethod -Uri $query.Url -TimeoutSec 30
        Save-JsonSample -Name $query.File -Value $response
        $results += [pscustomobject]@{
            Encoding = $query.Name
            Status = "OK"
            ResultsOnPage = $response.numberOfElements
            TotalResults = $response.totalElements
            FirstCallCodes = ($response.content | ForEach-Object { $_.numeroConvocatoria }) -join ","
            Sample = Join-Path "docs\samples" $query.File
        }
    }
    catch {
        $results += [pscustomobject]@{
            Encoding = $query.Name
            Status = "ERROR: $($_.Exception.Message)"
            ResultsOnPage = $null
            TotalResults = $null
            FirstCallCodes = ""
            Sample = ""
        }
    }
}

$results | Format-Table -AutoSize
