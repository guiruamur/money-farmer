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

function Step($n, $msg) { Write-Host "[$n/3] $msg" -ForegroundColor Cyan }
function Ok($msg)       { Write-Host "      $msg" -ForegroundColor Green }
function Fail($msg)     { Write-Host "ERROR: $msg" -ForegroundColor Red; try { Stop-Transcript | Out-Null } catch {}; exit 1 }

# Log persistente de cada arranque: imprime en pantalla Y graba a archivo, para
# que un fallo al encender el PC (timing de R: / Ollama) deje rastro. Antes la
# salida solo vivia en la ventana efimera y no habia forma de saber que fallo.
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
try { Start-Transcript -Path (Join-Path $LogDir "start.log") -Append | Out-Null } catch {}

Write-Host "=== Arranque crypto-farmer ($(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) ===" -ForegroundColor Cyan

# --- 1. Esperar a que el disco de modelos esté montado ---
Step 1 "Esperando disco de modelos ($ModelsPath)..."
$deadline = (Get-Date).AddSeconds(120)
while (-not (Test-Path $ModelsPath)) {
    if ((Get-Date) -gt $deadline) { Fail "$ModelsPath no se montó en 120s." }
    Start-Sleep -Seconds 2
}
Ok "disco disponible"

# --- 2. Reiniciar Ollama y verificar que ve los modelos ---
# La app de bandeja de Ollama arranca sola al encender el PC y puede quedarse
# con el puerto :11434 apuntando al directorio por defecto (sin los modelos de
# R:). Por eso reintentamos el CICLO COMPLETO: matar TODO ollama (serve + app
# de bandeja), relanzar 'serve' con OLLAMA_MODELS=R:, y comprobar que
# 'ollama list' ve los modelos. Si no, se vuelve a matar y reintentar (la app
# de bandeja puede haber revivido). Esto era la causa del fallo al encender.
Step 2 "Reiniciando Ollama y verificando modelos..."
$env:OLLAMA_MODELS = $ModelsPath
$ready = $false
$installed = ""
for ($attempt = 1; $attempt -le 4 -and -not $ready; $attempt++) {
    Get-Process | Where-Object { $_.Name -match "ollama" } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden

    # Esperar a que el servidor responda (hasta 30s)
    $deadline = (Get-Date).AddSeconds(30)
    $up = $false
    do {
        Start-Sleep -Seconds 2
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/version" `
                 -TimeoutSec 3 -UseBasicParsing
            $up = $r.StatusCode -eq 200
        } catch { $up = $false }
    } while (-not $up -and (Get-Date) -lt $deadline)
    if (-not $up) {
        Write-Host "      intento ${attempt}: Ollama no respondio, reintentando" -ForegroundColor Yellow
        continue
    }

    # Comprobar que ve los modelos requeridos (hasta 30s)
    $deadline = (Get-Date).AddSeconds(30)
    do {
        $installed = (& ollama list 2>&1 | Out-String)
        $missing = @($RequiredModels | Where-Object { $installed -notmatch [regex]::Escape($_) })
        if ($missing.Count -eq 0) { break }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $deadline)
    if ($missing.Count -eq 0) { $ready = $true }
    else { Write-Host "      intento ${attempt}: Ollama no ve los modelos, reintentando" -ForegroundColor Yellow }
}
if (-not $ready) {
    Write-Host $installed
    Fail "Ollama no ve los modelos tras varios intentos: $($RequiredModels -join ', '). Disco R: correcto?"
}
Ok "Ollama responde y ve los modelos: $($RequiredModels -join ', ')"

# --- 3. Arrancar el bot (matando una instancia previa si la hubiera) ---
Step 3 "Arrancando bot crypto-farmer..."
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
try { Stop-Transcript | Out-Null } catch {}
