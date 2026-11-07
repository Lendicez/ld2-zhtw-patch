<#
m061b 啟用版（清單 helper v2：Unicode 清單框＋TextOutW hook＋8 個清單點）功能驗收（Win11，可丟棄副本，只做一次）。

和 m061 啟用版 run1（57103342…ce5b，已於 2026-10-29 在 Win11 穩定執行）同樣的 hook 區段與 8 個清單點，差別：
  * 清單 helper 換成 m061b 的 @LD2_ListInsertU@24（MSVC 物件 e8144466…4d51，已在 Linux 稽核）；
  * 新增 4 個 USER32 匯入：IsWindowUnicode／GetWindowLongW／GetClassLongW／SetWindowLongW；
  * .ld2c 多一個政策字 LD2_ListMode：預設 2（未命中時把清單框切成 Unicode，讓假名能顯示）；
    加 -Mode0 會改用保底版（只有全部命中時才走 W，其餘完全照 m045）。
其他位元組（除 PE CheckSum）與對應的惰性合併結果相同。

寫入範圍只限你用 -DisposableRoot 明確指定的「新」資料夾（必填，沒有預設值）：
  game\       遊戲副本（不含原安裝的 Usr\）；Usr\ 只從 m060 可丟棄副本複製存檔（-SeedUsrFrom）
  exe-store\  Ld95.original.exe、Ld95.m061b-enabled.exe（hash 釘死）
  evidence\   hashes-before.json、launch-L.json、hashes-after.json、observations.md、screens\
遊戲安裝（來源）只讀；不改 Steam、不改系統設定；production_can_apply／release_approved 永遠 false。

用法（在本資料夾開 PowerShell；只對本次程序用 Bypass）：
  $D = "$env:SystemDrive\GameDev\LD2\zhTW_lab\game-acceptance\m061b-loader-enabled"
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-ENABLED-M061B.ps1 -DisposableRoot $D -CheckOnly
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-ENABLED-M061B.ps1 -DisposableRoot $D
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-ENABLED-M061B.ps1 -DisposableRoot $D -Launch
  powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-ENABLED-M061B.ps1 -DisposableRoot $D -Finalize
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$DisposableRoot,
  [string]$LD2Root = (Join-Path $env:SystemDrive 'GameDev\LD2'),
  [string]$SourceDir = '',
  [string]$M045Exe = '',
  [string]$SeedUsrFrom = '',
  [switch]$CheckOnly,
  [switch]$Launch,
  [switch]$Finalize,
  [switch]$Mode0
)
Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$ORIG_SHA = '6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2'
$ORIG_SIZE = 7090176
$M045_SHA = '4a0910243d159af8007b5e77369c21f262d9e7a402bcb92a991e4c368ccd9da7'
$M045_SIZE = 7118848
$LIST_OBJ_SHA = 'e8144466755d223a18f5d8f586510f64822c5cc1d793c708f171e964f6064d51'  # m061b MSVC list_insert_u.obj（已稽核）
if ($Mode0) {
  $LIST_MODE = 0
  $INERT_SHA = '287472ccd4c966b6f840ea2023b19e2a26cf783c6e7140e7a6935c5309236c99'
  $OUT_SHA = '49b623950708612c16b8b2a9f234ce499094104514820c84b7fb5c3d44d0d876'
  $DELTA_SHA = '4bbfc1904be23844ed9142d84f2bea94baaeeabf6b87d56242a6d31b9c651331'
  $DELTA_JSON_SHA = '1480c417faaca8a64895c1d035fcc9e5771d810724cb230cd98b1a560113cfa7'
} else {
  $LIST_MODE = 2
  $INERT_SHA = '6f9a8903f9a5ffeb68db1b7a0a0115a179c56084dd0beb0078bfcbe1d1fde1aa'
  $OUT_SHA = '3a1b75b35aca01a8b3e0e475ea8fd7454ebe2367f03165ebab18a7054825ed31'
  $DELTA_SHA = '5853948ca59d62d818f941cb91e3c4a80939e08077d392a47c2e1c50e27291cd'
  $DELTA_JSON_SHA = '32c09aa861b7b451cf4016614328b9610861ad371a5a7c7bd1bc4fd299e0aefc'
}
$OUT_SIZE = 7286784
$OUT_SIZE_OF_IMAGE = 0x70c000
$DELTA_SIZE = 168111
$HOOK_SPAN_OFF = 0x6dc7d
$HOOK_SPAN_LEN = 0x28
$HOOK_STUB_SHA = '67f30b3e3460e3035da33b684541fa8fd1c80d17c01c644a6ac857d8f64cca9e'
# 既有段內唯一允許改寫的位置：hook 區段＋8 個清單點的 rel32（檔案位移＝RVA）
$ALLOWED_CODE_RUNS = @('0x6dc7d:40', '0x92432:4', '0xaaf1a:4', '0xab0ff:4', '0xb1154:4', '0xb2d20:4', '0xb3478:4', '0xb46e5:4', '0xb4df2:4')
# 新匯入的 IAT 槽（VA）與檔案裡未綁定時的值（hint RVA）
$IAT_PROBES = @(
  @('GDI32!TextOutW', 0xb0b160, 0x70b14a),
  @('USER32!SendDlgItemMessageW', 0xb0b1e8, 0x70b174),
  @('USER32!IsWindowUnicode', 0xb0b1ec, 0x70b18a),
  @('USER32!GetWindowLongW', 0xb0b1f0, 0x70b19c),
  @('USER32!GetClassLongW', 0xb0b1f4, 0x70b1ae),
  @('USER32!SetWindowLongW', 0xb0b1f8, 0x70b1be)
)
$LIST_MODE_SLOT_VA = 0xb0a28c

if (-not $SourceDir) { $SourceDir = Join-Path $LD2Root 'LunaticDawnPotB' }
if (-not $SeedUsrFrom) { $SeedUsrFrom = Join-Path $LD2Root 'zhTW_lab\game-acceptance\m060\game\Usr' }
$SourceDir = [IO.Path]::GetFullPath($SourceDir).TrimEnd('\')
$DisposableRoot = [IO.Path]::GetFullPath($DisposableRoot).TrimEnd('\')
$Game = Join-Path $DisposableRoot 'game'
$Store = Join-Path $DisposableRoot 'exe-store'
$Evidence = Join-Path $DisposableRoot 'evidence'
$StateFile = Join-Path $Evidence 'state.json'
$DeltaBin = Join-Path $PSScriptRoot "m061b-enabled-mode$LIST_MODE.delta.bin"
$DeltaJson = Join-Path $PSScriptRoot "m061b-enabled-mode$LIST_MODE.delta.json"
$EnabledName = "Ld95.m061b-enabled-mode$LIST_MODE.exe"

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
  if ((Get-Sha $DeltaJson) -ne $DELTA_JSON_SHA) { Stop-Run "$(Split-Path -Leaf $DeltaJson) hash 不符" }
  if ((Get-Sha $DeltaBin) -ne $DELTA_SHA -or (Get-Item -LiteralPath $DeltaBin).Length -ne $DELTA_SIZE) { Stop-Run "$(Split-Path -Leaf $DeltaBin) hash 不符" }
  $man = Read-Json $DeltaJson
  if ($man.base_sha256 -ne $M045_SHA -or $man.out_sha256 -ne $OUT_SHA -or [int64]$man.out_size -ne $OUT_SIZE) { Stop-Run 'delta 說明檔與腳本內釘死的值不一致' }
  if ($man.production_can_apply -or -not $man.list_sites_patched -or -not $man.textoutw_hook_enabled -or $man.inert_sha256 -ne $INERT_SHA -or [int]$man.list_mode -ne $LIST_MODE -or $man.list_object_sha256 -ne $LIST_OBJ_SHA -or $man.list_profile -ne 'u') { Stop-Run 'delta 說明檔不是本 m061b 啟用版' }
  return $man
}
function Build-Enabled([string]$m045Path, $man) {
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
    if ($off -ge 0x1000 -and $off -lt $M045_SIZE -and ($ALLOWED_CODE_RUNS -notcontains ('0x{0:x}:{1}' -f $off, $len))) { Stop-Run "delta 試圖修改未核准的既有位置 @0x$($off.ToString('x'))" }
    if ($off -lt $M045_SIZE -and $off + $len -gt $M045_SIZE) { Stop-Run 'delta 區段跨越 m045 結尾' }
    [Array]::Copy($blob, $pos, $out, $off, $len)
    if ((Get-BytesSha $out $off $len) -ne $r.sha256) { Stop-Run "delta 區段 hash 不符 @$off" }
    $pos += $len
  }
  if ($pos -ne $blob.Length) { Stop-Run 'delta 長度未完全使用' }
  if ((Get-BytesSha $out $HOOK_SPAN_OFF $HOOK_SPAN_LEN) -ne $HOOK_STUB_SHA) { Stop-Run 'hook 區段不是核准的 stub' }
  if ((Get-BytesSha $out 0 $OUT_SIZE) -ne $OUT_SHA) { Stop-Run "合併結果 sha256 不符 $OUT_SHA" }
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
function Get-ModuleProbe([int]$procId, $man) {
  # 直接讀 32 位元 Ld95 的記憶體（固定基址 0x400000，無 relocation）。不依賴 MainModule（惰性版時為 null）。
  # 只讀：PROCESS_QUERY_LIMITED_INFORMATION|PROCESS_VM_READ。失敗只記錄原因，不影響判定。
  try {
    if (-not ('LD2Probe' -as [type])) {
      Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class LD2Probe {
  [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, IntPtr size, out IntPtr read);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
  public static byte[] Read(int pid, long addr, int n, out int err) {
    err = 0; IntPtr h = OpenProcess(0x1010, false, pid);
    if (h == IntPtr.Zero) { err = Marshal.GetLastWin32Error(); return null; }
    try { byte[] b = new byte[n]; IntPtr r;
      if (!ReadProcessMemory(h, new IntPtr(addr), b, new IntPtr(n), out r) || r.ToInt64() != n) { err = Marshal.GetLastWin32Error(); return null; }
      return b; } finally { CloseHandle(h); }
  }
}
"@
    }
    $err = 0
    $hdr = [LD2Probe]::Read($procId, 0x400000, 0x400, [ref]$err)
    if ($null -eq $hdr) { return [ordered]@{ ok = $false; note = "ReadProcessMemory/OpenProcess 失敗，Win32 錯誤 $err（5＝存取被拒：遊戲可能以系統管理員或相容性模式執行）" } }
    if ($hdr[0] -ne 0x4d -or $hdr[1] -ne 0x5a) { return [ordered]@{ ok = $false; note = '0x400000 不是 MZ' } }
    $pe = [BitConverter]::ToInt32($hdr, 0x3c)
    $soi = [BitConverter]::ToUInt32($hdr, $pe + 0x50)
    $iat = [ordered]@{}
    foreach ($e in $IAT_PROBES) {
      $w = [LD2Probe]::Read($procId, [int64]$e[1], 4, [ref]$err)
      if ($null -eq $w) { $iat[$e[0]] = "read-failed $err"; continue }
      $v = [BitConverter]::ToUInt32($w, 0)
      $bound = ($v -ne [uint32]$e[2]) -and ($v -ge 0x10000) -and -not ($v -ge 0x400000 -and $v -lt (0x400000 + $soi))
      $iat[$e[0]] = [ordered]@{ value = ('0x{0:X8}' -f $v); bound = $bound }
    }
    $mw = [LD2Probe]::Read($procId, [int64]$LIST_MODE_SLOT_VA, 4, [ref]$err)
    $modeInMem = if ($null -ne $mw) { [BitConverter]::ToUInt32($mw, 0) } else { "read-failed $err" }
    $codeOk = 0; $codeBad = @()
    foreach ($r in @($man.runs | Where-Object { $_.kind -eq 'code' })) {
      $b = [LD2Probe]::Read($procId, 0x400000 + [int64]$r.offset, [int]$r.length, [ref]$err)
      if ($null -ne $b -and (Get-BytesSha $b 0 $b.Length) -eq $r.sha256) { $codeOk++ } else { $codeBad += ('0x{0:x}' -f [int64]$r.offset) }
    }
    return [ordered]@{
      ok = $true
      method = 'ReadProcessMemory@0x400000'
      size_of_image = ('0x{0:X}' -f $soi)
      size_of_image_matches = ($soi -eq $OUT_SIZE_OF_IMAGE)
      iat = $iat
      code_runs_in_memory_ok = $codeOk
      code_runs_in_memory_bad = $codeBad
      list_mode_in_memory = $modeInMem
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
    schema = 'm061b-loader-enabled-hashes-after/1'
    taken_utc = (Get-Date).ToUniversalTime().ToString('o')
    source_exe = $src
    source_exe_same_as_before = ($src.sha256 -eq $before.source_exe.sha256 -and (ConvertTo-TimeText $src.last_write_utc) -eq (ConvertTo-TimeText $before.source_exe.last_write_utc))
    source_manifest_changes = $changed
    store_original_sha256 = Get-Sha (Join-Path $Store 'Ld95.original.exe')
    store_enabled_sha256 = Get-Sha (Join-Path $Store $EnabledName)
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
  Write-Host "請把 $Evidence 整個資料夾壓成 m061b-loader-enabled-evidence.zip 回傳（不要放 EXE、遊戲素材、存檔、dump 本體）。"
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
  if ((Get-Sha $active) -ne $OUT_SHA) { Stop-Run "game\Ld95.exe 不是 m061b 啟用版（模式 $LIST_MODE）；若 P 用了 -Mode0，-Launch／-Finalize 也要加 -Mode0" }
  $man = Assert-Delta
  Write-Host "啟動 m061b 啟用版（清單模式 $LIST_MODE）一次。"
  Write-Host '請依序（每個畫面截圖，檔名見 USER-STEPS）：' -ForegroundColor Cyan
  Write-Host '  1) 標題畫面 → 讀取存檔（第 2 格；沒有就第 1 格）' -ForegroundColor Cyan
  Write-Host '  2) 商店：購買清單、出售清單、強化清單（能開的都開）' -ForegroundColor Cyan
  Write-Host '  3) 酒館清單、旅館委託清單、委託一覽／委託資訊' -ForegroundColor Cyan
  Write-Host '  4) 任一道具的說明視窗（道具名稱那一行）' -ForegroundColor Cyan
  Write-Host '  5) 不要存檔；從遊戲選單「結束」離開' -ForegroundColor Cyan
  Write-Host '出現錯誤框、崩潰或卡住超過約 60 秒：先截圖，關閉它，不要重試。' -ForegroundColor Cyan
  $t0 = Get-Date
  $p = Start-Process -FilePath $active -WorkingDirectory $Game -PassThru
  $null = $p.Handle
  $probe = $null
  for ($i = 0; $i -lt 20 -and -not $p.HasExited; $i++) {
    Start-Sleep -Seconds 1
    if ($i -ge 7 -and -not $p.HasExited) { $p.Refresh(); if ($p.MainWindowHandle -ne [IntPtr]::Zero) { break } }
  }
  if (-not $p.HasExited) { $probe = Get-ModuleProbe $p.Id $man }
  if ($probe -and $probe.ok) {
    $c = if ($probe.size_of_image_matches -and $probe.code_runs_in_memory_bad.Count -eq 0) { 'Green' } else { 'Yellow' }
    Write-Host "載入檢查：SizeOfImage $($probe.size_of_image)（預期 0x70C000），記憶體內改寫點 $($probe.code_runs_in_memory_ok)/9 相符，清單模式字＝$($probe.list_mode_in_memory)" -ForegroundColor $c
  } elseif ($probe) { Write-Host "載入檢查未完成（不影響判定）：$($probe.note)" -ForegroundColor Yellow }
  Write-Host '等待遊戲結束…' -ForegroundColor Cyan
  $p.WaitForExit()
  $t1 = Get-Date
  $code = $p.ExitCode; if ($null -eq $code) { $code = -1 }
  $a = Get-Assessment $code $t0
  $rec = [ordered]@{
    step = 'L'; exe = $EnabledName; exe_sha256 = $OUT_SHA; list_mode = $LIST_MODE; list_object_sha256 = $LIST_OBJ_SHA
    start_utc = $t0.ToUniversalTime().ToString('o'); end_utc = $t1.ToUniversalTime().ToString('o')
    seconds = [math]::Round(($t1 - $t0).TotalSeconds, 1)
    exit_code = $code; exit_code_hex = ('0x{0:X8}' -f $code)
    exit_policy = $a.exit_policy
    events_ld95_all = $a.events_ld95_all; events_relevant = $a.events_relevant
    crash_dumps_new = $a.crash_dumps_new; wer_reports_new = $a.wer_reports_new
    module_probe = $probe
    list_sites_patched = $true; textoutw_hook_enabled = $true; production_can_apply = $false
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
    'ok' { Write-Host '步驟 L 結束碼 0、無錯誤事件。截圖放 evidence\screens\，填好 observations.md（必填），然後跑 -Finalize。' -ForegroundColor Green }
    'soft-warn-exit1' { Write-Host '步驟 L 結束碼 1（此遊戲從選單結束時的常見值），無錯誤事件／dump。請在 observations.md 寫明各清單畫面看到什麼、是否從選單結束（必填），然後跑 -Finalize。' -ForegroundColor Yellow }
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
$merged = Build-Enabled $m045.path $man
$SeedUsrFrom = [IO.Path]::GetFullPath($SeedUsrFrom).TrimEnd('\')
$seedOk = $false; $seedFiles = @()
if ($SeedUsrFrom.StartsWith($SourceDir, [StringComparison]::OrdinalIgnoreCase)) { Stop-Run '-SeedUsrFrom 不可指向原安裝（只能用 m060 可丟棄副本的存檔）' }
if ($SeedUsrFrom.StartsWith($DisposableRoot, [StringComparison]::OrdinalIgnoreCase)) { Stop-Run '-SeedUsrFrom 不可在本次副本內' }
if (Test-Path -LiteralPath $SeedUsrFrom) {
  $seedFiles = @(Get-ChildItem -LiteralPath $SeedUsrFrom -File -Force | Where-Object { $_.Name -like 'LUNAS*.LDP' })
  $seedOk = $seedFiles.Count -gt 0
}
if ($seedOk) { Write-Host "存檔來源 OK：$SeedUsrFrom（$($seedFiles.Count) 個 LUNAS*.LDP，只讀、複製到副本）" -ForegroundColor Green }
else { Write-Host "警告：$SeedUsrFrom 沒有 LUNAS*.LDP 存檔；副本的 Usr\ 會是空的，需要開新遊戲才能到商店／酒館。可用 -SeedUsrFrom 指定其他「可丟棄副本」的 Usr 資料夾。" -ForegroundColor Yellow }
Write-Host "記憶體內合併 OK（m061b 啟用版，清單模式 $LIST_MODE）：sha256 = $OUT_SHA（尚未寫檔）" -ForegroundColor Green
if ($CheckOnly) { Write-Host '-CheckOnly：前置全部通過，未寫入任何檔案。' -ForegroundColor Green; exit 0 }

Write-Host '計算來源清單 hash（略過 Usr\）…'
$srcManifest = @(Get-Manifest $SourceDir)
foreach ($d in @($DisposableRoot, $Game, $Store, $Evidence, (Join-Path $Evidence 'screens'))) { Assert-Writable $d; New-Item -ItemType Directory -Path $d | Out-Null }
$rc = Join-Path $env:SystemRoot 'System32\robocopy.exe'
& $rc $SourceDir $Game /E /XD Usr LUNAS /XJ /COPY:DAT /DCOPY:DAT /R:0 /W:0 /NP /NFL /NDL /NJH | Out-Host
if ($LASTEXITCODE -ge 8) { Stop-Run "robocopy 失敗（$LASTEXITCODE）" }
New-Item -ItemType Directory -Path (Join-Path $Game 'Usr') | Out-Null
$seeded = @()
if ($seedOk) {
  foreach ($f in $seedFiles) {
    $dst = Join-Path (Join-Path $Game 'Usr') $f.Name
    Assert-Writable $dst
    Copy-Item -LiteralPath $f.FullName -Destination $dst
    $seeded += [ordered]@{ name = $f.Name; size = $f.Length; sha256 = Get-Sha $dst }
  }
  Write-Host "已從 m060 可丟棄副本複製 $($seeded.Count) 個存檔到 game\Usr\。" -ForegroundColor Green
}
$gameExe = Join-Path $Game 'Ld95.exe'
if ((Get-Sha $gameExe) -ne $ORIG_SHA) { Stop-Run '副本內原版 hash 不符' }
Copy-Item -LiteralPath $gameExe -Destination (Join-Path $Store 'Ld95.original.exe')
$enabledPath = Join-Path $Store $EnabledName
Assert-Writable $enabledPath
[IO.File]::WriteAllBytes($enabledPath, $merged)
if ((Get-Sha $enabledPath) -ne $OUT_SHA) { Stop-Run '寫出後啟用版 EXE hash 不符' }
Assert-Writable $gameExe
Copy-Item -LiteralPath $enabledPath -Destination $gameExe -Force
if ((Get-Sha $gameExe) -ne $OUT_SHA) { Stop-Run 'game\Ld95.exe 換版後 hash 不符' }
$srcAfter = Assert-SourceExe
if ($srcAfter.last_write_utc -ne $srcBefore.last_write_utc) { Stop-Run '來源 Ld95.exe 修改時間在複製期間改變' }

$before = [ordered]@{
  schema = 'm061b-loader-enabled-hashes-before/1'
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
  enabled_exe_sha256 = $OUT_SHA
  enabled_exe_size = $OUT_SIZE
  inert_base_sha256 = $INERT_SHA
  list_mode = $LIST_MODE
  list_object_sha256 = $LIST_OBJ_SHA
  hook_stub_sha256 = $HOOK_STUB_SHA
  seed_usr_from = $SeedUsrFrom
  seeded_saves = $seeded
  list_sites_patched = $true
  textoutw_hook_enabled = $true
  production_can_apply = $false
  release_approved = $false
}
Write-Json (Join-Path $Evidence 'hashes-before.json') $before
Save-State ([ordered]@{ steps_done = @('P'); stopped = $null; finalized = $false })
$tpl = Join-Path $PSScriptRoot 'observations.template.md'
if (Test-Path -LiteralPath $tpl) { Copy-Item -LiteralPath $tpl -Destination (Join-Path $Evidence 'observations.md') }
Write-Host '步驟 P 完成：副本已建立，game\Ld95.exe ＝ m061b 啟用版（清單模式 $LIST_MODE）。下一步：-Launch' -ForegroundColor Green
