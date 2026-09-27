param(
    [string]$Sectors = "el-millon",
    [int]$Limit = 5,
    [double]$DelaySeconds = 5,
    [switch]$Commit
)

$ErrorActionPreference = "Stop"

$projectRoot = (
    Resolve-Path (
        Join-Path $PSScriptRoot ".."
    )
).Path

$logsDirectory = Join-Path $projectRoot "logs"

New-Item `
    -ItemType Directory `
    -Path $logsDirectory `
    -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

$logPath = Join-Path `
    $logsDirectory `
    "supercasas-refresh-$timestamp.log"

$refreshScript = Join-Path `
    $PSScriptRoot `
    "refresh_supercasas.ps1"



try {
    if ($Commit) {
        & $refreshScript `
            -Sectors $Sectors `
            -Limit $Limit `
            -DelaySeconds $DelaySeconds `
            -Commit 2>&1 |
            Tee-Object -FilePath $logPath
    }
    else {
        & $refreshScript `
            -Sectors $Sectors `
            -Limit $Limit `
            -DelaySeconds $DelaySeconds 2>&1 |
            Tee-Object -FilePath $logPath
    }
    if ($LASTEXITCODE -ne 0) {
        throw "The refresh script failed."
    }

    Write-Host ""
    Write-Host "Log saved: $logPath"
}
catch {
    $_ | Out-String | Add-Content -Path $logPath

    Write-Error "Refresh failed. Review: $logPath"

    exit 1
}