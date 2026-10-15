param(
    [string]$Sectors = "el-millon",

    [int]$Limit = 5,

    [double]$DelaySeconds = 3,

    [switch]$Commit
)

$ErrorActionPreference = "Stop"

$projectRoot = (
    Resolve-Path (
        Join-Path $PSScriptRoot ".."
    )
).Path

$pythonPath = Join-Path `
    $projectRoot `
    ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "No se encontró Python en .venv."
}

Set-Location $projectRoot

$sectorCount = @(
    $Sectors.Split(",") |
    Where-Object { $_.Trim() }
).Count

$extractionLimit = $Limit * $sectorCount

Write-Host ""
Write-Host "1. Descubriendo URLs actuales..."

& $pythonPath `
    "Scraping\discover_target_urls.py" `
    "--sectors" $Sectors `
    "--limit" $Limit

if ($LASTEXITCODE -ne 0) {
    throw "La búsqueda de URLs falló."
}

$targetUrlsPath = Join-Path `
    $projectRoot `
    "Scraping\target_urls.txt"

$targetUrls = @(
    Get-Content -LiteralPath $targetUrlsPath |
    Where-Object { $_.Trim() }
)

if ($targetUrls.Count -eq 0) {
    throw (
        "No se encontraron URLs actuales. " +
        "La extraccion fue detenida para proteger los datos existentes."
    )
}

Write-Host ""
Write-Host "2. Extrayendo datos de propiedades..."

& $pythonPath `
    "Scraping\extract_supercasas_to_csv.py" `
    "--input" "Scraping\target_urls.txt" `
    "--limit" $extractionLimit `
    "--delay" $DelaySeconds

if ($LASTEXITCODE -ne 0) {
    throw "La extracción de propiedades falló."
}



$csvPath = Join-Path `
    $projectRoot `
    "raw_data\supercasas_listings.csv"

if (-not (Test-Path -LiteralPath $csvPath)) {
    throw "No se generó supercasas_listings.csv."
}

$rows = @(
    Import-Csv -LiteralPath $csvPath
)

if ($rows.Count -eq 0) {
    throw (
        "No hay propiedades válidas para importar. " +
        "Revisa raw_data\supercasas_rejected.csv."
    )
}

Write-Host "3. Validando CSV con Django..."
Write-Host "   Propiedades válidas encontradas: $($rows.Count)"

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"

if ($Commit) {
    Write-Host ""
    Write-Host "4. Importando datos reales a InmoData..."

    & $pythonPath `
        "manage.py" `
        "import_listings_csv" `
        "raw_data\supercasas_listings.csv" 2>&1
}
else {
    Write-Host ""
    Write-Host (
        "4. Simulacion solamente. " +
        "La base de datos no sera modificada."
    )

    & $pythonPath `
        "manage.py" `
        "import_listings_csv" `
        "raw_data\supercasas_listings.csv" `
        "--dry-run" 2>&1
}

$importExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference

if ($importExitCode -ne 0) {
    throw "La importacion de Django fallo."
}

if ($Commit) {
    Write-Host ""
    Write-Host "5. Guardando fotografia diaria del mercado..."

    $previousSnapshotErrorActionPreference = (
        $ErrorActionPreference
    )

    $ErrorActionPreference = "Continue"

    & $pythonPath `
        "manage.py" `
        "snapshot_market" 2>&1

    $snapshotExitCode = $LASTEXITCODE

    $ErrorActionPreference = (
        $previousSnapshotErrorActionPreference
    )

    if ($snapshotExitCode -ne 0) {
        throw "No se pudo guardar la fotografia diaria del mercado."
    }
}

Write-Host ""
Write-Host "Proceso completado."