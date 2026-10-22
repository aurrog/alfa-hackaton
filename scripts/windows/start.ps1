<#
  Запуск стенда на Windows без Docker (для проверки на своём компьютере).

  Нужно установить заранее:
    * Python 3.12 (python.org, Windows installer 64-bit, галочка "Add python.exe to PATH");
    * Node.js 22 LTS (nodejs.org);
    * PostgreSQL 16 (postgresql.org, установщик EDB; запомните пароль пользователя postgres).

  Запуск: двойной щелчок по scripts\windows\start.cmd
     или: powershell -ExecutionPolicy Bypass -File scripts\windows\start.ps1 [-Reset] [-History 30]

  Что делает: создаёт базу credit, ставит зависимости (Python — по lock-файлам с проверкой хэшей,
  npm — по package-lock.json), применяет миграции и тестовые данные и запускает в фоне:
  симулятор :8081, API :8000, два воркера конвейера, интерфейс :5173 (если порт занят — первый свободный
  из 5180–5199). Журналы — в папке .run.
  Остановить — scripts\windows\stop.cmd.
#>
param(
    [switch]$Reset,              # удалить базу и создать заново
    [int]$History = 30,          # сколько заявок истории создать при первом наполнении
    [string]$PgPassword = ''     # пароль postgres (если не указан — спросим, когда понадобится)
)

$ErrorActionPreference = 'Continue'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$RunDir = Join-Path $Root '.run'
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$PidFile = Join-Path $RunDir 'pids.txt'

function Step([string]$text) { Write-Host ''; Write-Host "==> $text" -ForegroundColor Cyan }
function Show-Log([string]$name) {
    # последние строки журналов сервиса — чтобы причина была видна сразу, без поиска файлов
    foreach ($f in @("$name.err.log", "$name.log")) {
        $path = Join-Path $RunDir $f
        if ((Test-Path $path) -and (Get-Item $path).Length -gt 0) {
            Write-Host ''
            Write-Host "--- .run\$f (последние строки) ---" -ForegroundColor Yellow
            Get-Content $path -Tail 25 -Encoding UTF8 | ForEach-Object { Write-Host "    $_" }
        }
    }
}
function Fail([string]$text, [string]$log = '') {
    if ($log) { Show-Log $log }
    Write-Host ''
    Write-Host "ОШИБКА: $text" -ForegroundColor Red
    exit 1
}
function Wait-Http([string]$url, [int]$seconds, $proc = $null) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 3
            if ($r.StatusCode -eq 200) { return $true }
        } catch { }
        if ($proc -and $proc.HasExited) { return $false }   # процесс упал — ждать дальше бессмысленно
        Start-Sleep -Milliseconds 700
    }
    return $false
}
function Test-PortFree([int]$port) {
    # порт может быть занят другой программой или зарезервирован Windows (excludedportrange) — проверяем, что слушать можно
    foreach ($addr in @([System.Net.IPAddress]::Loopback, [System.Net.IPAddress]::Any)) {
        try {
            $l = New-Object System.Net.Sockets.TcpListener($addr, $port)
            $l.Start(); $l.Stop()
        } catch { return $false }
    }
    return $true
}
function Find-FreePort([int[]]$candidates) {
    foreach ($p in $candidates) { if (Test-PortFree $p) { return $p } }
    return 0
}
function Start-Service2([string]$name, [string]$exe, [string[]]$argList, [string]$dir) {
    $out = Join-Path $RunDir "$name.log"
    $err = Join-Path $RunDir "$name.err.log"
    $p = Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $dir -WindowStyle Hidden `
        -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
    $ticks = 0
    try { $ticks = $p.StartTime.ToUniversalTime().Ticks } catch { }
    Add-Content -Path $PidFile -Value "$($p.Id);$ticks"
    Write-Host "    $name запущен (PID $($p.Id)), журнал: .run\$name.log"
    return $p
}

# ------------------------------------------------------------------ 0. Остановить прошлый запуск
if (Test-Path $PidFile) {
    Step 'Останавливаю предыдущий запуск'
    & (Join-Path $PSScriptRoot 'stop.ps1') -Quiet
    Start-Sleep -Seconds 2   # дать процессам освободить порты
}

# ------------------------------------------------------------------ 1. Программы
Step 'Проверяю установленные программы'
$PyExe = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $candidate = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $candidate) { $PyExe = "$candidate".Trim() }
}
if (-not $PyExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $ver = & python -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    if ("$ver".Trim() -eq '3.12') { $PyExe = (& python -c "import sys; print(sys.executable)").Trim() }
}
if (-not $PyExe) { Fail 'Не найден Python 3.12. Установите его с python.org (Windows installer 64-bit) с галочкой "Add python.exe to PATH" и запустите скрипт снова.' }
Write-Host "    Python: $PyExe"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Fail 'Не найден Node.js. Установите Node.js 22 LTS с nodejs.org и перезапустите скрипт.' }
$nodeMajor = [int](("$(& node --version)").TrimStart('v').Split('.')[0])
if ($nodeMajor -lt 20) { Fail "Нужен Node.js 20 или новее (сейчас $(& node --version))." }
Write-Host "    Node.js: $(& node --version)"

$Psql = $null
$cmd = Get-Command psql -ErrorAction SilentlyContinue
if ($cmd) { $Psql = $cmd.Source }
if (-not $Psql) {
    $found = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\psql.exe' -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if ($found) { $Psql = $found.FullName }
}
if (-not $Psql) { Fail 'Не найден PostgreSQL. Установите PostgreSQL 16 (postgresql.org/download/windows) и запустите скрипт снова.' }
Write-Host "    PostgreSQL: $Psql"

# ------------------------------------------------------------------ 2. База данных
Step 'Готовлю базу данных'
$env:PGCLIENTENCODING = 'UTF8'
$env:PGPASSWORD = 'credit'
& $Psql -w -h localhost -U credit -d credit -tAc 'select 1' 2>$null | Out-Null
$haveDb = ($LASTEXITCODE -eq 0)
if ($Reset -or -not $haveDb) {
    if (-not $PgPassword) {
        $sec = Read-Host 'Пароль пользователя postgres (задавали при установке PostgreSQL)' -AsSecureString
        $PgPassword = (New-Object System.Net.NetworkCredential('', $sec)).Password
    }
    $env:PGPASSWORD = $PgPassword
    & $Psql -w -h localhost -U postgres -d postgres -tAc 'select 1' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail 'Не удалось подключиться к PostgreSQL как postgres. Проверьте пароль и что служба postgresql-x64-16 запущена (services.msc).' }
    $role = & $Psql -w -h localhost -U postgres -d postgres -tAc "select 1 from pg_roles where rolname = 'credit'" 2>$null
    if ("$role".Trim() -ne '1') {
        & $Psql -w -h localhost -U postgres -d postgres -v ON_ERROR_STOP=1 -c "create role credit login password 'credit' createdb" | Out-Null
    }
    if ($Reset) {
        & $Psql -w -h localhost -U postgres -d postgres -c "drop database if exists credit with (force)" | Out-Null
        Remove-Item -Recurse -Force (Join-Path $Root 'backend\data\uploads') -ErrorAction SilentlyContinue
    }
    $db = & $Psql -w -h localhost -U postgres -d postgres -tAc "select 1 from pg_database where datname = 'credit'" 2>$null
    if ("$db".Trim() -ne '1') {
        & $Psql -w -h localhost -U postgres -d postgres -v ON_ERROR_STOP=1 -c "create database credit owner credit encoding 'UTF8' template template0" | Out-Null
        if ($LASTEXITCODE -ne 0) { Fail 'Не удалось создать базу credit.' }
    }
    $env:PGPASSWORD = 'credit'
}
Write-Host '    База credit готова (пользователь credit / credit)'

# ------------------------------------------------------------------ 3. Зависимости
Step 'Устанавливаю зависимости Python (первый раз — 1–3 минуты)'
foreach ($part in @('backend', 'mocks')) {
    $venv = Join-Path $Root "$part\.venv"
    $vpy = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path $vpy)) {
        & $PyExe -m venv $venv
        if ($LASTEXITCODE -ne 0) { Fail "Не удалось создать виртуальное окружение $part\.venv" }
    }
    $lock = Join-Path $Root "$part\requirements.lock"
    $stamp = Join-Path $venv 'lock.sha256'
    $hash = (Get-FileHash $lock -Algorithm SHA256).Hash
    if (-not (Test-Path $stamp) -or ((Get-Content $stamp -Raw).Trim() -ne $hash)) {
        & $vpy -m pip install --disable-pip-version-check -q --require-hashes --no-deps -r $lock
        if ($LASTEXITCODE -ne 0) { Fail "Не удалось установить зависимости $part (см. сообщения выше)." }
        Set-Content -Path $stamp -Value $hash
    }
    Write-Host "    $part — готово"
}
$BackendPy = Join-Path $Root 'backend\.venv\Scripts\python.exe'
$MocksPy = Join-Path $Root 'mocks\.venv\Scripts\python.exe'

Step 'Устанавливаю зависимости интерфейса (первый раз — 1–2 минуты)'
$front = Join-Path $Root 'frontend'
if (-not (Test-Path (Join-Path $front 'node_modules\.bin\vite.cmd'))) {
    Push-Location $front
    & npm.cmd ci --no-audit --no-fund --loglevel=error
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { Fail 'npm ci завершился с ошибкой (см. сообщения выше).' }
}
$Npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $Npm) { Fail 'Не найден npm (ставится вместе с Node.js).' }
Write-Host '    frontend — готово'

# ------------------------------------------------------------------ 4. Порты
Step 'Проверяю свободные порты'
foreach ($need in @(@{ Name = 'симулятора'; Port = 8081 }, @{ Name = 'API'; Port = 8000 })) {
    if (-not (Test-PortFree $need.Port)) {
        Fail ("Порт $($need.Port) для $($need.Name) занят другой программой. Найти её: netstat -ano | findstr :$($need.Port) " +
              '(последнее число — PID, его видно в диспетчере задач на вкладке «Подробности»).')
    }
}
$WebPorts = @(5173) + (5180..5199) + @(3000, 4173, 8088)
Write-Host '    8000 и 8081 свободны'

# ------------------------------------------------------------------ 5. Запуск
$env:DATABASE_URL = 'postgresql+psycopg://credit:credit@localhost:5432/credit'
$env:INTEGRATIONS_BASE_URL = 'http://127.0.0.1:8081'
$env:STORAGE_DIR = Join-Path $Root 'backend\data\uploads'
$env:CORS_ORIGINS = 'http://127.0.0.1:5173,http://localhost:5173'   # интерфейс ходит в API через прокси Vite, CORS не участвует
$env:VITE_API_PROXY = 'http://127.0.0.1:8000'
$env:WORKER_METRICS_HOST = '127.0.0.1'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
if (Test-Path $PidFile) { Remove-Item $PidFile -Force }

Step 'Запускаю симулятор внешних систем'
$p = Start-Service2 'mocks' $MocksPy @('-m', 'uvicorn', 'simulator.main:app', '--host', '127.0.0.1', '--port', '8081', '--log-level', 'warning') (Join-Path $Root 'mocks')
if (-not (Wait-Http 'http://127.0.0.1:8081/health' 60 $p)) { Fail 'Симулятор не запустился.' 'mocks' }

Step 'Применяю миграции и тестовые данные (первый раз — около минуты)'
Push-Location (Join-Path $Root 'backend')
& $BackendPy -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail 'Миграции не применились (см. сообщения выше).' }
$env:LOG_LEVEL = 'WARNING'
& $BackendPy -m app.seed --history $History
$code = $LASTEXITCODE
$env:LOG_LEVEL = 'INFO'
Pop-Location
if ($code -ne 0) { Fail 'Не удалось создать тестовые данные (см. сообщения выше).' }

Step 'Запускаю API и конвейер'
$backend = Join-Path $Root 'backend'
$apiProc = Start-Service2 'api' $BackendPy @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') $backend
foreach ($i in 1, 2) {
    $env:WORKER_ID = "worker-$i"
    $env:WORKER_METRICS_PORT = "$((9100 + $i))"
    Start-Service2 "worker$i" $BackendPy @('-m', 'app.worker') $backend | Out-Null
}
if (-not (Wait-Http 'http://127.0.0.1:8000/api/health/ready' 90 $apiProc)) { Fail 'API не запустился.' 'api' }

Step 'Запускаю интерфейс'
$WebUrl = $null
$tried = @()
foreach ($attempt in 1..3) {
    $WebPort = Find-FreePort ($WebPorts | Where-Object { $tried -notcontains $_ })
    if (-not $WebPort) { break }
    $tried += $WebPort
    if ($WebPort -ne 5173) { Write-Host "    Порт 5173 занят или зарезервирован Windows — беру порт $WebPort" -ForegroundColor Yellow }
    $webProc = Start-Service2 'web' $Npm @('run', 'dev', '--', '--host', '127.0.0.1', '--port', "$WebPort", '--strictPort') $front
    if (Wait-Http "http://127.0.0.1:$WebPort/" 180 $webProc) { $WebUrl = "http://127.0.0.1:$WebPort"; break }
    if (-not $webProc.HasExited) { break }   # процесс жив, но не отвечает — другой порт не поможет
    $out = (Get-Content (Join-Path $RunDir 'web.log'), (Join-Path $RunDir 'web.err.log') -Raw -ErrorAction SilentlyContinue) -join ''
    if ($out -notmatch 'already in use|EADDRINUSE|EACCES') { break }   # упал не из-за порта
}
if (-not $WebUrl) {
    if ($webProc -and -not $webProc.HasExited) { & taskkill.exe /PID $webProc.Id /T /F 2>$null | Out-Null }
    Fail 'Интерфейс не запустился, причина — в строках журнала выше.' 'web'
}

Write-Host ''
Write-Host 'Стенд запущен' -ForegroundColor Green
Write-Host "  Интерфейс:          $WebUrl   (учётки на странице входа, пароль Demo-2026)"
Write-Host "  Swagger UI:         $WebUrl/api/docs"
Write-Host '  Симулятор и сбои:   http://127.0.0.1:8081/docs'
Write-Host '  Журналы:            папка .run'
Write-Host '  Остановить:         scripts\windows\stop.cmd'
Write-Host "  Сквозные сценарии:  backend\.venv\Scripts\python tests\e2e\run_scenarios.py --base $WebUrl --mocks http://127.0.0.1:8081"
Start-Process $WebUrl
