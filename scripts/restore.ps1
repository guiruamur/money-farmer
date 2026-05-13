param(
    [Parameter(Mandatory=$true)][string]$From,
    [string]$DataDir = "data"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $From)) {
    throw "Directorio no encontrado: $From"
}

$db = Join-Path $From "crypto_farmer.db"
$memory = Join-Path $From "memory"

if (Test-Path $db) {
    Copy-Item -Path $db -Destination (Join-Path $DataDir "crypto_farmer.db") -Force
}
if (Test-Path $memory) {
    if (Test-Path (Join-Path $DataDir "memory")) {
        Remove-Item (Join-Path $DataDir "memory") -Recurse -Force
    }
    Copy-Item -Path $memory -Destination (Join-Path $DataDir "memory") -Recurse -Force
}

Write-Output "Restaurado desde $From"
