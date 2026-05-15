# stop.ps1 — Detiene el bot crypto-farmer de forma limpia.
#
# Antes de matar el proceso, envía un aviso "Sistema finalizado" a Telegram
# (leyendo las credenciales de .env). Esto es fiable aunque el proceso se mate
# de forma forzada, porque el mensaje lo manda este script, no el bot.
#
# Uso:  .\scripts\stop.ps1                 (solo el bot)
#       .\scripts\stop.ps1 -IncludeOllama  (también el servidor Ollama)

param(
    [switch]$IncludeOllama
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path $PSScriptRoot -Parent
$EnvFile    = Join-Path $ProjectDir ".env"

Write-Host "=== Deteniendo crypto-farmer ===" -ForegroundColor Cyan

# --- Aviso a Telegram antes de matar nada ---
function Get-EnvValue($key) {
    if (-not (Test-Path $EnvFile)) { return $null }
    foreach ($line in Get-Content $EnvFile) {
        if ($line -match "^\s*$key\s*=\s*(.+?)\s*$") { return $Matches[1] }
    }
    return $null
}

$token  = Get-EnvValue "TELEGRAM_BOT_TOKEN"
$chatId = Get-EnvValue "TELEGRAM_CHAT_ID"
if ($token -and $chatId) {
    try {
        $body = @{
            chat_id    = $chatId
            text       = "🔴 <b>Sistema finalizado</b> — crypto-farmer detenido."
            parse_mode = "HTML"
        }
        Invoke-WebRequest -Uri "https://api.telegram.org/bot$token/sendMessage" `
            -Method Post -Body $body -TimeoutSec 10 -UseBasicParsing | Out-Null
        Write-Host "  aviso enviado a Telegram" -ForegroundColor Green
    } catch {
        Write-Host "  no se pudo avisar a Telegram (se detiene igualmente)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  sin credenciales en .env, no se avisa a Telegram" -ForegroundColor Yellow
}

# --- Detener el bot ---
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
