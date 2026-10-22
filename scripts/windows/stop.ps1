<# Остановка стенда, запущенного scripts\windows\start.ps1 #>
param([switch]$Quiet)
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$PidFile = Join-Path $Root '.run\pids.txt'
if (Test-Path $PidFile) {
    foreach ($line in Get-Content $PidFile) {
        $parts = "$line".Trim().Split(';')
        if ($parts[0] -notmatch '^\d+$') { continue }
        $proc = Get-Process -Id ([int]$parts[0]) -ErrorAction SilentlyContinue
        if (-not $proc) { continue }
        # PID мог достаться другой программе (например, после перезагрузки) — сверяем время старта
        $ours = $false
        if ($parts.Count -gt 1 -and $parts[1] -match '^\d+$' -and [long]$parts[1] -gt 0) {
            try { $ours = ($proc.StartTime.ToUniversalTime().Ticks -eq [long]$parts[1]) } catch { }
        } else {
            $ours = @('python', 'pythonw', 'node', 'cmd') -contains $proc.ProcessName.ToLower()   # запись старого формата
        }
        if ($ours) { & taskkill.exe /PID $proc.Id /T /F 2>$null | Out-Null }
    }
    Remove-Item $PidFile -Force
    if (-not $Quiet) { Write-Host 'Стенд остановлен. Данные в базе сохранены; начать заново: start.cmd -Reset' -ForegroundColor Green }
} elseif (-not $Quiet) {
    Write-Host 'Запущенный стенд не найден.'
}
