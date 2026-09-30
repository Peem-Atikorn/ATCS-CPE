param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('up', 'down', 'logs', 'smoke', 'warmup', 'config', 'preflight', 'monitor', 'eval', 'eval-live')]
    [string]$Task
)

$ErrorActionPreference = 'Stop'
$docker = (Get-Command docker -ErrorAction SilentlyContinue).Source
if (-not $docker) {
    $desktopCli = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
    if (Test-Path -LiteralPath $desktopCli) { $docker = $desktopCli }
}
if ($Task -in @('up', 'preflight')) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { throw 'Python 3.12+ is required for deploy/preflight.py.' }
    & $python.Source deploy/preflight.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if ($Task -eq 'preflight') { exit 0 }
}
if ($Task -in @('eval', 'eval-live', 'monitor')) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { throw 'Python 3.12+ is required for this task.' }
    if ($Task -eq 'eval') { & $python.Source eval/build_report.py }
    elseif ($Task -eq 'eval-live') { & $python.Source eval/run_live.py }
    else { & $python.Source deploy/monitor.py }
    exit $LASTEXITCODE
}
if (-not (Test-Path -LiteralPath '.env')) {
    throw 'Copy .env.example to .env and set local passwords and provider keys first.'
}

$composeArgs = @('compose', '--env-file', '.env', '-f', 'docker-compose.yml')
switch ($Task) {
    'up' { $composeArgs += @('up', '--build', '-d', '--wait') }
    'down' { $composeArgs += @('down') }
    'logs' { $composeArgs += @('logs', '-f', '--tail=100') }
    'smoke' { $composeArgs += @('run', '--rm', '--no-deps', 'checks', 'python', '/tools/smoke.py') }
    'warmup' { $composeArgs += @('run', '--rm', '--no-deps', 'checks', 'python', '/tools/warmup.py') }
    'config' { $composeArgs += @('config', '--quiet') }
}

if (-not $docker) { throw 'Docker CLI not found. Install or start Docker Desktop.' }
& $docker @composeArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
