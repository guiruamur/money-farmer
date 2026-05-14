# stop.ps1 — Detiene el bot crypto-farmer de forma limpia.
#
# Uso:  .\scripts\stop.ps1                 (solo el bot)
#       .\scripts\stop.ps1 -IncludeOllama  (también el servidor Ollama)

param(
    [switch]$IncludeOllama
)

$ErrorActionPreference = "Stop"

Write-Host "=== Deteniendo crypto-farmer ===" -ForegroundColor Cyan

# Bot: python que ejecuta el módulo crypto_farmer
$bot = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
       Where-Object { $_.CommandLine -match "crypto_farmer" }
if ($bot) {
    $bot | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "  bot detenido (PID $($_.ProcessId))" -ForegroundColor Green
    }
} else {
    Write-Host "  el bot no estaba corriendo" -ForegroundColor Yellow
}

if ($IncludeOllama) {
    $ollama = Get-Process | Where-Object { $_.Name -match "ollama" }
    if ($ollama) {
        $ollama | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-Host "  Ollama detenido" -ForegroundColor Green
    } else {
        Write-Host "  Ollama no estaba corriendo" -ForegroundColor Yellow
    }
}

Write-Host "=== Hecho ===" -ForegroundColor Cyan
