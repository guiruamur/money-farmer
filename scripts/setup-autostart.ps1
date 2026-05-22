# setup-autostart.ps1 - Configura el arranque automatico del bot SIN vigilancia periodica.
#
# Que hace:
#   1. Elimina la tarea programada "crypto-farmer-watchdog" (la que corria cada
#      5 min y hacia parpadear una ventana de PowerShell, molesto).
#   2. Deja en la carpeta Startup un lanzador que, al iniciar sesion, arranca el
#      bot UNA vez en una ventana de PowerShell VISIBLE que permanece abierta
#      (-NoExit), para que la veas y la cierres a mano cuando quieras.
#
# Cerrar esa ventana NO mata el bot: start.ps1 lo lanza como proceso
# independiente (Start-Process), asi que sigue corriendo en segundo plano.
#
# Compromiso: sin la tarea periodica, si el bot muere con el PC ya encendido no
# se auto-recupera hasta el siguiente arranque. Como apagas/enciendes a diario
# y la suspension esta desactivada, en la practica queda cubierto.
#
# Uso:  .\scripts\setup-autostart.ps1

$ErrorActionPreference = "Stop"
$StartPs1 = Join-Path $PSScriptRoot "start.ps1"

# --- 1. Quitar la tarea periodica si existe ---
$task = Get-ScheduledTask -TaskName "crypto-farmer-watchdog" -ErrorAction SilentlyContinue
if ($task) {
    try {
        Unregister-ScheduledTask -TaskName "crypto-farmer-watchdog" -Confirm:$false -ErrorAction Stop
        Write-Host "Tarea periodica eliminada (se acabo el parpadeo cada 5 min)." -ForegroundColor Green
    } catch {
        Write-Host "NO se pudo eliminar la tarea: $_" -ForegroundColor Red
        Write-Host "Ejecuta este script desde TU PowerShell normal (no elevado basta)." -ForegroundColor Yellow
        throw
    }
} else {
    Write-Host "No habia tarea periodica registrada." -ForegroundColor Yellow
}

# --- 2. Lanzador VISIBLE en la carpeta Startup ---
# 'start ""' abre PowerShell en su propia ventana; -NoExit la deja abierta tras
# ejecutar start.ps1 para que veas el resultado y la cierres tu.
$startup = [Environment]::GetFolderPath('Startup')
$cmd     = Join-Path $startup "crypto-farmer-start.cmd"
$body    = "@echo off`r`nstart `"crypto-farmer`" powershell.exe -NoExit -ExecutionPolicy Bypass -File `"$StartPs1`""
Set-Content -Path $cmd -Value $body -Encoding ASCII
Write-Host "Lanzador de arranque (ventana visible) escrito en:" -ForegroundColor Green
Write-Host "  $cmd"
Write-Host "Listo. Al encender el PC se abrira una ventana de PowerShell que arranca" -ForegroundColor Cyan
Write-Host "el bot y se queda abierta para que la cierres tu." -ForegroundColor Cyan
