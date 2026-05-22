# watchdog.ps1 - Vigila el bot crypto-farmer y lo relanza si no esta vivo.
#
# Pensado para ejecutarse cada pocos minutos desde una Tarea Programada
# (ver scripts/install-watchdog.ps1). Resuelve el fallo de fiabilidad de
# depender de la carpeta Startup: esa solo se dispara al iniciar sesion y,
# con "Inicio rapido" de Windows o tras una suspension, no relanza el bot.
# El watchdog cubre TODOS los casos de muerte (crash, kill, suspension,
# fin del proceso) porque solo mira "esta vivo el bot, si o no".
#
# NOTA ENCODING: ASCII puro a proposito. PowerShell 5.1 lee scripts sin BOM
# como Windows-1252 y cualquier caracter no-ASCII rompe el parser.

$ProjectDir  = Split-Path $PSScriptRoot -Parent
$LogDir      = Join-Path $ProjectDir "data\logs"
$LogFile     = Join-Path $LogDir "watchdog.log"
$StartScript = Join-Path $PSScriptRoot "start.ps1"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Log($msg) {
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Add-Content -Path $LogFile -Value "$ts  $msg"
}

$bot = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
       Where-Object { $_.CommandLine -match "crypto_farmer" }

if ($bot) {
    # Vivo: no hacemos nada y no logueamos (evita inflar el archivo cada 5 min).
    exit 0
}

Log "bot caido -> ejecutando start.ps1"
try {
    # Capturamos toda la salida en una cadena (un solo encoding) y solo la
    # volcamos al log si algo fue mal; en el caso normal basta el resumen.
    $out = & $StartScript 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) {
        Log "start.ps1 OK (bot relanzado)"
    } else {
        Log "start.ps1 FALLO (exit code $LASTEXITCODE):"
        Add-Content -Path $LogFile -Value $out
    }
} catch {
    Log "ERROR ejecutando start.ps1: $_"
}
