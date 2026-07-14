# 카카오톡 PC 대화 내보내기 자동화 (Win32 입력 방식)
#
# 카카오톡 .edb는 암호화되어 있고 UI Automation에도 본문이 노출되지 않으므로,
# 채팅방 창을 잠깐 foreground로 가져와 Ctrl+S(대화 저장)를 보내는 방식을 쓴다.
# 한글(방 이름·경로)은 IME 타이핑이 불안정하므로 전부 클립보드 붙여넣기로 처리한다.
#
# 종료 코드: 0=성공/건너뜀, 3=로그인 필요, 4=채팅방 열기 실패,
#            5=저장 대화상자 미출현, 6=파일 미생성
param(
    [string]$RoomTitle = '2026 제주대학교 하기 계절학기 학점교류방',
    [string]$ExportDirectory = (Join-Path $env:USERPROFILE 'Documents'),
    # 최근 N분 내 내보내기 파일이 이미 있으면 건너뛴다(작업 중 포커스 뺏김 최소화).
    # 30분: 예약 작업은 10분마다 돌지만 실제 화면 포커스를 뺏는 내보내기(Ctrl+S)는
    # 30분에 한 번만. 사이 틱은 업로드·큐 처리만 하고, 내보내기 실패 시엔 다음 틱 재시도.
    [int]$MinIntervalMinutes = 30,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class KakaoWin {
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder sb, int max);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder sb, int max);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool attach);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
    delegate bool EnumWindowsProc(IntPtr h, IntPtr lp);

    public class Info { public IntPtr Hwnd; public uint Pid; public string Cls; public string Title; public bool Visible; }

    public static List<Info> Windows(uint targetPid) {
        var list = new List<Info>();
        EnumWindows((h, lp) => {
            uint pid; GetWindowThreadProcessId(h, out pid);
            if (targetPid != 0 && pid != targetPid) return true;
            var t = new StringBuilder(512); GetWindowText(h, t, 512);
            var c = new StringBuilder(256); GetClassName(h, c, 256);
            list.Add(new Info { Hwnd = h, Pid = pid, Cls = c.ToString(), Title = t.ToString(), Visible = IsWindowVisible(h) });
            return true;
        }, IntPtr.Zero);
        return list;
    }

    // SetForegroundWindow 제한 회피: Alt 탭 신호 + 스레드 입력 연결
    public static bool Focus(IntPtr h) {
        uint targetThread; GetWindowThreadProcessId(h, out targetThread);
        // keybd_event로 Alt를 눌렀다 떼면 포그라운드 전환 잠금이 풀린다
        keybd_event(0x12, 0, 0, UIntPtr.Zero);
        keybd_event(0x12, 0, 2, UIntPtr.Zero);
        ShowWindow(h, 9); // SW_RESTORE
        uint cur = GetCurrentThreadId();
        AttachThreadInput(cur, targetThread, true);
        bool ok = SetForegroundWindow(h);
        AttachThreadInput(cur, targetThread, false);
        return ok;
    }
}
"@

function Write-Log([string]$message) {
    Write-Output ("내보내기: {0}" -f $message)
}

function Get-KakaoProcess {
    return Get-Process KakaoTalk -ErrorAction SilentlyContinue | Select-Object -First 1
}

function Get-KakaoWindows {
    $kakao = Get-KakaoProcess
    if (-not $kakao) { return @() }
    return [KakaoWin]::Windows([uint32]$kakao.Id)
}

function Find-ChatWindow {
    return Get-KakaoWindows |
        Where-Object { $_.Cls -eq 'EVA_Window_Dblclk' -and $_.Visible -and $_.Title -like "*$RoomTitle*" } |
        Select-Object -First 1
}

function Find-LoginWindow {
    return Get-KakaoWindows |
        Where-Object { $_.Cls -eq 'EVA_Window' -and $_.Visible -and $_.Title -eq '카카오톡' } |
        Select-Object -First 1
}

function Find-MainWindow {
    return Get-KakaoWindows |
        Where-Object { $_.Cls -eq 'EVA_Window_Dblclk' -and $_.Visible -and $_.Title -eq '카카오톡' } |
        Select-Object -First 1
}

function Send-Keys([string]$keys) {
    [System.Windows.Forms.SendKeys]::SendWait($keys)
    Start-Sleep -Milliseconds 300
}

# 포커스 전환을 검증한다. 실패한 채로 키를 보내면 사용자가 쓰던 앱에
# 키 입력이 들어가므로(실측: 첫 시도에서 전환이 씹힌 사례 있음) 반드시 확인.
function Focus-Window([IntPtr]$hwnd) {
    for ($i = 0; $i -lt 3; $i++) {
        [KakaoWin]::Focus($hwnd) | Out-Null
        Start-Sleep -Milliseconds 700
        if ([KakaoWin]::GetForegroundWindow() -eq $hwnd) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Set-ClipboardText([string]$text) {
    # Set-Clipboard는 STA 이슈가 있어 WinForms Clipboard를 직접 쓴다
    [System.Windows.Forms.Clipboard]::SetText($text)
}

# ── 0. 건너뛰기 판단: 최근 내보내기가 충분히 새것이면 종료 ──────────────
$latest = Get-ChildItem -Path $ExportDirectory -Filter 'KakaoTalk_*_group.txt' -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $Force -and $latest -and $latest.LastWriteTime -gt (Get-Date).AddMinutes(-$MinIntervalMinutes)) {
    Write-Log ("건너뜀: {0}분 내 내보내기 존재({1})" -f $MinIntervalMinutes, $latest.Name)
    exit 0
}

# ── 1. 카카오톡 프로세스 확보 ───────────────────────────────────────────
if (-not (Get-KakaoProcess)) {
    Write-Log '카카오톡 미실행 — 시작'
    Start-Process 'C:\Program Files\Kakao\KakaoTalk\KakaoTalk.exe'
    Start-Sleep -Seconds 12
}

# ── 2. 채팅방 창 확보 (없으면 메인 창 검색으로 연다) ─────────────────────
$chat = Find-ChatWindow
if (-not $chat) {
    if (Find-LoginWindow) {
        Write-Log '로그인 필요 — 사용자가 카카오톡에 로그인해야 합니다(자동로그인 권장)'
        exit 3
    }
    $main = Find-MainWindow
    if (-not $main) {
        # 트레이에 숨어 있으면 exe 재실행으로 기존 인스턴스 메인 창을 띄운다
        Start-Process 'C:\Program Files\Kakao\KakaoTalk\KakaoTalk.exe'
        Start-Sleep -Seconds 5
        if (Find-LoginWindow) {
            Write-Log '로그인 필요 — 사용자가 카카오톡에 로그인해야 합니다(자동로그인 권장)'
            exit 3
        }
        $main = Find-MainWindow
    }
    if (-not $main) {
        Write-Log '카카오톡 메인 창을 찾지 못했습니다'
        exit 4
    }

    $previousClipboard = $null
    try { $previousClipboard = [System.Windows.Forms.Clipboard]::GetText() } catch {}

    # 채팅 탭 → 검색 → 방 이름 붙여넣기 → 첫 결과 열기
    if (-not (Focus-Window $main.Hwnd)) {
        Write-Log '메인 창 포커스 전환 실패 — 키 전송을 중단합니다'
        exit 4
    }
    Send-Keys '{ESC}'
    Send-Keys '^2'
    Send-Keys '^f'
    Set-ClipboardText $RoomTitle
    Send-Keys '^v'
    Start-Sleep -Seconds 2
    Send-Keys '{ENTER}'

    # 채팅방 창이 뜰 때까지 대기, 안 뜨면 ↓ 후 Enter 재시도
    $deadline = (Get-Date).AddSeconds(8)
    while (-not ($chat = Find-ChatWindow) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
    if (-not $chat) {
        Send-Keys '{DOWN}'
        Send-Keys '{ENTER}'
        $deadline = (Get-Date).AddSeconds(8)
        while (-not ($chat = Find-ChatWindow) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
    }
    if ($previousClipboard) { try { Set-ClipboardText $previousClipboard } catch {} }
    if (-not $chat) {
        Write-Log ("채팅방을 열지 못했습니다: {0}" -f $RoomTitle)
        exit 4
    }
    Write-Log '채팅방 창을 새로 열었습니다'
}

# ── 3. Ctrl+S → 저장 대화상자 → 경로 붙여넣기 → 저장 ────────────────────
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$savePath = Join-Path $ExportDirectory ("KakaoTalk_auto_{0}_group.txt" -f $stamp)

$previousClipboard = $null
try { $previousClipboard = [System.Windows.Forms.Clipboard]::GetText() } catch {}

if (-not (Focus-Window $chat.Hwnd)) {
    Write-Log '채팅방 창 포커스 전환 실패 — 키 전송을 중단합니다'
    exit 5
}
Send-Keys '^s'

# 저장 대화상자(#32770) 대기
$dialog = $null
$deadline = (Get-Date).AddSeconds(10)
while (-not $dialog -and (Get-Date) -lt $deadline) {
    $dialog = Get-KakaoWindows | Where-Object { $_.Cls -eq '#32770' -and $_.Visible } | Select-Object -First 1
    if (-not $dialog) { Start-Sleep -Milliseconds 500 }
}
if (-not $dialog) {
    Write-Log '저장 대화상자가 뜨지 않았습니다(잠금 화면이거나 포커스 실패 가능)'
    exit 5
}

# 파일명 입력칸은 기본 포커스 — 전체 선택 후 전체 경로 붙여넣기
Set-ClipboardText $savePath
Send-Keys '^a'
Send-Keys '^v'
Send-Keys '{ENTER}'
if ($previousClipboard) { try { Set-ClipboardText $previousClipboard } catch {} }

# ── 4. 파일 생성 검증 ───────────────────────────────────────────────────
$deadline = (Get-Date).AddSeconds(15)
while (-not (Test-Path -LiteralPath $savePath) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
if (-not (Test-Path -LiteralPath $savePath)) {
    Write-Log '저장 파일이 생성되지 않았습니다'
    exit 6
}
$size = (Get-Item -LiteralPath $savePath).Length
Write-Log ("성공: {0} ({1} bytes)" -f (Split-Path -Leaf $savePath), $size)

# ── 5. 오래된 자동 내보내기 정리(자동 생성분만, 최신 3개 유지) ───────────
Get-ChildItem -Path $ExportDirectory -Filter 'KakaoTalk_auto_*_group.txt' -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -Skip 3 |
    Remove-Item -Force -ErrorAction SilentlyContinue

exit 0
