# start.ps1 — Arranque fiable de crypto-farmer tras un reinicio del PC.
#
# Resuelve el problema recurrente: al encender el equipo, Ollama arranca antes
# de que el disco de modelos (R:) esté montado, y se queda "ciego" (sin modelos).
# Este script espera al disco, reinicia Ollama apuntando bien, verifica que ve
# los modelos, y arranca el bot.
#
# Uso:  click derecho > "Ejecutar con PowerShell"   (o)   .\scripts\start.ps1
# Opcional: registrarlo como tarea al iniciar sesión (ver README).

$ErrorActionPreference = "Stop"

# Rutas derivadas de la ubicación del script (scripts/ está dentro del proyecto).
$ProjectDir = Split-Path $PSScriptRoot -Parent
$Python     = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$LogDir     = Join-Path $ProjectDir "data\logs"

# Ruta de modelos: usa la variable de sistema si existe, si no un default.
$ModelsPath = [Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "Machine")
if (-not $ModelsPath) { $ModelsPath = "R:\OllamaModels" }

$RequiredModels = @("qwen2.5:7b-instruct-q4_K_M", "mxbai-embed-large")

function Step($n, $msg) { Write-Host "[$n/4] $msg" -ForegroundColor Cyan }
function Ok($msg)       { Write-Host "      $msg" -ForegroundColor Green }
function Fail($msg)     { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

Write-Host "=== Arranque crypto-farmer ===" -ForegroundColor Cyan

# --- 1. Esperar a que el disco de modelos esté montado ---
Step 1 "Esperando disco de modelos ($ModelsPath)..."
$deadline = (Get-Date).AddSeconds(120)
while (-not (Test-Path $ModelsPath)) {
    if ((Get-Date) -gt $deadline) { Fail "$ModelsPath no se montó en 120s." }
    Start-Sleep -Seconds 2
}
Ok "disco disponible"

# --- 2. Reiniciar Ollama apuntando al disco correcto ---
Step 2 "Reiniciando Ollama..."
$env:OLLAMA_MODELS = $ModelsPath
Get-Process | Where-Object { $_.Name -match "ollama" } |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden

$deadline = (Get-Date).AddSeconds(60)
$ollamaUp = $false
do {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/version" `
             -TimeoutSec 3 -UseBasicParsing
        $ollamaUp = $r.StatusCode -eq 200
    } catch { $ollamaUp = $false }
} while (-not $ollamaUp -and (Get-Date) -lt $deadline)
if (-not $ollamaUp) { Fail "Ollama no respondió en 60s." }
Ok "Ollama responde en :11434"

# --- 3. Verificar que Ollama ve los modelos necesarios ---
Step 3 "Verificando modelos..."
$installed = (& ollama list 2>&1 | Out-String)
foreach ($m in $RequiredModels) {
    if ($installed -notmatch [regex]::Escape($m)) {
        Write-Host $installed
        Fail "Ollama no ve el modelo '$m'. ¿Disco R: correcto?"
    }
}
Ok "modelos disponibles: $($RequiredModels -join ', ')"

# --- 4. Arrancar el bot (matando una instancia previa si la hubiera) ---
Step 4 "Arrancando bot crypto-farmer..."
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "crypto_farmer" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

if (-not (Test-Path $Python)) { Fail "No existe el venv: $Python (¿hiciste el setup?)" }
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Start-Process -FilePath $Python `
    -ArgumentList "-m", "crypto_farmer", "--config", "config/config.yaml" `
    -WorkingDirectory $ProjectDir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $LogDir "bot-stdout.log") `
    -RedirectStandardError  (Join-Path $LogDir "bot-stderr.log")
Ok "bot lanzado (logs en data\logs\)"

Write-Host ""
Write-Host "=== Sistema arrancado correctamente ===" -ForegroundColor Cyan
Write-Host "Bot y Ollama corriendo en segundo plano."
Write-Host "Revisa el progreso por Telegram o en data\logs\crypto_farmer.log"
