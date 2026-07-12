$ErrorActionPreference = 'Stop'

$secret = [Environment]::GetEnvironmentVariable('KAKAO_UPLOAD_SECRET', 'User')
if ([string]::IsNullOrWhiteSpace($secret)) {
    throw 'KAKAO_UPLOAD_SECRET user environment variable is missing.'
}
$env:KAKAO_UPLOAD_SECRET = $secret

$python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = (Get-Command python.exe -ErrorAction Stop).Source
}

$logDirectory = Join-Path $env:LOCALAPPDATA 'Synapspot'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$logPath = Join-Path $logDirectory 'kakao-export-collector.log'
$collector = Join-Path $PSScriptRoot 'kakao_export_collector.py'

& $python $collector --upload *>> $logPath
exit $LASTEXITCODE
