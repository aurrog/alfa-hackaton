<# Остановка стенда, запущенного scripts\windows\start.ps1 #>
param([switch]$Quiet)
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$PidFile = Join-Path $Root '.run\pids.txt'
if (Test-Path $PidFile) {
    foreach ($line in Get-Content $PidFile) {
        $id = "$line".Trim()
        if ($id -match '^\d+$') { & taskkill.exe /PID $id /T /F 2>$null | Out-Null }
    }
    Remove-Item $PidFile -Force
    if (-not $Quiet) { Write-Host 'Стенд остановлен. Данные в базе сохранены; начать заново: start.cmd -Reset' -ForegroundColor Green }
} elseif (-not $Quiet) {
    Write-Host 'Запущенный стенд не найден.'
}
