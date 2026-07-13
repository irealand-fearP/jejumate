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

# 1) 카카오톡 대화 내보내기 자동화(베스트에포트) — 실패해도 수집은 계속한다.
#    로그인 안 됨(3)·잠금 화면(5) 등은 로그만 남기고, 기존 txt로 수집을 이어간다.
$autoExport = Join-Path $PSScriptRoot 'kakao_auto_export.ps1'
if (Test-Path -LiteralPath $autoExport) {
    try {
        & $autoExport *>> $logPath
        "auto-export exit=$LASTEXITCODE" | Out-File -FilePath $logPath -Append -Encoding utf8
    } catch {
        "auto-export error: $($_.Exception.GetType().Name)" | Out-File -FilePath $logPath -Append -Encoding utf8
    }
}

# 2) 최신 내보내기 파일 업로드·큐 처리
& $python $collector --upload *>> $logPath
exit $LASTEXITCODE
