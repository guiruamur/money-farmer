# install-watchdog.ps1 - Registra la Tarea Programada que mantiene vivo el bot.
#
# Crea la tarea "crypto-farmer-watchdog" que ejecuta scripts/watchdog.ps1:
#   - cada 5 minutos (red de seguridad: recupera de cualquier muerte en <=5 min)
#   - al iniciar sesion (arranque rapido al encender el PC)
#
# Corre solo cuando el usuario esta logueado, asi que NO necesita permisos de
# administrador. Como respaldo adicional mantiene tambien el lanzador de la
# carpeta Startup: si el Task Scheduler fallara, al menos el .cmd lo intenta.
# (start.ps1 mata cualquier instancia previa, asi que no hay doble bot.)
#
# Uso:  .\scripts\install-watchdog.ps1
# Desinstalar:  Unregister-ScheduledTask -TaskName crypto-farmer-watchdog -Confirm:$false

$ErrorActionPreference = "Stop"
$TaskName  = "crypto-farmer-watchdog"
$Watchdog  = Join-Path $PSScriptRoot "watchdog.ps1"
$StartPs1  = Join-Path $PSScriptRoot "start.ps1"

if (-not (Test-Path $Watchdog)) { throw "No existe $Watchdog" }

# --- Accion: lanzar watchdog.ps1 oculto ---
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Watchdog`""

# --- Triggers ---
# 1) Repeticion cada 5 min. Duracion finita pero enorme (10 anos): MaxValue
#    genera P99999999DT... que el Task Scheduler rechaza por estar fuera de rango.
$tRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
# 2) Al iniciar sesion.
$tLogon  = New-ScheduledTaskTrigger -AtLogOn

# --- Principal: usuario actual, sin elevacion, solo con sesion iniciada ---
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive -RunLevel Limited

# --- Settings: no solapar instancias, recuperar ejecuciones perdidas ---
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

try {
    Register-ScheduledTask -TaskName $TaskName -Action $action `
        -Trigger @($tRepeat, $tLogon) -Principal $principal -Settings $settings `
        -Force -ErrorAction Stop | Out-Null
} catch {
    Write-Host "ERROR registrando la tarea: $_" -ForegroundColor Red
    Write-Host "No se ha tocado el respaldo de Startup." -ForegroundColor Yellow
    throw
}

# Verificar que existe de verdad antes de cantar victoria.
$check = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $check) { throw "La tarea no aparece tras registrarla; algo fallo." }
Write-Host "Tarea '$TaskName' registrada (cada 5 min + al iniciar sesion)." -ForegroundColor Green

# --- Respaldo: (re)crear el lanzador de la carpeta Startup ---
$startup = [Environment]::GetFolderPath('Startup')
$cmd     = Join-Path $startup "crypto-farmer-start.cmd"
$cmdBody = "@echo off`r`npowershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$StartPs1`""
Set-Content -Path $cmd -Value $cmdBody -Encoding ASCII
Write-Host "Respaldo de Startup en su sitio: $cmd" -ForegroundColor Green

Write-Host "Listo. La tarea se ejecutara en <=5 min y mantendra el bot vivo." -ForegroundColor Cyan
