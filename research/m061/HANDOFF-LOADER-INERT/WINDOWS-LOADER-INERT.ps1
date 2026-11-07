<#
m061 惰性雙 helper loader 驗收（Win11，可丟棄副本，只做一次）。

目的：確認「m045＋.ld2t/.ld2c/.ld2i 三個新段＋2 個新匯入（GDI32!TextOutW、USER32!SendDlgItemMessageW）」
的 Ld95.exe 能被 Windows loader 載入並進到標題畫面。
惰性＝hook（RVA 0x6dc7d..0x6dca5）與 8 個清單呼叫點都「沒有」改，遊戲任何路徑都不會走到新程式碼。

寫入範圍只限你用 -DisposableRoot 明確指定的資料夾（必填，沒有預設值）：
  game\       遊戲副本（不含 Usr\ 私人存檔；建立空 Usr\）；game\Ld95.exe 換成惰性合併版
  exe-store\  Ld95.original.exe、Ld95.m061-inert.exe（hash 釘死）
  evidence\   hashes-before.json、launch-L.json、hashes-after.json、observations.md、screens\
遊戲安裝（來源）只讀；不改 Steam、不改系統設定；production_can_apply／release_approved 永遠 false。

用法（在本資料夾開 PowerShell；只對本次程序用 Bypass）：
  $D = "<磁碟>:\GameDev\LD2\zhTW_lab\game-acceptance\m061-loader-inert"
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-INERT.ps1 -DisposableRoot $D -CheckOnly
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-INERT.ps1 -DisposableRoot $D            # P：建副本＋寫惰性 EXE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-INERT.ps1 -DisposableRoot $D -Launch    # L：啟動一次到標題畫面
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-INERT.ps1 -DisposableRoot $D -Finalize  # G：收尾
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$DisposableRoot,
  [string]$LD2Root = (Join-Path $env:SystemDrive 'GameDev\LD2'),
  [string]$SourceDir = '',
  [string]$M045Exe = '',
  [switch]$CheckOnly,
  [switch]$Launch,
  [switch]$Finalize
)
Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$ORIG_SHA = '6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2'
$ORIG_SIZE = 7090176
$M045_SHA = '4a0910243d159af8007b5e77369c21f262d9e7a402bcb92a991e4c368ccd9da7'
$M045_SIZE = 7118848
$OUT_SHA = '6a43dc4e3d881a207f4b0dae2fcc5f1fca5d079d6fe90139115da84ac3ef1cfe'
$OUT_SIZE = 7286784
$OUT_SIZE_OF_IMAGE = 0x70c000
$DELTA_SHA = 'f26cdbb0c57ee52a91aa63429b82ddf261fe129f94b9a16949fe5e243c6ea64a'
$DELTA_SIZE = 168039
$DELTA_JSON_SHA = '0823981344bedbf1b3abb14ccb449a4082601c080f9ea6a0171afca1fbef9463'
$HOOK_SPAN_OFF = 0x6dc7d
$HOOK_SPAN_LEN = 0x28

if (-not $SourceDir) { $SourceDir = Join-Path $LD2Root 'LunaticDawnPotB' }
$SourceDir = [IO.Path]::GetFullPath($SourceDir).TrimEnd('\')
$DisposableRoot = [IO.Path]::GetFullPath($DisposableRoot).TrimEnd('\')
$Game = Join-Path $DisposableRoot 'game'
$Store = Join-Path $DisposableRoot 'exe-store'
$Evidence = Join-Path $DisposableRoot 'evidence'
$StateFile = Join-Path $Evidence 'state.json'
$DeltaBin = Join-Path $PSScriptRoot 'm061-inert.delta.bin'
$DeltaJson = Join-Path $PSScriptRoot 'm061-inert.delta.json'

function Stop-Run([string]$msg) {
  Write-Host ''
  Write-Host "停止：$msg" -ForegroundColor Red
  Write-Host '不重試、不換方法；只蒐證後回傳。' -ForegroundColor Red
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
function Get-BytesSha([byte[]]$b, [int]$off, [int]$len) {
  $h = [Security.Cryptography.SHA256]::Create()
  try { return (($h.ComputeHash($b, $off, $len) | ForEach-Object { $_.ToString('x2') }) -join '') } finally { $h.Dispose() }
}
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
  if ($null -eq $obj) { return $null }
  $pp = $obj.PSObject.Properties[$name]
  if ($pp) { return $pp.Value } else { return $null }
}
function ConvertTo-TimeText($v) {
  if ($v -is [datetime]) { return $v.ToUniversalTime().ToString('o') }
  return [string]$v
}
function Get-Manifest([string]$root) {
  $items = Get-ChildItem -LiteralPath $root -Recurse -File -Force | Where-Object {
    $rel = $_.FullName.Substring($root.Length + 1)
    -not ($rel -like 'Usr\*' -or $rel -like 'LUNAS*')
  } | Sort-Object FullName
  foreach ($f in $items) {
    [ordered]@{ path = $f.FullName.Substring($root.Length + 1); size = $f.Length; sha256 = Get-Sha $f.FullName; last_write_utc = $f.LastWriteTimeUtc.ToString('o') }
  }
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
  if (Get-Process -Name 'Ld95' -ErrorAction SilentlyContinue) { Stop-Run 'Ld95 正在執行（可能是 Steam 安裝版）。請先關閉遊戲。' }
}
function Assert-SourceExe {
  $exe = Join-Path $SourceDir 'Ld95.exe'
  if (-not (Test-Path -LiteralPath $exe)) { Stop-Run "找不到來源 $exe（遊戲不在預設位置時請加 -LD2Root 或 -SourceDir）" }
  $it = Get-Item -LiteralPath $exe
  $h = Get-Sha $exe
  if ($h -ne $ORIG_SHA -or $it.Length -ne $ORIG_SIZE) { Stop-Run "來源 Ld95.exe hash 不符：$h ($($it.Length) bytes)" }
  return [ordered]@{ path = $exe; size = $it.Length; sha256 = $h; last_write_utc = $it.LastWriteTimeUtc.ToString('o') }
}
function Find-M045 {
  $cands = @()
  if ($M045Exe) { $cands += $M045Exe }
  $cands += @(
    (Join-Path $LD2Root 'zhTW_lab\game-acceptance\m060\exe-store\Ld95.m045.exe'),
    (Join-Path $LD2Root 'zhTW_lab\runs\m045\build-first\Ld95.exe'),
    (Join-Path $LD2Root 'zhTW_lab\runs\m045\build-second\Ld95.exe'),
    (Join-Path $LD2Root 'zhTW_lab\runs\m045-win\Ld95.exe')
  )
  foreach ($c in $cands) {
    if ((Test-Path -LiteralPath $c) -and (Get-Item -LiteralPath $c).Length -eq $M045_SIZE) {
      $h = Get-Sha $c
      if ($h -eq $M045_SHA) { return [ordered]@{ path = [IO.Path]::GetFullPath($c); size = $M045_SIZE; sha256 = $h } }
      Write-Host "  候選 $c hash 不符：$h（略過）" -ForegroundColor Yellow
    }
  }
  $lab = Join-Path $LD2Root 'zhTW_lab'
  if (Test-Path -LiteralPath $lab) {
    $hits = Get-ChildItem -LiteralPath $lab -Recurse -File -Force -ErrorAction SilentlyContinue |
      Where-Object { $_.Length -eq $M045_SIZE -and -not $_.FullName.StartsWith($DisposableRoot, [StringComparison]::OrdinalIgnoreCase) }
    foreach ($f in $hits) { if ((Get-Sha $f.FullName) -eq $M045_SHA) { return [ordered]@{ path = $f.FullName; size = $M045_SIZE; sha256 = $M045_SHA } } }
  }
  return $null
}
function Assert-Delta {
  foreach ($f in @($DeltaBin, $DeltaJson)) { if (-not (Test-Path -LiteralPath $f)) { Stop-Run "缺少 $f（請完整解壓 zip）" } }
  if ((Get-Sha $DeltaJson) -ne $DELTA_JSON_SHA) { Stop-Run 'm061-inert.delta.json hash 不符' }
  if ((Get-Sha $DeltaBin) -ne $DELTA_SHA -or (Get-Item -LiteralPath $DeltaBin).Length -ne $DELTA_SIZE) { Stop-Run 'm061-inert.delta.bin hash 不符' }
  $man = Read-Json $DeltaJson
  if ($man.base_sha256 -ne $M045_SHA -or $man.out_sha256 -ne $OUT_SHA -or [int64]$man.out_size -ne $OUT_SIZE) { Stop-Run 'delta 說明檔與腳本內釘死的值不一致' }
  if ($man.production_can_apply -or $man.list_sites_patched -or $man.textoutw_hook_enabled) { Stop-Run 'delta 說明檔不是惰性版' }
  return $man
}
function Build-Inert([string]$m045Path, $man) {
  $base = [IO.File]::ReadAllBytes($m045Path)
  if ($base.Length -ne $M045_SIZE) { Stop-Run 'm045 長度不符' }
  $blob = [IO.File]::ReadAllBytes($DeltaBin)
  $out = New-Object byte[] $OUT_SIZE
  [Array]::Copy($base, $out, $base.Length)
  $pos = 0
  foreach ($r in @($man.runs)) {
    $off = [int]$r.offset; $len = [int]$r.length
    if ($off + $len -gt $OUT_SIZE -or $pos + $len -gt $blob.Length) { Stop-Run 'delta 區段越界' }
    if ($off -lt 0x1000 -and $off + $len -gt 0x1000) { Stop-Run 'delta 區段跨越 PE 標頭' }
    if ($off -ge 0x1000 -and $off -lt $M045_SIZE) { Stop-Run 'delta 試圖修改既有段（應只改標頭＋附加新段）' }
    [Array]::Copy($blob, $pos, $out, $off, $len)
    if ((Get-BytesSha $out $off $len) -ne $r.sha256) { Stop-Run "delta 區段 hash 不符 @$off" }
    $pos += $len
  }
  if ($pos -ne $blob.Length) { Stop-Run 'delta 長度未完全使用' }
  if ((Get-BytesSha $out $HOOK_SPAN_OFF $HOOK_SPAN_LEN) -ne (Get-BytesSha $base $HOOK_SPAN_OFF $HOOK_SPAN_LEN)) { Stop-Run 'hook 區段被改動（不應發生）' }
  if ((Get-BytesSha $out 0 $OUT_SIZE) -ne $OUT_SHA) { Stop-Run '合併結果 sha256 不符 6a43dc4e…1cfe' }
  return ,$out
}
function Get-Assessment([int]$code, [datetime]$t0) {
  $since = $t0.AddSeconds(-5)
  $all = @(Get-WinEvent -FilterHashtable @{ LogName = 'Application'; StartTime = $since } -ErrorAction SilentlyContinue |
    Where-Object { ("$($_.Message)" -match '(?i)ld95') })
  $relevant = @($all | Where-Object { ($_.ProviderName -in @('Application Error', 'Windows Error Reporting', 'Application Hang')) -or ($_.Level -in @(1, 2)) })
  $dumpDir = Join-Path $env:LOCALAPPDATA 'CrashDumps'
  $dumpsNew = @(if (Test-Path -LiteralPath $dumpDir) { Get-ChildItem -LiteralPath $dumpDir -Filter 'Ld95*' -File -Force -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $since } })
  $werNew = @()
  foreach ($w in @((Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\WER'), (Join-Path $env:ProgramData 'Microsoft\Windows\WER'))) {
    foreach ($sub in @('ReportArchive', 'ReportQueue')) {
      $d = Join-Path $w $sub
      if (Test-Path -LiteralPath $d) {
        $werNew += @(Get-ChildItem -LiteralPath $d -Directory -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '(?i)ld95' -and $_.LastWriteTime -ge $since } | ForEach-Object { $_.Name })
      }
    }
  }
  $policy = 'hard-stop'
  if ($code -eq 0 -and $relevant.Count -eq 0 -and $dumpsNew.Count -eq 0) { $policy = 'ok' }
  elseif ($code -eq 1 -and $relevant.Count -eq 0 -and $dumpsNew.Count -eq 0 -and $werNew.Count -eq 0) { $policy = 'soft-warn-exit1' }
  return [ordered]@{
    exit_policy = $policy
    events_ld95_all = $all.Count
    events_relevant = $relevant.Count
    events_text = @($all | Select-Object -First 20 | ForEach-Object { "[$($_.TimeCreated.ToString('o'))] $($_.ProviderName) id=$($_.Id) level=$($_.Level)`n$($_.Message)" })
    crash_dumps_new = @($dumpsNew | ForEach-Object { $_.Name })
    wer_reports_new = $werNew
  }
}
function Get-ModuleProbe([int]$procId) {
  # 用 32 位元 PowerShell 讀 32 位元 Ld95 的主模組大小（SizeOfImage 0x70c000 ＝ 新段已映射）。失敗不影響判定。
  $ps32 = Join-Path $env:SystemRoot 'SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
  if (-not (Test-Path -LiteralPath $ps32)) { return [ordered]@{ ok = $false; note = 'no SysWOW64 powershell' } }
  $cmd = "`$p = Get-Process -Id $procId -ErrorAction Stop; `$m = `$p.MainModule; 'MAIN|' + `$m.ModuleName + '|' + `$m.BaseAddress.ToInt64() + '|' + `$m.ModuleMemorySize; 'TITLE|' + `$p.MainWindowTitle; 'MODS|' + ((`$p.Modules | ForEach-Object { `$_.ModuleName }) -join ',')"
  try {
    $lines = @(& $ps32 -NoProfile -NonInteractive -Command $cmd 2>&1 | ForEach-Object { "$_" })
    $main = @($lines | Where-Object { $_ -like 'MAIN|*' })
    $mods = @($lines | Where-Object { $_ -like 'MODS|*' })
    $title = @($lines | Where-Object { $_ -like 'TITLE|*' })
    if ($main.Count -eq 0) { return [ordered]@{ ok = $false; note = ($lines -join ' / ') } }
    $f = $main[0].Split('|')
    $modList = if ($mods.Count) { @($mods[0].Substring(5).Split(',')) } else { @() }
    return [ordered]@{
      ok = $true
      main_module = $f[1]
      image_base = ('0x{0:X}' -f [int64]$f[2])
      module_memory_size = ('0x{0:X}' -f [int64]$f[3])
      size_of_image_matches_inert = ([int64]$f[3] -eq $OUT_SIZE_OF_IMAGE)
      window_title_present = ($title.Count -gt 0 -and $title[0].Length -gt 6)
      gdi32_loaded = [bool]($modList | Where-Object { $_ -ieq 'gdi32.dll' })
      user32_loaded = [bool]($modList | Where-Object { $_ -ieq 'user32.dll' })
      module_count = $modList.Count
    }
  } catch { return [ordered]@{ ok = $false; note = "$_" } }
}

# ---------- 共通前置 ----------
Write-Host "來源（只讀）：$SourceDir"
Write-Host "副本根目錄（只寫這裡）：$DisposableRoot"
if ($DisposableRoot.StartsWith($SourceDir, [StringComparison]::OrdinalIgnoreCase) -or
    $SourceDir.StartsWith($DisposableRoot, [StringComparison]::OrdinalIgnoreCase)) { Stop-Run '來源與副本路徑重疊' }
if ($DisposableRoot -match '(?i)\\steamapps\\|\\Program Files|\\Windows\\') { Stop-Run '副本不可放在 Steam / Program Files / Windows 底下' }
if ($DisposableRoot.Length -le 3) { Stop-Run '副本不可是磁碟根目錄' }
Assert-NotRunning

# ---------- G：收尾 ----------
if ($Finalize) {
  if (-not (Test-Path -LiteralPath $StateFile)) { Stop-Run '尚未執行準備步驟 P' }
  $st = Read-Json $StateFile
  if (Get-Prop $st 'finalized') { Stop-Run '已完成 G，不重跑' }
  $before = Read-Json (Join-Path $Evidence 'hashes-before.json')
  $src = Assert-SourceExe
  Write-Host '計算來源清單 hash（略過 Usr\），與準備時比對…'
  $changed = Compare-Manifest $before.source_manifest @(Get-Manifest $SourceDir)
  $after = [ordered]@{
    schema = 'm061-loader-inert-hashes-after/1'
    taken_utc = (Get-Date).ToUniversalTime().ToString('o')
    source_exe = $src
    source_exe_same_as_before = ($src.sha256 -eq $before.source_exe.sha256 -and (ConvertTo-TimeText $src.last_write_utc) -eq (ConvertTo-TimeText $before.source_exe.last_write_utc))
    source_manifest_changes = $changed
    store_original_sha256 = Get-Sha (Join-Path $Store 'Ld95.original.exe')
    store_inert_sha256 = Get-Sha (Join-Path $Store 'Ld95.m061-inert.exe')
    game_active_exe_sha256 = Get-Sha (Join-Path $Game 'Ld95.exe')
    steps_done = @($st.steps_done)
    stopped = (Get-Prop $st 'stopped')
    production_can_apply = $false
    release_approved = $false
  }
  Write-Json (Join-Path $Evidence 'hashes-after.json') $after
  $st | Add-Member -NotePropertyName finalized -NotePropertyValue $true -Force
  Save-State $st
  if ($changed.Count -gt 0 -or -not $after.source_exe_same_as_before) { Write-Host '警告：原目錄有變動！見 hashes-after.json。' -ForegroundColor Red }
  else { Write-Host '原目錄未變動。G 完成。' -ForegroundColor Green }
  Write-Host "請把 $Evidence 整個資料夾壓成 m061-loader-inert-evidence.zip 回傳（不要放 EXE、遊戲素材、存檔、dump 本體）。"
  exit 0
}

# ---------- L：啟動一次 ----------
if ($Launch) {
  if (-not (Test-Path -LiteralPath $StateFile)) { Stop-Run '尚未執行準備步驟 P' }
  $st = Read-Json $StateFile
  if (Get-Prop $st 'stopped') { Stop-Run "先前已停止（$($st.stopped)），不再啟動" }
  if (Get-Prop $st 'finalized') { Stop-Run '已完成 G' }
  if (@($st.steps_done) -contains 'L') { Stop-Run '步驟 L 已執行過（只啟動一次）' }
  $null = Assert-SourceExe
  $active = Join-Path $Game 'Ld95.exe'
  if ((Get-Sha $active) -ne $OUT_SHA) { Stop-Run 'game\Ld95.exe 不是惰性合併版（6a43dc4e…1cfe）' }
  Write-Host '啟動惰性合併版一次。看到「標題畫面」後截圖（L-title.png），再從標題選單「結束」離開；不需要開新遊戲或讀檔。' -ForegroundColor Cyan
  Write-Host '若出現錯誤框（例如「找不到程序進入點」「應用程式無法正常啟動 0xc000007b」）：先截圖，再按確定關閉。' -ForegroundColor Cyan
  $t0 = Get-Date
  $p = Start-Process -FilePath $active -WorkingDirectory $Game -PassThru
  $null = $p.Handle
  $probe = $null
  for ($i = 0; $i -lt 20 -and -not $p.HasExited; $i++) {
    Start-Sleep -Seconds 1
    if ($i -ge 7 -and -not $p.HasExited) { $p.Refresh(); if ($p.MainWindowHandle -ne [IntPtr]::Zero) { break } }
  }
  if (-not $p.HasExited) { $probe = Get-ModuleProbe $p.Id }
  if ($probe -and $probe.ok) {
    $c = if ($probe.size_of_image_matches_inert) { 'Green' } else { 'Yellow' }
    Write-Host "載入檢查：主模組大小 $($probe.module_memory_size)（預期 0x70C000）" -ForegroundColor $c
  }
  Write-Host '等待遊戲結束…' -ForegroundColor Cyan
  $p.WaitForExit()
  $t1 = Get-Date
  $code = $p.ExitCode; if ($null -eq $code) { $code = -1 }
  $a = Get-Assessment $code $t0
  $rec = [ordered]@{
    step = 'L'; exe = 'Ld95.m061-inert.exe'; exe_sha256 = $OUT_SHA
    start_utc = $t0.ToUniversalTime().ToString('o'); end_utc = $t1.ToUniversalTime().ToString('o')
    seconds = [math]::Round(($t1 - $t0).TotalSeconds, 1)
    exit_code = $code; exit_code_hex = ('0x{0:X8}' -f $code)
    exit_policy = $a.exit_policy
    events_ld95_all = $a.events_ld95_all; events_relevant = $a.events_relevant
    crash_dumps_new = $a.crash_dumps_new; wer_reports_new = $a.wer_reports_new
    module_probe = $probe
    list_sites_patched = $false; textoutw_hook_enabled = $false; production_can_apply = $false
  }
  if ($code -ne 0 -or $a.events_ld95_all -gt 0) {
    $ev = Join-Path $Evidence 'launch-L-events.txt'; Assert-Writable $ev
    (@($a.events_text) -join "`n----`n") | Out-File -LiteralPath $ev -Encoding utf8
  }
  Write-Json (Join-Path $Evidence 'launch-L.json') $rec
  $st.steps_done = @(@($st.steps_done) + 'L')
  if ($a.exit_policy -eq 'hard-stop') { $st | Add-Member -NotePropertyName stopped -NotePropertyValue ("step L exit " + $rec.exit_code_hex) -Force }
  Save-State $st
  switch ($a.exit_policy) {
    'ok' { Write-Host '步驟 L 結束碼 0、無錯誤事件。截圖放 evidence\screens\，填 observations.md，然後跑 -Finalize。' -ForegroundColor Green }
    'soft-warn-exit1' { Write-Host '步驟 L 結束碼 1（此遊戲從選單結束時的常見值），無錯誤事件／dump。請在 observations.md 寫明是否看到標題畫面、是否從選單結束，然後跑 -Finalize。' -ForegroundColor Yellow }
    default { Write-Host "結束碼 $($rec.exit_code_hex)、事件 $($a.events_relevant)、dump $(@($a.crash_dumps_new).Count)。之後只跑 -Finalize 收尾並回傳證據。" -ForegroundColor Red; exit 2 }
  }
  exit 0
}

# ---------- P：準備（或 -CheckOnly） ----------
if (Test-Path -LiteralPath $DisposableRoot) { Stop-Run "副本資料夾已存在：$DisposableRoot（不覆蓋、不沿用；請換一個新的路徑）" }
if (-not (Test-Path -LiteralPath $SourceDir)) { Stop-Run "找不到來源：$SourceDir（可用 -SourceDir 指定）" }
$srcBefore = Assert-SourceExe
Write-Host "來源 Ld95.exe OK：$($srcBefore.sha256)" -ForegroundColor Green
$extra = @(Get-ChildItem -LiteralPath $SourceDir -Recurse -File -Force | Where-Object {
  $rel = $_.FullName.Substring($SourceDir.Length + 1)
  ($rel -notlike 'Usr\*') -and ($_.Extension -match '(?i)^\.(dll|asi|exe)$') -and ($rel -ne 'Ld95.exe')
})
if ($extra.Count -gt 0) { $extra | ForEach-Object { Write-Host "  $($_.FullName)" }; Stop-Run '來源含其他 mod／可執行檔，停止回報' }
$man = Assert-Delta
Write-Host 'delta 檔 OK（hash 釘死）。' -ForegroundColor Green
$m045 = Find-M045
if (-not $m045) { Stop-Run '找不到 SHA-256 = 4a0910…9da7（7,118,848 bytes）的 m045 Ld95.exe；可用 -M045Exe <路徑> 指定。' }
Write-Host "m045 OK：$($m045.path)" -ForegroundColor Green
$merged = Build-Inert $m045.path $man
Write-Host "記憶體內合併 OK：sha256 = $OUT_SHA（尚未寫檔）" -ForegroundColor Green
if ($CheckOnly) { Write-Host '-CheckOnly：前置全部通過，未寫入任何檔案。' -ForegroundColor Green; exit 0 }

Write-Host '計算來源清單 hash（略過 Usr\）…'
$srcManifest = @(Get-Manifest $SourceDir)
foreach ($d in @($DisposableRoot, $Game, $Store, $Evidence, (Join-Path $Evidence 'screens'))) { Assert-Writable $d; New-Item -ItemType Directory -Path $d | Out-Null }
$rc = Join-Path $env:SystemRoot 'System32\robocopy.exe'
& $rc $SourceDir $Game /E /XD Usr LUNAS /XJ /COPY:DAT /DCOPY:DAT /R:0 /W:0 /NP /NFL /NDL /NJH | Out-Host
if ($LASTEXITCODE -ge 8) { Stop-Run "robocopy 失敗（$LASTEXITCODE）" }
New-Item -ItemType Directory -Path (Join-Path $Game 'Usr') | Out-Null
$gameExe = Join-Path $Game 'Ld95.exe'
if ((Get-Sha $gameExe) -ne $ORIG_SHA) { Stop-Run '副本內原版 hash 不符' }
Copy-Item -LiteralPath $gameExe -Destination (Join-Path $Store 'Ld95.original.exe')
$inertPath = Join-Path $Store 'Ld95.m061-inert.exe'
Assert-Writable $inertPath
[IO.File]::WriteAllBytes($inertPath, $merged)
if ((Get-Sha $inertPath) -ne $OUT_SHA) { Stop-Run '寫出後惰性 EXE hash 不符' }
Assert-Writable $gameExe
Copy-Item -LiteralPath $inertPath -Destination $gameExe -Force
if ((Get-Sha $gameExe) -ne $OUT_SHA) { Stop-Run 'game\Ld95.exe 換版後 hash 不符' }
$srcAfter = Assert-SourceExe
if ($srcAfter.last_write_utc -ne $srcBefore.last_write_utc) { Stop-Run '來源 Ld95.exe 修改時間在複製期間改變' }

$before = [ordered]@{
  schema = 'm061-loader-inert-hashes-before/1'
  taken_utc = (Get-Date).ToUniversalTime().ToString('o')
  windows = [Environment]::OSVersion.VersionString
  source_dir = $SourceDir
  disposable_root = $DisposableRoot
  source_exe = $srcBefore
  source_exe_after_copy = $srcAfter
  source_manifest_excludes = 'Usr\, LUNAS*（私人存檔，未讀取內容）'
  source_manifest = $srcManifest
  m045 = $m045
  delta_sha256 = $DELTA_SHA
  inert_exe_sha256 = $OUT_SHA
  inert_exe_size = $OUT_SIZE
  hook_span_unchanged = $true
  list_sites_patched = $false
  textoutw_hook_enabled = $false
  production_can_apply = $false
  release_approved = $false
}
Write-Json (Join-Path $Evidence 'hashes-before.json') $before
Save-State ([ordered]@{ steps_done = @('P'); stopped = $null; finalized = $false })
$tpl = Join-Path $PSScriptRoot 'observations.template.md'
if (Test-Path -LiteralPath $tpl) { Copy-Item -LiteralPath $tpl -Destination (Join-Path $Evidence 'observations.md') }
Write-Host '步驟 P 完成：副本已建立，game\Ld95.exe ＝ 惰性合併版。下一步：-Launch' -ForegroundColor Green
