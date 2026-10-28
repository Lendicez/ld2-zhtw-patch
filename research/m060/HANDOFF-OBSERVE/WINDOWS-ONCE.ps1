<#
m060 可丟棄副本單次觀察（Win11）。使用者已於 2026-10-28 批准「一次」。
寫入範圍只限 $DisposableRoot（預設 <LD2_ROOT>\zhTW_lab\game-acceptance\m060\）：
  game\       遊戲副本（不含 Usr\ 私人存檔；建立空 Usr\）
  exe-store\  Ld95.original.exe / Ld95.m045.exe（切換時複製到 game\Ld95.exe，檔名不變）
  evidence\   hashes-before.json、launch-*.json、hashes-after.json（之後手動複製到 runs\m060-observe\）
來源資料夾（遊戲安裝）只讀：robocopy 只從來源讀，絕不寫入來源或 Steam 目錄。
不修改 production_can_apply / release_approved；不關 Defender、不改 ACL/locale。

用法（在 PowerShell，本次程序才用 Bypass，不改系統設定）：
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -CheckOnly
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1            # 步驟 A
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -LaunchStep B
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -LaunchStep C   # C+D+E 同一次 m045 啟動
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -LaunchStep F
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -Finalize       # 步驟 G
#>
[CmdletBinding()]
param(
  [string]$LD2Root = (Join-Path $env:SystemDrive 'GameDev\LD2'),  # 公開版：等同原預設 C:槽，避免寫死私人路徑
  [string]$SourceDir = '',
  [string]$M045Exe = '',
  [string]$DisposableRoot = '',
  [ValidateSet('', 'B', 'C', 'F')][string]$LaunchStep = '',
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

if (-not $SourceDir) { $SourceDir = Join-Path $LD2Root 'LunaticDawnPotB' }
if (-not $DisposableRoot) { $DisposableRoot = Join-Path $LD2Root 'zhTW_lab\game-acceptance\m060' }
$SourceDir = [IO.Path]::GetFullPath($SourceDir).TrimEnd('\')
$DisposableRoot = [IO.Path]::GetFullPath($DisposableRoot).TrimEnd('\')
$Game = Join-Path $DisposableRoot 'game'
$Store = Join-Path $DisposableRoot 'exe-store'
$Evidence = Join-Path $DisposableRoot 'evidence'
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
function Assert-NotRunning {
  $p = Get-Process -Name 'Ld95' -ErrorAction SilentlyContinue
  if ($p) { Stop-Run 'Ld95 正在執行（可能是 Steam 安裝版）。請先關閉遊戲。' }
}
function Assert-SourceExe {
  $exe = Join-Path $SourceDir 'Ld95.exe'
  if (-not (Test-Path -LiteralPath $exe)) { Stop-Run "找不到來源 $exe" }
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
  # 後援：在 zhTW_lab 底下找同大小檔案（排除本次副本）
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
function Show-Checklist {
  @'
=== 單次流程 A–G（每步一次；任何異常→立即停止，只蒐證） ===
A 已完成：副本＋hashes-before.json
B  -LaunchStep B：原版 → 新遊戲 → 存第 1 格 → 正常退出
   截圖 B-title.png、B-save.png
C  -LaunchStep C：m045 版（這一次啟動涵蓋 C、D、E）
   C：截圖 C-main-menu.png、C-file-menu.png、C-f1-help.png、C-statusbar.png
D  同一次：讀第 1 格 → 角色/道具/設施/戰鬥 UI 各一次（到得了才看）
   截圖 D-*.png；記豆腐字/?/截斷位置（道具名仍為日文＝預期）
E  同一次：存到第 2 格（不覆蓋第 1 格）→ 正常退出
F  -LaunchStep F：原版讀第 2 格 → 截圖 F-load.png（日期欄「?」為既知問題）
G  -Finalize：hashes-after.json；確認原目錄 Ld95.exe 與 A 相同
截圖請放 evidence\screens\ ；填寫 observations.md（由 observations.template.md 複製）
崩潰/0xC0000409/MFC 錯誤框/無回應>60s/安全軟體封鎖 → 停止，不再啟動。
'@ | Write-Host
}

# ---------- 共通前置 ----------
Write-Host "來源（只讀）：$SourceDir"
Write-Host "副本根目錄：  $DisposableRoot"
if ($DisposableRoot.StartsWith($SourceDir, [StringComparison]::OrdinalIgnoreCase) -or
    $SourceDir.StartsWith($DisposableRoot, [StringComparison]::OrdinalIgnoreCase)) { Stop-Run '來源與副本路徑重疊' }
if ($DisposableRoot -match '(?i)\\steamapps\\|\\Program Files') { Stop-Run '副本不可放在 Steam / Program Files 底下' }
Assert-NotRunning

# ---------- 步驟 G ----------
if ($Finalize) {
  if (-not (Test-Path -LiteralPath $StateFile)) { Stop-Run '尚未執行步驟 A' }
  $st = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
  if ($st.finalized) { Stop-Run '已完成 G，不重跑' }
  $before = Get-Content -LiteralPath (Join-Path $Evidence 'hashes-before.json') -Raw | ConvertFrom-Json
  $src = Assert-SourceExe
  $srcManifest = @(Get-Manifest $SourceDir -SkipUsr)
  $changed = @()
  $bmap = @{}; foreach ($m in $before.source_manifest) { $bmap[$m.path] = $m }
  foreach ($m in $srcManifest) {
    $b = $bmap[$m.path]
    if (-not $b) { $changed += "新增：$($m.path)" }
    elseif ($b.sha256 -ne $m.sha256 -or $b.last_write_utc -ne $m.last_write_utc) { $changed += "改變：$($m.path)" }
    $bmap.Remove($m.path)
  }
  foreach ($k in $bmap.Keys) { $changed += "消失：$k" }
  $after = [ordered]@{
    schema = 'm060-observe-hashes-after/1'
    taken_utc = (Get-Date).ToUniversalTime().ToString('o')
    source_exe = $src
    source_exe_same_as_before = ($src.sha256 -eq $before.source_exe.sha256 -and $src.last_write_utc -eq $before.source_exe.last_write_utc)
    source_manifest_changes = $changed
    store_original_sha256 = Get-Sha (Join-Path $Store 'Ld95.original.exe')
    store_m045_sha256 = Get-Sha (Join-Path $Store 'Ld95.m045.exe')
    game_active_exe_sha256 = Get-Sha (Join-Path $Game 'Ld95.exe')
    game_usr = Get-UsrSnapshot
    production_can_apply = $false
    release_approved = $false
  }
  Write-Json (Join-Path $Evidence 'hashes-after.json') $after
  $st | Add-Member -NotePropertyName finalized -NotePropertyValue $true -Force
  Save-State $st
  if ($changed.Count -gt 0 -or -not $after.source_exe_same_as_before) {
    Write-Host '警告：原目錄有變動！見 hashes-after.json（計畫 §3 停止條件）。' -ForegroundColor Red
  } else { Write-Host '原目錄未變動。G 完成。' -ForegroundColor Green }
  Write-Host "請把 $Evidence 的內容（不含任何 EXE / 存檔本體以外的遊戲素材）複製到 $LD2Root\zhTW_lab\runs\m060-observe\ 後壓縮回傳。"
  exit 0
}

# ---------- 步驟 B / C / F ----------
if ($LaunchStep) {
  if (-not (Test-Path -LiteralPath $StateFile)) { Stop-Run '尚未執行步驟 A' }
  $st = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
  if ($st.stopped) { Stop-Run "先前已觸發停止條件（$($st.stopped)），不再啟動" }
  if ($st.finalized) { Stop-Run '已完成 G' }
  $done = @($st.steps_done)
  if ($done -contains $LaunchStep) { Stop-Run "步驟 $LaunchStep 已執行過（每步一次）" }
  $order = @{ 'B' = @(); 'C' = @('B'); 'F' = @('B', 'C') }
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
  $usrBefore = Get-UsrSnapshot
  Show-Checklist
  Write-Host "啟動步驟 $LaunchStep（$which）… 關閉遊戲後腳本才會繼續。" -ForegroundColor Cyan
  $t0 = Get-Date
  $p = Start-Process -FilePath $active -WorkingDirectory $Game -PassThru
  $null = $p.Handle   # 保留 handle，確保之後讀得到 ExitCode
  $p.WaitForExit()
  $t1 = Get-Date
  $code = $p.ExitCode
  if ($null -eq $code) { $code = -1 }
  $rec = [ordered]@{
    step = $LaunchStep; exe = $which; exe_sha256 = $want
    start_utc = $t0.ToUniversalTime().ToString('o'); end_utc = $t1.ToUniversalTime().ToString('o')
    seconds = [math]::Round(($t1 - $t0).TotalSeconds, 1)
    exit_code = $code; exit_code_hex = ('0x{0:X8}' -f $code)
    usr_before = $usrBefore; usr_after = Get-UsrSnapshot
  }
  $crash = ($code -ne 0)
  if ($crash) {
    $ev = @(Get-WinEvent -FilterHashtable @{ LogName = 'Application'; StartTime = $t0.AddSeconds(-5) } -ErrorAction SilentlyContinue |
      Where-Object { $_.Message -match '(?i)ld95' } | Select-Object -First 20 |
      ForEach-Object { "[$($_.TimeCreated.ToString('o'))] $($_.ProviderName) id=$($_.Id)`n$($_.Message)" })
    $evFile = Join-Path $Evidence "launch-$LaunchStep-events.txt"
    Assert-Writable $evFile
    ($ev -join "`n----`n") | Out-File -LiteralPath $evFile -Encoding utf8
    $dumpDir = Join-Path $env:LOCALAPPDATA 'CrashDumps'
    $rec.crash_dumps_names_only = @(if (Test-Path $dumpDir) { Get-ChildItem $dumpDir -Filter 'Ld95*' -File | ForEach-Object { "$($_.Name) $($_.Length) bytes" } })
    $rec.is_0xC0000409 = ($code -eq $EXIT_STACK_BUFFER_OVERRUN)
  }
  Write-Json (Join-Path $Evidence "launch-$LaunchStep.json") $rec
  $st.steps_done = @($done + $LaunchStep)
  if ($crash) { $st | Add-Member -NotePropertyName stopped -NotePropertyValue ("step $LaunchStep exit " + $rec.exit_code_hex) -Force }
  Save-State $st
  if ($crash) { Stop-Run "結束碼 $($rec.exit_code_hex)；已匯出事件紀錄。若其實是正常退出，請在 observations.md 註明。" }
  Write-Host "步驟 $LaunchStep 結束碼 0。記得截圖放 evidence\screens\ 並填 observations.md。" -ForegroundColor Green
  exit 0
}

# ---------- 步驟 A（或 -CheckOnly） ----------
if (Test-Path -LiteralPath $DisposableRoot) { Stop-Run "副本資料夾已存在：$DisposableRoot（不覆蓋、不沿用）" }
if (-not (Test-Path -LiteralPath $SourceDir)) { Stop-Run "找不到來源：$SourceDir（可用 -SourceDir 指定）" }
$srcBefore = Assert-SourceExe
Write-Host "來源 Ld95.exe OK：$($srcBefore.sha256)" -ForegroundColor Green

# 其他 mod 檢查（LDWMM.dll 等）
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
# robocopy：只從來源讀；/XD 排除私人存檔資料夾；/XJ 不跟隨 junction；/R:0 /W:0 不重試
$rc = Join-Path $env:SystemRoot 'System32\robocopy.exe'
& $rc $SourceDir $Game /E /XD Usr LUNAS /XJ /COPY:DAT /DCOPY:DAT /R:0 /W:0 /NP /NFL /NDL /NJH | Out-Host
if ($LASTEXITCODE -ge 8) { Stop-Run "robocopy 失敗（$LASTEXITCODE）" }
New-Item -ItemType Directory -Path (Join-Path $Game 'Usr') | Out-Null   # 空的 Usr\，存檔只在副本內新建

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
  source_exe = $srcBefore
  source_exe_after_copy = $srcAfter
  source_manifest_excludes = 'Usr\, LUNAS*（私人存檔，未讀取內容）'
  source_manifest = $srcManifest
  copy_original_sha256 = $ORIG_SHA
  m045 = $m045
  copy_excluded_dirs = @('Usr', 'LUNAS')
  saves_created = @()   # 由 launch-B/C/F.json 的 usr_after 補
  production_can_apply = $false
  release_approved = $false
}
Write-Json (Join-Path $Evidence 'hashes-before.json') $before
Save-State ([ordered]@{ steps_done = @('A'); stopped = $null; finalized = $false })
$tpl = Join-Path $PSScriptRoot 'observations.template.md'
if (Test-Path -LiteralPath $tpl) { Copy-Item -LiteralPath $tpl -Destination (Join-Path $Evidence 'observations.md') }
Write-Host '步驟 A 完成。' -ForegroundColor Green
Show-Checklist
