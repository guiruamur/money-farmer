param(
    [string]$DataDir = "data",
    [string]$BackupDir = "data/backups",
    [int]$RetentionDays = 30
)

$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "yyyy-MM-dd"
$target = Join-Path $BackupDir $timestamp
if (-not (Test-Path $target)) {
    New-Item -ItemType Directory -Force -Path $target | Out-Null
}

$db = Join-Path $DataDir "crypto_farmer.db"
if (Test-Path $db) {
    Copy-Item -Path $db -Destination (Join-Path $target "crypto_farmer.db") -Force
}

$memory = Join-Path $DataDir "memory"
if (Test-Path $memory) {
    Copy-Item -Path $memory -Destination (Join-Path $target "memory") -Recurse -Force
}

$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem $BackupDir -Directory | Where-Object {
    try {
        [datetime]::ParseExact($_.Name, "yyyy-MM-dd", $null) -lt $cutoff
    } catch { $false }
} | Remove-Item -Recurse -Force

Write-Output "Backup creado en $target"
