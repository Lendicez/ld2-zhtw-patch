<#
m060 可丟棄副本觀察（Win11）。
- 第一次（run1，2026-10-28 已執行）：A、B 完成；B 結束碼 1 被舊版腳本誤判停止。
- 第二次（run2，使用者 2026-10-28 訊息 t33u 批准）：只跑 C～F＋G，沿用 run1 的副本與第 1 格存檔，
  證據寫到新的 evidence-run2\（run1 的 evidence\ 不動）。

寫入範圍只限 $DisposableRoot（預設 <LD2_ROOT>\zhTW_lab\game-acceptance\m060\）：
  game\          遊戲副本（不含 Usr\ 私人存檔；建立空 Usr\）
  exe-store\     Ld95.original.exe / Ld95.m045.exe（切換時複製到 game\Ld95.exe，檔名不變）
  evidence\      run1 證據（hashes-before.json、launch-*.json、hashes-after.json）
  evidence-run2\ run2 證據（-Run2 才使用）
來源資料夾（遊戲安裝）只讀：robocopy 只從來源讀，絕不寫入來源或 Steam 目錄。
不修改 production_can_apply / release_approved（永遠 false）；不關 Defender、不改 ACL/locale。

結束碼判定（m060 run2 起）：
  - 0                → 成功。
  - 1 且同時符合下列全部 → 「軟警告」（黃字，記錄 exit_policy=soft-warn-exit1，繼續下一步）：
      (a) 啟動期間 Application 記錄沒有任何 Ld95 相關的 Application Error / Windows Error Reporting /
          Application Hang 項目，也沒有 Ld95 相關的「錯誤／重大」等級事件；
      (b) %LOCALAPPDATA%\CrashDumps 沒有本次新增／更新的 Ld95 dump，WER 報告資料夾也沒有本次新增的 Ld95 報告；
      (c) 本次啟動期間 game\Usr\ 至少有一個 LUNAS*.LDP 存檔被新增或內容改變。
    原因：這款 1990 年代 MFC 遊戲從選單「結束」離開時會回傳 1（run1 步驟 B 即如此）。
  - 0xC0000409、其他任何非 0 碼、或結束碼 1 但缺少 (a)(b)(c) 任一項 → 硬停（紅字，不再啟動）。
  軟警告不是「確認正常」：請在 observations.md 寫明是否用遊戲選單正常結束。

用法（在 PowerShell，本次程序才用 Bypass，不改系統設定）：
  第二次（只跑 C～F，沿用 run1 副本）：
    powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -Run2                 # R：檢查＋建立 evidence-run2
    powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -Run2 -LaunchStep C   # C+D+E 同一次 m045 啟動
    powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -Run2 -LaunchStep F
    powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -Run2 -Finalize       # G
  全新副本（只有 run1 副本已不存在、且另獲批准時才用；請配合新的 -DisposableRoot）：
    ... -CheckOnly / （無參數＝A） / -LaunchStep B / -LaunchStep C / -LaunchStep F / -Finalize
#>
[CmdletBinding()]
param(
  [string]$LD2Root = (Join-Path $env:SystemDrive 'GameDev\LD2'),  # 預設系統磁碟（通常 C:）；其他磁碟請用 -LD2Root 指定
  [string]$SourceDir = '',
  [string]$M045Exe = '',
  [string]$DisposableRoot = '',
  [ValidateSet('', 'B', 'C', 'F')][string]$LaunchStep = '',
  [switch]$Run2,
  [switch]$Finalize,
  [switch]$CheckOnly
)
Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$ORIG_SHA = '6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2'
$ORIG_SIZE = 7090176
$M045_SHA = '4a0910243d159af8007b5e77369c21f262d9e7a402bcb92a991e4c368ccd9da7'
$M045_SIZE = 7118848
$EXIT_STACK_BUFFER_OVERRUN = -1073740791  # 0xC0000409
$RUN1_STOP_TEXT = 'step B exit 0x00000001'

if (-not $SourceDir) { $SourceDir = Join-Path $LD2Root 'LunaticDawnPotB' }
if (-not $DisposableRoot) { $DisposableRoot = Join-Path $LD2Root 'zhTW_lab\game-acceptance\m060' }
$SourceDir = [IO.Path]::GetFullPath($SourceDir).TrimEnd('\')
$DisposableRoot = [IO.Path]::GetFullPath($DisposableRoot).TrimEnd('\')
$Game = Join-Path $DisposableRoot 'game'
$Store = Join-Path $DisposableRoot 'exe-store'
$Evidence1 = Join-Path $DisposableRoot 'evidence'
$Evidence = if ($Run2) { Join-Path $DisposableRoot 'evidence-run2' } else { $Evidence1 }
$StateFile = Join-Path $Evidence 'state.json'

function Stop-Run([string]$msg) {
  Write-Host ''
  Write-Host "停止：$msg" -ForegroundColor Red
  Write-Host '依計畫 §3：不重試、不換方法；只蒐證後帶回 Linux 端分析。' -ForegroundColor Red
  exit 2
}
function Assert-Writable([string]$p) {
  $full = [IO.Path]::GetFullPath($p)
  if (-not ($full.StartsWith($DisposableRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or
            $full.Equals($DisposableRoot, [StringComparison]::OrdinalIgnoreCase))) {
    Stop-Run "內部防護：拒絕寫入副本以外的路徑 $full"
  }
}
function Get-Sha([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() }
function Write-Json([string]$p, $obj) {
  Assert-Writable $p
  if (Test-Path -LiteralPath $p) { Stop-Run "證據檔已存在，不覆蓋：$p" }
  $obj | ConvertTo-Json -Depth 8 | Out-File -LiteralPath $p -Encoding utf8
}
function Save-State($st) {
  Assert-Writable $StateFile
  $st | ConvertTo-Json -Depth 8 | Out-File -LiteralPath $StateFile -Encoding utf8 -Force
}
function Read-Json([string]$p) { Get-Content -LiteralPath $p -Raw -Encoding UTF8 | ConvertFrom-Json }
function Get-Prop($obj, [string]$name) {
  # StrictMode 下讀取可能不存在的屬性
  if ($null -eq $obj) { return $null }
  $pp = $obj.PSObject.Properties[$name]
  if ($pp) { return $pp.Value } else { return $null }
}
function Get-Manifest([string]$root, [switch]$SkipUsr) {
  $items = Get-ChildItem -LiteralPath $root -Recurse -File -Force | Where-Object {
    $rel = $_.FullName.Substring($root.Length + 1)
    -not ($SkipUsr -and ($rel -like 'Usr\*' -or $rel -like 'LUNAS*'))
  } | Sort-Object FullName
  foreach ($f in $items) {
    [ordered]@{
      path = $f.FullName.Substring($root.Length + 1)
      size = $f.Length
      sha256 = Get-Sha $f.FullName
      last_write_utc = $f.LastWriteTimeUtc.ToString('o')
    }
  }
}
function Get-UsrSnapshot {
  $u = Join-Path $Game 'Usr'
  if (-not (Test-Path -LiteralPath $u)) { return @() }
  @(Get-ChildItem -LiteralPath $u -Recurse -File -Force | Sort-Object FullName | ForEach-Object {
    [ordered]@{ path = $_.FullName.Substring($Game.Length + 1); size = $_.Length; sha256 = Get-Sha $_.FullName; last_write_utc = $_.LastWriteTimeUtc.ToString('o') }
  })
}
function ConvertTo-TimeText($v) {
  # PowerShell 7 的 ConvertFrom-Json 會把時間字串轉成 DateTime；統一成 'o' 格式字串再比較
  if ($v -is [datetime]) { return $v.ToUniversalTime().ToString('o') }
  return [string]$v
}
function Compare-Manifest($beforeList, $afterList) {
  $changed = @()
  $bmap = @{}; foreach ($m in @($beforeList)) { if ($m) { $bmap[[string]$m.path] = $m } }
  foreach ($m in @($afterList)) {
    if (-not $m) { continue }
    $b = $bmap[[string]$m.path]
    if (-not $b) { $changed += "新增：$($m.path)" }
    elseif ($b.sha256 -ne $m.sha256 -or (ConvertTo-TimeText $b.last_write_utc) -ne (ConvertTo-TimeText $m.last_write_utc)) { $changed += "改變：$($m.path)" }
    $bmap.Remove([string]$m.path)
  }
  foreach ($k in @($bmap.Keys)) { $changed += "消失：$k" }
  return ,$changed
}
function Assert-NotRunning {
  $p = Get-Process -Name 'Ld95' -ErrorAction SilentlyContinue
  if ($p) { Stop-Run 'Ld95 正在執行（可能是 Steam 安裝版）。請先關閉遊戲。' }
}
function Assert-SourceExe {
  $exe = Join-Path $SourceDir 'Ld95.exe'
  if (-not (Test-Path -LiteralPath $exe)) { Stop-Run "找不到來源 $exe（遊戲不在預設位置時請加 -LD2Root 或 -SourceDir）" }
  $len = (Get-Item -LiteralPath $exe).Length
  $h = Get-Sha $exe
  if ($h -ne $ORIG_SHA -or $len -ne $ORIG_SIZE) { Stop-Run "來源 Ld95.exe hash 不符：$h ($len bytes)" }
  return [ordered]@{ path = $exe; size = $len; sha256 = $h; last_write_utc = (Get-Item -LiteralPath $exe).LastWriteTimeUtc.ToString('o') }
}
function Find-M045 {
  $cands = @()
  if ($M045Exe) { $cands += $M045Exe }
  $cands += @(
    (Join-Path $LD2Root 'zhTW_lab\runs\m045\build-first\Ld95.exe'),
    (Join-Path $LD2Root 'zhTW_lab\runs\m045\build-second\Ld95.exe'),
    (Join-Path $LD2Root 'zhTW_lab\game-acceptance\m046\game\Ld95.exe'),
    (Join-Path $LD2Root 'zhTW_lab\runs\m045-win\Ld95.exe')
  )
  foreach ($c in $cands) {
    if (Test-Path -LiteralPath $c) {
      $len = (Get-Item -LiteralPath $c).Length
      if ($len -eq $M045_SIZE) {
        $h = Get-Sha $c
        if ($h -eq $M045_SHA) { return [ordered]@{ path = [IO.Path]::GetFullPath($c); size = $len; sha256 = $h } }
        Write-Host "  候選 $c hash 不符：$h（略過）" -ForegroundColor Yellow
      }
    }
  }
  $lab = Join-Path $LD2Root 'zhTW_lab'
  if (Test-Path -LiteralPath $lab) {
    $hits = Get-ChildItem -LiteralPath $lab -Recurse -File -Force -ErrorAction SilentlyContinue |
      Where-Object { $_.Length -eq $M045_SIZE -and -not $_.FullName.StartsWith($DisposableRoot, [StringComparison]::OrdinalIgnoreCase) }
    foreach ($f in $hits) {
      if ((Get-Sha $f.FullName) -eq $M045_SHA) { return [ordered]@{ path = $f.FullName; size = $f.Length; sha256 = $M045_SHA } }
    }
  }
  return $null
}
function Show-M045Missing {
  Write-Host ''
  Write-Host '找不到 SHA-256 = 4a0910…9da7（7,118,848 bytes）的 m045 Ld95.exe。' -ForegroundColor Red
  Write-Host '請先「離線」生成（只讀原版、輸出到新資料夾、不碰遊戲目錄），例如：'
  Write-Host "  mkdir `"$LD2Root\zhTW_lab\runs\m045-win`""
  Write-Host "  cd `"$LD2Root\ld2-zhtw-patch-m051`""
  Write-Host "  python -B tools\build_patch.py --profile m045 --input `"$SourceDir\Ld95.exe`" --out `"$LD2Root\zhTW_lab\runs\m045-win\Ld95.exe`" --metadata-out `"$LD2Root\zhTW_lab\runs\m045-win\build.json`""
  Write-Host '生成後 hash 必須正好是 4a0910243d159af8007b5e77369c21f262d9e7a402bcb92a991e4c368ccd9da7，再重跑本腳本。'
  Write-Host '（或用 -M045Exe <路徑> 指定既有檔案。）'
  exit 3
}
function Get-ExitAssessment([int]$code, [datetime]$t0, $usrBefore, $usrAfter) {
  # 回傳 exit_policy：ok / soft-warn-exit1 / hard-stop，以及判定依據
  $since = $t0.AddSeconds(-5)
  $all = @(Get-WinEvent -FilterHashtable @{ LogName = 'Application'; StartTime = $since } -ErrorAction SilentlyContinue |
    Where-Object { ("$($_.Message)" -match '(?i)ld95') })
  $relevant = @($all | Where-Object {
    ($_.ProviderName -in @('Application Error', 'Windows Error Reporting', 'Application Hang')) -or ($_.Level -in @(1, 2))
  })
  $dumpDir = Join-Path $env:LOCALAPPDATA 'CrashDumps'
  $dumpsAll = @(if (Test-Path -LiteralPath $dumpDir) { Get-ChildItem -LiteralPath $dumpDir -Filter 'Ld95*' -File -Force -ErrorAction SilentlyContinue })
  $dumpsNew = @($dumpsAll | Where-Object { $_.LastWriteTime -ge $since })
  $werNew = @()
  foreach ($w in @((Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\WER'), (Join-Path $env:ProgramData 'Microsoft\Windows\WER'))) {
    foreach ($sub in @('ReportArchive', 'ReportQueue')) {
      $d = Join-Path $w $sub
      if (Test-Path -LiteralPath $d) {
        $werNew += @(Get-ChildItem -LiteralPath $d -Directory -Force -ErrorAction SilentlyContinue |
          Where-Object { $_.Name -match '(?i)ld95' -and $_.LastWriteTime -ge $since } | ForEach-Object { $_.Name })
      }
    }
  }
  $bmap = @{}; foreach ($u in @($usrBefore)) { if ($u) { $bmap[[string]$u.path] = [string]$u.sha256 } }
  $saves = @(@($usrAfter) | Where-Object { $_ -and ((Split-Path -Leaf ([string]$_.path)) -like 'LUNAS*.LDP') -and
    ((-not $bmap.ContainsKey([string]$_.path)) -or $bmap[[string]$_.path] -ne [string]$_.sha256) } | ForEach-Object { [string]$_.path })

  $policy = 'hard-stop'
  if ($code -eq 0) { $policy = 'ok' }
  elseif ($code -eq 1 -and $relevant.Count -eq 0 -and $dumpsNew.Count -eq 0 -and $werNew.Count -eq 0 -and $saves.Count -gt 0) { $policy = 'soft-warn-exit1' }
  $reasons = @()
  if ($code -ne 0) {
    if ($code -eq $EXIT_STACK_BUFFER_OVERRUN) { $reasons += '0xC0000409（STATUS_STACK_BUFFER_OVERRUN）' }
    elseif ($code -ne 1) { $reasons += ('結束碼不是 0 或 1：0x{0:X8}' -f $code) }
    if ($relevant.Count -gt 0) { $reasons += "有 $($relevant.Count) 筆 Ld95 相關錯誤／WER 事件" }
    if ($dumpsNew.Count -gt 0) { $reasons += "有 $($dumpsNew.Count) 個本次新增的 Ld95 dump" }
    if ($werNew.Count -gt 0) { $reasons += "有 $($werNew.Count) 個本次新增的 WER 報告" }
    if ($saves.Count -eq 0) { $reasons += '本次沒有新增或改變任何 Usr\LUNAS*.LDP 存檔' }
  }
  return [ordered]@{
    exit_policy = $policy
    is_0xC0000409 = ($code -eq $EXIT_STACK_BUFFER_OVERRUN)
    events_ld95_all = $all.Count
    events_relevant = $relevant.Count
    events_text = @($all | Select-Object -First 20 | ForEach-Object { "[$($_.TimeCreated.ToString('o'))] $($_.ProviderName) id=$($_.Id) level=$($_.Level)`n$($_.Message)" })
    crash_dumps_names_only = @($dumpsAll | ForEach-Object { "$($_.Name) $($_.Length) bytes $($_.LastWriteTimeUtc.ToString('o'))" })
    crash_dumps_new = @($dumpsNew | ForEach-Object { $_.Name })
    wer_reports_new = $werNew
    saves_changed = $saves
    hard_stop_reasons = $reasons
  }
}
function Show-Checklist {
  if ($Run2) {
    @'
=== 第二次（run2）：只跑 C～F＋G（每步一次；任何異常→立即停止，只蒐證） ===
R  -Run2：已完成檢查並建立 evidence-run2\（沿用 run1 的副本與第 1 格存檔）
C  -Run2 -LaunchStep C：m045 版（這一次啟動涵蓋 C、D、E）
   C：截圖 C-main-menu.png、C-file-menu.png、C-f1-help.png、C-statusbar.png
D  同一次：讀第 1 格 → 角色/道具/設施/戰鬥 UI 各一次（到得了才看）
   截圖 D-*.png；記豆腐字/?/截斷位置（道具名仍為日文＝預期）
E  同一次：存到第 2 格（不覆蓋第 1 格）→ 從遊戲選單「結束」正常退出
F  -Run2 -LaunchStep F：原版讀第 2 格 → 截圖 F-load.png（日期欄「?」為既知問題）
   → 存到第 3 格（新格，不覆蓋 1、2）→ 從選單正常退出（讓結束碼 1 可判為軟警告）
G  -Run2 -Finalize：hashes-after.json；確認原目錄未變
截圖請放 evidence-run2\screens\ ；填寫 evidence-run2\observations.md
結束碼 1＋無錯誤事件＋無 dump＋有存檔 → 黃字軟警告、可繼續；其他非 0 → 紅字停止。
崩潰/0xC0000409/MFC 錯誤框/無回應>60s/安全軟體封鎖 → 停止，不再啟動（之後仍可跑 G）。
'@ | Write-Host
    return
  }
  @'
=== 單次流程 A–G（每步一次；任何異常→立即停止，只蒐證） ===
A 已完成：副本＋hashes-before.json
B  -LaunchStep B：原版 → 新遊戲 → 存第 1 格 → 從選單正常退出
   截圖 B-title.png、B-save.png
C  -LaunchStep C：m045 版（這一次啟動涵蓋 C、D、E）
   C：截圖 C-main-menu.png、C-file-menu.png、C-f1-help.png、C-statusbar.png
D  同一次：讀第 1 格 → 角色/道具/設施/戰鬥 UI 各一次（到得了才看）
   截圖 D-*.png；記豆腐字/?/截斷位置（道具名仍為日文＝預期）
E  同一次：存到第 2 格（不覆蓋第 1 格）→ 正常退出
F  -LaunchStep F：原版讀第 2 格 → 截圖 F-load.png（日期欄「?」為既知問題）→ 存第 3 格 → 正常退出
G  -Finalize：hashes-after.json；確認原目錄 Ld95.exe 與 A 相同
截圖請放 evidence\screens\ ；填寫 observations.md（由 observations.template.md 複製）
結束碼 1＋無錯誤事件＋無 dump＋有存檔 → 黃字軟警告、可繼續；其他非 0 → 紅字停止。
'@ | Write-Host
}

# ---------- 共通前置 ----------
Write-Host "來源（只讀）：$SourceDir"
Write-Host "副本根目錄：  $DisposableRoot"
if ($Run2) { Write-Host '模式：第二次觀察（run2，只跑 C～F＋G）' -ForegroundColor Cyan }
if ($DisposableRoot.StartsWith($SourceDir, [StringComparison]::OrdinalIgnoreCase) -or
    $SourceDir.StartsWith($DisposableRoot, [StringComparison]::OrdinalIgnoreCase)) { Stop-Run '來源與副本路徑重疊' }
if ($DisposableRoot -match '(?i)\\steamapps\\|\\Program Files') { Stop-Run '副本不可放在 Steam / Program Files 底下' }
Assert-NotRunning

# ---------- 步驟 G ----------
if ($Finalize) {
  if (-not (Test-Path -LiteralPath $StateFile)) { if ($Run2) { Stop-Run '尚未執行 -Run2（步驟 R）' } else { Stop-Run '尚未執行步驟 A' } }
  $st = Read-Json $StateFile
  if (Get-Prop $st 'finalized') { Stop-Run '已完成 G，不重跑' }
  $before = Read-Json (Join-Path $Evidence 'hashes-before.json')
  $src = Assert-SourceExe
  $srcManifest = @(Get-Manifest $SourceDir -SkipUsr)
  $changed = Compare-Manifest $before.source_manifest $srcManifest
  $after = [ordered]@{
    schema = $(if ($Run2) { 'm060-observe-run2-hashes-after/1' } else { 'm060-observe-hashes-after/1' })
    taken_utc = (Get-Date).ToUniversalTime().ToString('o')
    source_exe = $src
    source_exe_same_as_before = ($src.sha256 -eq $before.source_exe.sha256 -and (ConvertTo-TimeText $src.last_write_utc) -eq (ConvertTo-TimeText $before.source_exe.last_write_utc))
    source_manifest_changes = $changed
    store_original_sha256 = Get-Sha (Join-Path $Store 'Ld95.original.exe')
    store_m045_sha256 = Get-Sha (Join-Path $Store 'Ld95.m045.exe')
    game_active_exe_sha256 = Get-Sha (Join-Path $Game 'Ld95.exe')
    game_usr = @(Get-UsrSnapshot)
    steps_done = @($st.steps_done)
    stopped = (Get-Prop $st 'stopped')
    production_can_apply = $false
    release_approved = $false
  }
  Write-Json (Join-Path $Evidence 'hashes-after.json') $after
  $st | Add-Member -NotePropertyName finalized -NotePropertyValue $true -Force
  Save-State $st
  if ($changed.Count -gt 0 -or -not $after.source_exe_same_as_before) {
    Write-Host '警告：原目錄有變動！見 hashes-after.json（計畫 §3 停止條件）。' -ForegroundColor Red
  } else { Write-Host '原目錄未變動。G 完成。' -ForegroundColor Green }
  $dest = if ($Run2) { 'zhTW_lab\runs\m060-observe-run2\' } else { 'zhTW_lab\runs\m060-observe\' }
  Write-Host "請把 $Evidence 的全部內容複製到 $LD2Root\$dest 後壓縮回傳（不要放 EXE、遊戲素材、存檔本體、dump 本體）。"
  exit 0
}

# ---------- 步驟 B / C / F ----------
if ($LaunchStep) {
  if ($Run2 -and $LaunchStep -eq 'B') { Stop-Run '第二次觀察不跑 B（沿用 run1 第 1 格存檔）' }
  if (-not (Test-Path -LiteralPath $StateFile)) { if ($Run2) { Stop-Run '尚未執行 -Run2（步驟 R）' } else { Stop-Run '尚未執行步驟 A' } }
  $st = Read-Json $StateFile
  $prevStop = Get-Prop $st 'stopped'
  if ($prevStop) {
    if (-not $Run2 -and $prevStop -eq $RUN1_STOP_TEXT) { Stop-Run "run1 已停在 $prevStop。第二次觀察請改用 -Run2（見 USER-STEPS）。" }
    Stop-Run "先前已觸發停止條件（$prevStop），不再啟動"
  }
  if (Get-Prop $st 'finalized') { Stop-Run '已完成 G' }
  $done = @($st.steps_done)
  if ($done -contains $LaunchStep) { Stop-Run "步驟 $LaunchStep 已執行過（每步一次）" }
  $order = @{ 'B' = @(); 'C' = @('B'); 'F' = @('B', 'C') }
  if ($Run2) { $order = @{ 'C' = @('R'); 'F' = @('R', 'C') } }
  foreach ($need in $order[$LaunchStep]) { if ($done -notcontains $need) { Stop-Run "需先完成步驟 $need" } }
  $null = Assert-SourceExe
  $which = if ($LaunchStep -eq 'C') { 'Ld95.m045.exe' } else { 'Ld95.original.exe' }
  $want = if ($LaunchStep -eq 'C') { $M045_SHA } else { $ORIG_SHA }
  $srcExe = Join-Path $Store $which
  if ((Get-Sha $srcExe) -ne $want) { Stop-Run "$which hash 不符" }
  $active = Join-Path $Game 'Ld95.exe'
  Assert-Writable $active
  Copy-Item -LiteralPath $srcExe -Destination $active -Force
  if ((Get-Sha $active) -ne $want) { Stop-Run '切換後 game\Ld95.exe hash 不符' }
  $usrBefore = @(Get-UsrSnapshot)
  Show-Checklist
  Write-Host "啟動步驟 $LaunchStep（$which）… 關閉遊戲後腳本才會繼續。請從遊戲選單「結束」離開。" -ForegroundColor Cyan
  $t0 = Get-Date
  $p = Start-Process -FilePath $active -WorkingDirectory $Game -PassThru
  $null = $p.Handle   # 保留 handle，確保之後讀得到 ExitCode
  $p.WaitForExit()
  $t1 = Get-Date
  $code = $p.ExitCode
  if ($null -eq $code) { $code = -1 }
  $usrAfter = @(Get-UsrSnapshot)
  $assess = Get-ExitAssessment $code $t0 $usrBefore $usrAfter
  $rec = [ordered]@{
    run = $(if ($Run2) { 'run2' } else { 'run1' })
    step = $LaunchStep; exe = $which; exe_sha256 = $want
    start_utc = $t0.ToUniversalTime().ToString('o'); end_utc = $t1.ToUniversalTime().ToString('o')
    seconds = [math]::Round(($t1 - $t0).TotalSeconds, 1)
    exit_code = $code; exit_code_hex = ('0x{0:X8}' -f $code)
    exit_policy = $assess.exit_policy
    is_0xC0000409 = $assess.is_0xC0000409
    events_ld95_all = $assess.events_ld95_all
    events_relevant = $assess.events_relevant
    crash_dumps_names_only = $assess.crash_dumps_names_only
    crash_dumps_new = $assess.crash_dumps_new
    wer_reports_new = $assess.wer_reports_new
    saves_changed = $assess.saves_changed
    hard_stop_reasons = $assess.hard_stop_reasons
    usr_before = $usrBefore; usr_after = $usrAfter
  }
  if ($code -ne 0) {
    $evFile = Join-Path $Evidence "launch-$LaunchStep-events.txt"
    Assert-Writable $evFile
    (@($assess.events_text) -join "`n----`n") | Out-File -LiteralPath $evFile -Encoding utf8
  }
  Write-Json (Join-Path $Evidence "launch-$LaunchStep.json") $rec
  $st.steps_done = @($done + $LaunchStep)
  if ($assess.exit_policy -eq 'hard-stop') { $st | Add-Member -NotePropertyName stopped -NotePropertyValue ("step $LaunchStep exit " + $rec.exit_code_hex) -Force }
  if ($assess.exit_policy -eq 'soft-warn-exit1') {
    $sw = @(Get-Prop $st 'soft_warnings') + ("step $LaunchStep exit 0x00000001")
    $st | Add-Member -NotePropertyName soft_warnings -NotePropertyValue @($sw | Where-Object { $_ }) -Force
  }
  Save-State $st
  switch ($assess.exit_policy) {
    'ok' {
      Write-Host "步驟 $LaunchStep 結束碼 0。記得截圖放 $Evidence\screens\ 並填 observations.md。" -ForegroundColor Green
    }
    'soft-warn-exit1' {
      Write-Host ''
      Write-Host "警告（軟警告，可繼續）：步驟 $LaunchStep 結束碼 0x00000001。" -ForegroundColor Yellow
      Write-Host '  無 Ld95 錯誤／WER 事件、無新 dump、且本次有存檔：' -ForegroundColor Yellow
      Write-Host ("  " + (@($assess.saves_changed) -join '、')) -ForegroundColor Yellow
      Write-Host '  判讀為這款遊戲從選單結束時的正常結束碼。請在 observations.md 寫明「是否從遊戲選單正常結束」。' -ForegroundColor Yellow
      Write-Host "  記得截圖放 $Evidence\screens\，然後照清單進行下一步。" -ForegroundColor Yellow
    }
    default {
      Write-Host ('原因：' + (@($assess.hard_stop_reasons) -join '；')) -ForegroundColor Red
      $g = if ($Run2) { '-Run2 -Finalize' } else { '-Finalize' }
      Write-Host "之後只可跑 $g 收尾 hash（不會啟動遊戲），然後回傳證據。" -ForegroundColor Red
      Stop-Run "結束碼 $($rec.exit_code_hex)；已匯出事件紀錄。若其實是正常退出，請在 observations.md 註明。"
    }
  }
  exit 0
}

# ---------- 步驟 R（第二次觀察準備，只檢查＋建立 evidence-run2） ----------
if ($Run2) {
  if ($CheckOnly) { Write-Host '-Run2 -CheckOnly：只檢查，不寫入。' -ForegroundColor Cyan }
  if (-not (Test-Path -LiteralPath $DisposableRoot)) {
    Stop-Run "找不到 run1 副本：$DisposableRoot。若副本在其他磁碟，請加 -LD2Root 或 -DisposableRoot；若已刪除，請停止並回報（需改走全新副本流程）。"
  }
  if (Test-Path -LiteralPath $Evidence) { Stop-Run "evidence-run2 已存在：$Evidence（每次觀察只準備一次，不覆蓋）" }
  $st1File = Join-Path $Evidence1 'state.json'
  $b1File = Join-Path $Evidence1 'launch-B.json'
  $hb1File = Join-Path $Evidence1 'hashes-before.json'
  foreach ($f in @($st1File, $b1File, $hb1File)) { if (-not (Test-Path -LiteralPath $f)) { Stop-Run "找不到 run1 證據：$f" } }
  $st1 = Read-Json $st1File
  $done1 = @($st1.steps_done)
  if (-not ($done1 -contains 'A' -and $done1 -contains 'B')) { Stop-Run 'run1 的 A、B 未完成' }
  if ($done1 -contains 'C' -or $done1 -contains 'F') { Stop-Run 'run1 已跑過 C/F，與預期不符，停止回報' }
  if ((Get-Prop $st1 'stopped') -ne $RUN1_STOP_TEXT) { Stop-Run "run1 停止原因不是預期的「$RUN1_STOP_TEXT」，停止回報" }
  # run1 步驟 B 依新規則重新判定（不重跑遊戲）
  $b1 = Read-Json $b1File
  $evText = ''
  $ev1 = Join-Path $Evidence1 'launch-B-events.txt'
  if (Test-Path -LiteralPath $ev1) { $evText = (Get-Content -LiteralPath $ev1 -Raw -Encoding UTF8) }
  if ($null -eq $evText) { $evText = '' }
  $evText = $evText.Trim([char]0xFEFF, ' ', "`r", "`n", "`t")
  $b1Usr = @(Get-Prop $b1 'usr_after') | Where-Object { $_ -and (Get-Prop $_ 'path') }
  $b1Saves = @($b1Usr | Where-Object { (Split-Path -Leaf ([string]$_.path)) -like 'LUNAS*.LDP' })
  if ([int]$b1.exit_code -ne 1 -or (Get-Prop $b1 'is_0xC0000409') -or @(Get-Prop $b1 'crash_dumps_names_only' | Where-Object { $_ }).Count -gt 0 -or
      $evText.Length -gt 0 -or $b1Saves.Count -eq 0) {
    Stop-Run 'run1 步驟 B 不符合軟警告條件（結束碼 1＋無事件＋無 dump＋有存檔），不續跑'
  }
  Write-Host 'run1 步驟 B 依新規則重新判定：soft-warn-exit1（結束碼 1、無事件、無 dump、有存檔）。' -ForegroundColor Yellow
  # 完整性：來源、exe-store、副本現況、第 1 格存檔未變
  $src = Assert-SourceExe
  $hb1 = Read-Json $hb1File
  Write-Host '計算來源清單 hash（略過 Usr\），與 run1 比對…'
  $srcManifest = @(Get-Manifest $SourceDir -SkipUsr)
  $chg = Compare-Manifest $hb1.source_manifest $srcManifest
  if ($chg.Count -gt 0) { $chg | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }; Stop-Run '原安裝自 run1 以來有變動（見上列）' }
  if ((Get-Sha (Join-Path $Store 'Ld95.original.exe')) -ne $ORIG_SHA) { Stop-Run 'exe-store\Ld95.original.exe hash 不符' }
  if ((Get-Sha (Join-Path $Store 'Ld95.m045.exe')) -ne $M045_SHA) { Stop-Run 'exe-store\Ld95.m045.exe hash 不符' }
  if ((Get-Sha (Join-Path $Game 'Ld95.exe')) -ne $ORIG_SHA) { Stop-Run 'game\Ld95.exe 不是原版（run1 收尾後應為原版）' }
  $usrNow = @(Get-UsrSnapshot)
  $usrChg = Compare-Manifest $b1Usr $usrNow
  if ($usrChg.Count -gt 0) { $usrChg | ForEach-Object { Write-Host "  $_" }; Stop-Run '副本 Usr\ 與 run1 步驟 B 結束時不同（第 1 格存檔被動過）' }
  $extra = @(Get-ChildItem -LiteralPath $Game -Recurse -File -Force | Where-Object {
    $rel = $_.FullName.Substring($Game.Length + 1)
    ($rel -notlike 'Usr\*') -and ($_.Extension -match '(?i)^\.(dll|asi|exe)$') -and ($rel -ne 'Ld95.exe')
  })
  if ($extra.Count -gt 0) { $extra | ForEach-Object { Write-Host "  $($_.FullName)" }; Stop-Run '副本內出現其他 mod／可執行檔' }
  Write-Host '完整性檢查全部通過。' -ForegroundColor Green
  if ($CheckOnly) { Write-Host '-CheckOnly：未寫入任何檔案。' -ForegroundColor Green; exit 0 }

  foreach ($d in @($Evidence, (Join-Path $Evidence 'screens'))) { Assert-Writable $d; New-Item -ItemType Directory -Path $d | Out-Null }
  $resolved = $DisposableRoot
  try { $it = Get-Item -LiteralPath $DisposableRoot -Force; if ($it.PSObject.Properties['Target'] -and $it.Target) { $resolved = [string](@($it.Target)[0]) } } catch { }
  $before = [ordered]@{
    schema = 'm060-observe-run2-hashes-before/1'
    approved = 'user approved 2026-10-28 (t33u): second disposable-copy m060 observation, steps C-F + G only, reusing run1 copy'
    taken_utc = (Get-Date).ToUniversalTime().ToString('o')
    windows = [Environment]::OSVersion.VersionString
    source_dir = $SourceDir
    disposable_root = $DisposableRoot
    disposable_root_resolved = $resolved
    source_exe = $src
    source_manifest_excludes = 'Usr\, LUNAS*（私人存檔，未讀取內容）'
    source_manifest = $srcManifest
    source_manifest_changes_since_run1 = $chg
    store_original_sha256 = $ORIG_SHA
    store_m045_sha256 = $M045_SHA
    game_usr_at_start = $usrNow
    run1_step_B_reassessed = [ordered]@{ exit_code = 1; exit_policy = 'soft-warn-exit1'; events = 0; dumps = 0; saves = @($b1Saves | ForEach-Object { "$($_.path) $($_.sha256)" }) }
    production_can_apply = $false
    release_approved = $false
  }
  Write-Json (Join-Path $Evidence 'hashes-before.json') $before
  Save-State ([ordered]@{ run = 'run2'; steps_done = @('A', 'B', 'R'); stopped = $null; finalized = $false; soft_warnings = @('run1 step B exit 0x00000001 (reassessed)') })
  $tpl = Join-Path $PSScriptRoot 'observations.template.md'
  if (Test-Path -LiteralPath $tpl) { Copy-Item -LiteralPath $tpl -Destination (Join-Path $Evidence 'observations.md') }
  Write-Host '步驟 R 完成：evidence-run2\ 已建立。' -ForegroundColor Green
  Show-Checklist
  exit 0
}

# ---------- 步驟 A（或 -CheckOnly）：全新副本 ----------
if (Test-Path -LiteralPath $DisposableRoot) {
  if (Test-Path -LiteralPath (Join-Path $Evidence1 'state.json')) { Stop-Run "副本資料夾已存在：$DisposableRoot。這是 run1 的副本——第二次觀察請用 -Run2。" }
  Stop-Run "副本資料夾已存在：$DisposableRoot（不覆蓋、不沿用）"
}
if (-not (Test-Path -LiteralPath $SourceDir)) { Stop-Run "找不到來源：$SourceDir（可用 -SourceDir 指定）" }
$srcBefore = Assert-SourceExe
Write-Host "來源 Ld95.exe OK：$($srcBefore.sha256)" -ForegroundColor Green

$extra = @(Get-ChildItem -LiteralPath $SourceDir -Recurse -File -Force | Where-Object {
  $rel = $_.FullName.Substring($SourceDir.Length + 1)
  ($rel -notlike 'Usr\*') -and ($_.Extension -match '(?i)^\.(dll|asi|exe)$') -and ($rel -ne 'Ld95.exe')
})
if ($extra.Count -gt 0) {
  $extra | ForEach-Object { Write-Host ("  {0}  {1}" -f $_.FullName.Substring($SourceDir.Length + 1), (Get-Sha $_.FullName)) }
  Stop-Run '來源含其他 mod／可執行檔（見上列），依計畫 §1 停止並回報。'
}
$m045 = Find-M045
if (-not $m045) { Show-M045Missing }
Write-Host "m045 OK：$($m045.path)" -ForegroundColor Green
if ($CheckOnly) { Write-Host '-CheckOnly：前置全部通過，未寫入任何檔案。' -ForegroundColor Green; exit 0 }

Write-Host '計算來源清單 hash（略過 Usr\）…'
$srcManifest = @(Get-Manifest $SourceDir -SkipUsr)

foreach ($d in @($DisposableRoot, $Game, $Store, $Evidence, (Join-Path $Evidence 'screens'))) {
  Assert-Writable $d; New-Item -ItemType Directory -Path $d | Out-Null
}
$rc = Join-Path $env:SystemRoot 'System32\robocopy.exe'
& $rc $SourceDir $Game /E /XD Usr LUNAS /XJ /COPY:DAT /DCOPY:DAT /R:0 /W:0 /NP /NFL /NDL /NJH | Out-Host
if ($LASTEXITCODE -ge 8) { Stop-Run "robocopy 失敗（$LASTEXITCODE）" }
New-Item -ItemType Directory -Path (Join-Path $Game 'Usr') | Out-Null

$gameExe = Join-Path $Game 'Ld95.exe'
if ((Get-Sha $gameExe) -ne $ORIG_SHA) { Stop-Run '副本內原版 hash 不符' }
Copy-Item -LiteralPath $gameExe -Destination (Join-Path $Store 'Ld95.original.exe')
Copy-Item -LiteralPath $m045.path -Destination (Join-Path $Store 'Ld95.m045.exe')
if ((Get-Sha (Join-Path $Store 'Ld95.m045.exe')) -ne $M045_SHA) { Stop-Run '複製後 m045 hash 不符' }

$srcAfter = Assert-SourceExe
if ($srcAfter.last_write_utc -ne $srcBefore.last_write_utc) { Stop-Run '來源 Ld95.exe 修改時間在複製期間改變' }
$usrCopied = @(Get-ChildItem -LiteralPath (Join-Path $Game 'Usr') -Recurse -Force)
if ($usrCopied.Count -gt 0) { Stop-Run '副本 Usr\ 不是空的' }

$before = [ordered]@{
  schema = 'm060-observe-hashes-before/1'
  approved = 'user approved 2026-10-28: one disposable-copy m060 observation only'
  taken_utc = (Get-Date).ToUniversalTime().ToString('o')
  windows = [Environment]::OSVersion.VersionString
  source_dir = $SourceDir
  disposable_root = $DisposableRoot
  source_exe = $srcBefore
  source_exe_after_copy = $srcAfter
  source_manifest_excludes = 'Usr\, LUNAS*（私人存檔，未讀取內容）'
  source_manifest = $srcManifest
  copy_original_sha256 = $ORIG_SHA
  m045 = $m045
  copy_excluded_dirs = @('Usr', 'LUNAS')
  saves_created = @()
  production_can_apply = $false
  release_approved = $false
}
Write-Json (Join-Path $Evidence 'hashes-before.json') $before
Save-State ([ordered]@{ steps_done = @('A'); stopped = $null; finalized = $false })
$tpl = Join-Path $PSScriptRoot 'observations.template.md'
if (Test-Path -LiteralPath $tpl) { Copy-Item -LiteralPath $tpl -Destination (Join-Path $Evidence 'observations.md') }
Write-Host '步驟 A 完成。' -ForegroundColor Green
Show-Checklist
