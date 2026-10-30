<#
m063d：catalog v4 啟用驗收（Win11，可丟棄副本，惰性版先、啟用版後，各啟動一次）。

這一包「不編譯」：MSVC 物件已在 m063b 由使用者在 Win11 編好並 pin，Linux 已用它們合併出兩個 EXE 並全部稽核：
  * 惰性版（inert）：新段 .ld2t／.ld2c／.ld2i 與新匯入都在，但 hook 區段、18 個清單點、26 個 TextOut 點都沒改
    ＝ 遊戲行為應與 m045 相同。用來先確認「新段＋新匯入」本身能載入、能玩。
  * 啟用版（enabled）：hook 區段改呼叫 _LD2_NamePair@16；18 個清單點（7 道具／11 人名）改呼叫 v4 清單 helper；
    25＋1 個名字 TextOut 點改呼叫 @LD2_NameTextOut@24。catalog 為 lab_preview v4（1817 列譯名＋m051，6148 列），
    不是可發行的 catalog。
兩者只差 45 個核准位置（窗共 245 bytes，其中 228 bytes 不同）與 PE CheckSum；惰性版由啟用版在記憶體內還原，不另帶檔。

寫入範圍只限你用 -DisposableRoot 明確指定的「新」資料夾（必填，沒有預設值）：
  game\       遊戲副本（不含原安裝的 Usr\）；Usr\ 只從 m060 可丟棄副本複製存檔（-SeedUsrFrom）
  exe-store\  Ld95.original.exe、Ld95.m063d-inert-modeN.exe、Ld95.m063d-enabled-modeN.exe（hash 釘死）
  evidence\   hashes-before.json、launch-L1.json、enable-E.json、launch-L2.json、hashes-after.json、
              observations.md、screens\、state.json
遊戲安裝（來源）只讀；不改 Steam、不改系統設定；production_can_apply／release_approved 永遠 false。
本腳本沒有任何「寫回正式安裝」的功能；-Finalize 只做唯讀比對（確認原目錄沒被動過）。

步驟（在本資料夾開 PowerShell；只對本次程序用 Bypass）：
  -CheckOnly      只檢查（不寫檔）
  （無開關）       P：建立副本，game\Ld95.exe ＝ 惰性版
  -LaunchInert    L1：惰性版啟動一次（標題→讀檔→一個商店清單→選單結束）
  -Enable         E：L1 通過後，把 game\Ld95.exe 換成啟用版（只換副本內的檔）
  -LaunchEnabled  L2：啟用版啟動一次（觀察巡迴）
  -Finalize       G：唯讀比對原安裝（一定要跑，失敗也要）
  -Pack           Z：檢查 evidence 只含紀錄與截圖，壓成桌面上的 zip
加 -Mode0 改用保底版（清單只在全部命中時走 W）；要用新的 -DisposableRoot。
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$DisposableRoot,
  [string]$LD2Root = (Join-Path $env:SystemDrive 'GameDev\LD2'),
  [string]$SourceDir = '',
  [string]$M045Exe = '',
  [string]$SeedUsrFrom = '',
  [switch]$CheckOnly,
  [switch]$LaunchInert,
  [switch]$Enable,
  [switch]$LaunchEnabled,
  [switch]$Finalize,
  [switch]$Pack,
  [switch]$Mode0
)
Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

#region consts
$ORIG_SHA = '6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2'
$ORIG_SIZE = 7090176
$M045_SHA = '4a0910243d159af8007b5e77369c21f262d9e7a402bcb92a991e4c368ccd9da7'
$M045_SIZE = 7118848
# m063b MSVC 物件（使用者 Win11 編譯、Linux 稽核後 pin）
$NAME_OBJ_SHA = 'bf33cfc674f28fd6f8bb069d76176f45d1309a8ab3198f068fc31c3ed87792e6'
$LIST_OBJ_SHA = 'cb74d585c9936f41debc831c863e1eb91dd652770ba4911660e16dd4e3c72b35'
$TEXTOUT_OBJ_SHA = '76d0adb7cecc82e54c1e0543a2d5f8b932f3b2d9f82a255ac6941390385cc0f6'
$BLOB_SHA = 'bbe4974f321ca128e4479e774b84da9080de7b4fa351d1f7c3ecc2e6223d1502'
$CATALOG_POLICY = 'lab_preview'
if ($Mode0) {
  $LIST_MODE = 0
  $INERT_SHA = '811c0788c15836055516e3f77ce4129641bec05a0a31c80be23d7ff28713675c'
  $OUT_SHA = 'bdba6fb06bc328cb561fe0ca100a8af2e48e407acdf1a619826c0e957f4716d3'
  $DELTA_SHA = '023f6e15688253709b40fe89800ec0da3d427b819be6fb7370006bf92e452dd1'
  $DELTA_JSON_SHA = 'de9d284ed0f2e7924a733ad0504776f6f98f7361cd2111845e66392be242e556'
} else {
  $LIST_MODE = 2
  $INERT_SHA = 'c796bc12378440b1ea027c5e268b0f564aff47bd4675b3a61bc1465068726e37'
  $OUT_SHA = '240ab04d7f81f185820865549c72b12a0c73475bb1f8dd073146731dab3f4121'
  $DELTA_SHA = '6dd23ce18c1ed41e425a906d09c7575a36464ad3ebddadf0ffb0b8f315516490'
  $DELTA_JSON_SHA = '2b84a4d56c9a80a20d4e2930abcaef274e789c78ff478dea21edb5c810ed390d'
}
$OUT_SIZE = 7393280
$OUT_SIZE_OF_IMAGE = 0x726000
$DELTA_SIZE = 274780
$HOOK_SPAN_OFF = 0x6dc7d
$HOOK_SPAN_LEN = 0x28
# 既有段內唯一允許改寫的位置（檔案位移＝RVA）：hook 區段＋18 個清單點 rel32＋26 個 TextOut 點
$ALLOWED_CODE_RUNS = @(
  '0x38a0c:5', '0x38a3b:5', '0x38a51:5', '0x38ad7:5', '0x38b06:5', '0x38b1c:5', '0x38ba2:5', '0x38bd1:5', '0x38be7:5',
  '0x38c6d:5', '0x38c9f:5', '0x38cb8:5', '0x38d3c:5', '0x38d6e:5', '0x38d87:5', '0x38e0b:5', '0x38e3d:5', '0x38e56:5',
  '0x6dc7d:40', '0x6e73b:4', '0x735f7:4', '0x74eae:4', '0x7502d:4', '0x75bbf:4', '0x7c243:4', '0x7db6b:4', '0x81d43:4',
  '0x8f442:5', '0x8f47e:8', '0x92432:4', '0x97a21:4', '0xaaf1a:4', '0xab0ff:4', '0xb1154:4', '0xb2d20:4', '0xb3478:4',
  '0xb46e5:4', '0xb4df2:4', '0xb9573:5', '0xb958a:5', '0xcb4b3:4', '0xd9719:5', '0xd98d1:5', '0xddcc9:5', '0xdde81:5'
)
# 新匯入的 IAT 槽（VA）與檔案裡未綁定時的值（hint RVA）
$IAT_PROBES = @(
  @('GDI32!TextOutW', 0xb25160, 0x72514a),
  @('USER32!SendDlgItemMessageW', 0xb251e8, 0x725174),
  @('USER32!IsWindowUnicode', 0xb251ec, 0x72518a),
  @('USER32!GetWindowLongW', 0xb251f0, 0x72519c),
  @('USER32!GetClassLongW', 0xb251f4, 0x7251ae),
  @('USER32!SetWindowLongW', 0xb251f8, 0x7251be)
)
$LIST_MODE_SLOT_VA = 0xae600c
$EVIDENCE_EXT_OK = @('.json', '.md', '.txt', '.png', '.jpg', '.jpeg')
$EVIDENCE_MAX_FILE = 15MB
#endregion consts

if (-not $SourceDir) { $SourceDir = Join-Path $LD2Root 'LunaticDawnPotB' }
if (-not $SeedUsrFrom) { $SeedUsrFrom = Join-Path $LD2Root 'zhTW_lab\game-acceptance\m060\game\Usr' }
$SourceDir = [IO.Path]::GetFullPath($SourceDir).TrimEnd('\')
$DisposableRoot = [IO.Path]::GetFullPath($DisposableRoot).TrimEnd('\')
$Game = Join-Path $DisposableRoot 'game'
$Store = Join-Path $DisposableRoot 'exe-store'
$Evidence = Join-Path $DisposableRoot 'evidence'
$StateFile = Join-Path $Evidence 'state.json'
$DeltaBin = Join-Path $PSScriptRoot "m063d-v4-lab_preview-mode$LIST_MODE.delta.bin"
$DeltaJson = Join-Path $PSScriptRoot "m063d-v4-lab_preview-mode$LIST_MODE.delta.json"
$InertName = "Ld95.m063d-inert-mode$LIST_MODE.exe"
$EnabledName = "Ld95.m063d-enabled-mode$LIST_MODE.exe"
$ZipPath = Join-Path ([Environment]::GetFolderPath('Desktop')) "m063d-v4-enable-mode$LIST_MODE-evidence.zip"

function Stop-Run([string]$msg) {
  Write-Host ''
  Write-Host "停止：$msg" -ForegroundColor Red
  Write-Host '不重試、不換方法；接著只跑 -Finalize 與 -Pack，把 zip 回傳。' -ForegroundColor Red
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
function Add-Step($st, [string]$step) { $st.steps_done = @(@($st.steps_done) + $step) }
function Set-Stopped($st, [string]$why) { $st | Add-Member -NotePropertyName stopped -NotePropertyValue $why -Force }
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
  if ($man.schema -ne 'm063d-v4-enabled-delta/1' -or $man.base_sha256 -ne $M045_SHA -or $man.out_sha256 -ne $OUT_SHA -or [int64]$man.out_size -ne $OUT_SIZE) { Stop-Run 'delta 說明檔與腳本內釘死的值不一致' }
  if ($man.production_can_apply -or $man.release_approved -or $man.inert_sha256 -ne $INERT_SHA -or [int]$man.list_mode -ne $LIST_MODE -or
      $man.list_object_sha256 -ne $LIST_OBJ_SHA -or $man.name_object_sha256 -ne $NAME_OBJ_SHA -or $man.textout_object_sha256 -ne $TEXTOUT_OBJ_SHA -or
      $man.blob_sha256 -ne $BLOB_SHA -or $man.catalog_policy -ne $CATALOG_POLICY -or -not $man.hook_enabled) { Stop-Run 'delta 說明檔不是本 m063d v4 啟用版' }
  return $man
}
function Build-Enabled([byte[]]$base, $man) {
  if ($base.Length -ne $M045_SIZE -or (Get-BytesSha $base 0 $base.Length) -ne $M045_SHA) { Stop-Run 'm045 內容不符' }
  $blob = [IO.File]::ReadAllBytes($DeltaBin)
  $out = New-Object byte[] $OUT_SIZE
  [Array]::Copy($base, $out, $base.Length)
  $pos = 0; $codeRuns = 0
  foreach ($r in @($man.runs)) {
    $off = [int]$r.offset; $len = [int]$r.length
    if ($off + $len -gt $OUT_SIZE -or $pos + $len -gt $blob.Length) { Stop-Run 'delta 區段越界' }
    if ($off -lt 0x1000 -and $off + $len -gt 0x1000) { Stop-Run 'delta 區段跨越 PE 標頭' }
    if ($off -ge 0x1000 -and $off -lt $M045_SIZE) {
      if ($ALLOWED_CODE_RUNS -notcontains ('0x{0:x}:{1}' -f $off, $len) -or $r.kind -ne 'code') { Stop-Run "delta 試圖修改未核准的既有位置 @0x$($off.ToString('x'))" }
      $codeRuns++
    }
    if ($off -lt $M045_SIZE -and $off + $len -gt $M045_SIZE) { Stop-Run 'delta 區段跨越 m045 結尾' }
    [Array]::Copy($blob, $pos, $out, $off, $len)
    if ((Get-BytesSha $out $off $len) -ne $r.sha256) { Stop-Run "delta 區段 hash 不符 @$off" }
    $pos += $len
  }
  if ($pos -ne $blob.Length) { Stop-Run 'delta 長度未完全使用' }
  if ($codeRuns -ne $ALLOWED_CODE_RUNS.Count) { Stop-Run "核准位置數不符（$codeRuns／$($ALLOWED_CODE_RUNS.Count)）" }
  if ((Get-BytesSha $out $HOOK_SPAN_OFF $HOOK_SPAN_LEN) -ne $man.hook_stub_sha256) { Stop-Run 'hook 區段不是核准的 stub' }
  if ((Get-BytesSha $out 0 $OUT_SIZE) -ne $OUT_SHA) { Stop-Run "啟用版合併結果 sha256 不符 $OUT_SHA" }
  return ,$out
}
function Build-Inert([byte[]]$enabled, [byte[]]$base, $man) {
  # 惰性版＝啟用版把 45 個核准位置還原成 m045 原 bytes，再寫回惰性版的 PE CheckSum
  $out = New-Object byte[] $enabled.Length
  [Array]::Copy($enabled, $out, $enabled.Length)
  foreach ($r in @($man.runs | Where-Object { $_.kind -eq 'code' })) { [Array]::Copy($base, [int]$r.offset, $out, [int]$r.offset, [int]$r.length) }
  $ck = [Convert]::ToUInt32(([string]$man.inert_checksum).Substring(2), 16)
  [Array]::Copy([BitConverter]::GetBytes($ck), 0, $out, [int]$man.inert_checksum_offset, 4)
  if ((Get-BytesSha $out 0 $out.Length) -ne $INERT_SHA) { Stop-Run "惰性版還原結果 sha256 不符 $INERT_SHA" }
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
function Get-ModuleProbe([int]$procId, $man, [byte[]]$expect) {
  # 直接讀 32 位元 Ld95 的記憶體（固定基址 0x400000，無 relocation）。只讀；失敗只記錄原因，不影響判定。
  # 45 個核准位置在記憶體內應等於「這次啟動的 EXE」在檔案裡的 bytes（惰性版＝m045 原樣，啟用版＝新呼叫）。
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
    if ($null -eq $hdr) { return [ordered]@{ ok = $false; note = "ReadProcessMemory/OpenProcess 失敗，Win32 錯誤 $err（5＝存取被拒：常見於相容性模式或權限設定；不影響判定）" } }
    if ($hdr[0] -ne 0x4d -or $hdr[1] -ne 0x5a) { return [ordered]@{ ok = $false; note = '0x400000 不是 MZ' } }
    $pe = [BitConverter]::ToInt32($hdr, 0x3c)
    $soi = [BitConverter]::ToUInt32($hdr, $pe + 0x50)
    $iat = [ordered]@{}; $bound = 0
    foreach ($e in $IAT_PROBES) {
      $w = [LD2Probe]::Read($procId, [int64]$e[1], 4, [ref]$err)
      if ($null -eq $w) { $iat[$e[0]] = "read-failed $err"; continue }
      $v = [BitConverter]::ToUInt32($w, 0)
      $b = ($v -ne [uint32]$e[2]) -and ($v -ge 0x10000) -and -not ($v -ge 0x400000 -and $v -lt (0x400000 + $soi))
      if ($b) { $bound++ }
      $iat[$e[0]] = [ordered]@{ value = ('0x{0:X8}' -f $v); bound = $b }
    }
    $mw = [LD2Probe]::Read($procId, [int64]$LIST_MODE_SLOT_VA, 4, [ref]$err)
    $modeInMem = if ($null -ne $mw) { [BitConverter]::ToUInt32($mw, 0) } else { "read-failed $err" }
    $codeOk = 0; $codeBad = @()
    foreach ($r in @($man.runs | Where-Object { $_.kind -eq 'code' })) {
      $b = [LD2Probe]::Read($procId, 0x400000 + [int64]$r.offset, [int]$r.length, [ref]$err)
      if ($null -ne $b -and (Get-BytesSha $b 0 $b.Length) -eq (Get-BytesSha $expect ([int]$r.offset) ([int]$r.length))) { $codeOk++ } else { $codeBad += ('0x{0:x}' -f [int64]$r.offset) }
    }
    return [ordered]@{
      ok = $true
      method = 'ReadProcessMemory@0x400000'
      size_of_image = ('0x{0:X}' -f $soi)
      size_of_image_matches = ($soi -eq $OUT_SIZE_OF_IMAGE)
      iat = $iat
      iat_bound = $bound
      code_runs_in_memory_ok = $codeOk
      code_runs_in_memory_bad = $codeBad
      list_mode_in_memory = $modeInMem
    }
  } catch { return [ordered]@{ ok = $false; note = "$_" } }
}
function Invoke-OneLaunch([string]$step, [string]$exeName, [string]$exeSha, $man, [string[]]$guide) {
  $active = Join-Path $Game 'Ld95.exe'
  if ((Get-Sha $active) -ne $exeSha) { Stop-Run "game\Ld95.exe 不是 $exeName（若 P 用了 -Mode0，之後每一步都要加 -Mode0）" }
  $expect = [IO.File]::ReadAllBytes($active)
  Write-Host "啟動 $exeName 一次。" -ForegroundColor Cyan
  foreach ($g in $guide) { Write-Host "  $g" -ForegroundColor Cyan }
  Write-Host '出現錯誤框、崩潰或卡住超過約 60 秒：先截圖（Win＋Shift＋S），關閉它，不要重試。' -ForegroundColor Cyan
  $t0 = Get-Date
  $p = Start-Process -FilePath $active -WorkingDirectory $Game -PassThru
  $null = $p.Handle
  $probe = $null
  for ($i = 0; $i -lt 20 -and -not $p.HasExited; $i++) {
    Start-Sleep -Seconds 1
    if ($i -ge 7 -and -not $p.HasExited) { $p.Refresh(); if ($p.MainWindowHandle -ne [IntPtr]::Zero) { break } }
  }
  if (-not $p.HasExited) { $probe = Get-ModuleProbe $p.Id $man $expect }
  if ($probe -and $probe.ok) {
    $c = if ($probe.size_of_image_matches -and $probe.code_runs_in_memory_bad.Count -eq 0 -and $probe.iat_bound -eq $IAT_PROBES.Count) { 'Green' } else { 'Yellow' }
    Write-Host "載入檢查：SizeOfImage $($probe.size_of_image)（預期 0x726000），新匯入已綁定 $($probe.iat_bound)/6，記憶體內 45 個位置相符 $($probe.code_runs_in_memory_ok)/45，清單模式字＝$($probe.list_mode_in_memory)" -ForegroundColor $c
  } elseif ($probe) { Write-Host "載入檢查未完成（不影響判定）：$($probe.note)" -ForegroundColor Yellow }
  Write-Host '等待遊戲結束…（遊戲關掉前不要關這個視窗）' -ForegroundColor Cyan
  $p.WaitForExit()
  $t1 = Get-Date
  $code = $p.ExitCode; if ($null -eq $code) { $code = -1 }
  $a = Get-Assessment $code $t0
  $rec = [ordered]@{
    step = $step; exe = $exeName; exe_sha256 = $exeSha; list_mode = $LIST_MODE; catalog_policy = $CATALOG_POLICY
    start_utc = $t0.ToUniversalTime().ToString('o'); end_utc = $t1.ToUniversalTime().ToString('o')
    seconds = [math]::Round(($t1 - $t0).TotalSeconds, 1)
    exit_code = $code; exit_code_hex = ('0x{0:X8}' -f $code)
    exit_policy = $a.exit_policy
    events_ld95_all = $a.events_ld95_all; events_relevant = $a.events_relevant
    crash_dumps_new = $a.crash_dumps_new; wer_reports_new = $a.wer_reports_new
    module_probe = $probe
    production_can_apply = $false; release_approved = $false
  }
  if ($code -ne 0 -or $a.events_ld95_all -gt 0) {
    $ev = Join-Path $Evidence "launch-$step-events.txt"; Assert-Writable $ev
    (@($a.events_text) -join "`n----`n") | Out-File -LiteralPath $ev -Encoding utf8
  }
  Write-Json (Join-Path $Evidence "launch-$step.json") $rec
  return $rec
}

# ---------- 共通前置 ----------
$picked = @($CheckOnly, $LaunchInert, $Enable, $LaunchEnabled, $Finalize, $Pack | Where-Object { $_ }).Count
if ($picked -gt 1) { Stop-Run '一次只能選一個步驟開關' }
Write-Host "來源（只讀）：$SourceDir"
Write-Host "副本根目錄（只寫這裡）：$DisposableRoot"
Write-Host "版本：m063d v4 啟用驗收，catalog $CATALOG_POLICY，清單模式 $LIST_MODE"
if ($DisposableRoot.StartsWith($SourceDir, [StringComparison]::OrdinalIgnoreCase) -or
    $SourceDir.StartsWith($DisposableRoot, [StringComparison]::OrdinalIgnoreCase)) { Stop-Run '來源與副本路徑重疊' }
if ($DisposableRoot -match '(?i)\\steamapps\\|\\Program Files|\\Windows\\') { Stop-Run '副本不可放在 Steam / Program Files / Windows 底下' }
if ($DisposableRoot.Length -le 3) { Stop-Run '副本不可是磁碟根目錄' }
if (-not $Pack) { Assert-NotRunning }

# ---------- Z：打包證據 ----------
if ($Pack) {
  if (-not (Test-Path -LiteralPath $StateFile)) { Stop-Run '尚未執行準備步驟 P' }
  $st = Read-Json $StateFile
  if (-not (Get-Prop $st 'finalized')) { Stop-Run '請先跑 -Finalize（G）再打包' }
  $obs = Join-Path $Evidence 'observations.md'
  $tpl = Join-Path $PSScriptRoot 'observations.template.md'
  if ((Test-Path -LiteralPath $tpl) -and (Test-Path -LiteralPath $obs) -and (Get-Sha $obs) -eq (Get-Sha $tpl)) {
    Write-Host 'observations.md 還沒填（和範本一模一樣）。請先用記事本填寫、存檔，再跑一次 -Pack。' -ForegroundColor Yellow; exit 1
  }
  $files = @(Get-ChildItem -LiteralPath $Evidence -Recurse -File -Force)
  $bad = @($files | Where-Object { ($EVIDENCE_EXT_OK -notcontains $_.Extension.ToLowerInvariant()) -or $_.Length -gt $EVIDENCE_MAX_FILE })
  if ($bad.Count -gt 0) {
    $bad | ForEach-Object { Write-Host "  不允許放進證據：$($_.FullName)（$($_.Length) bytes）" -ForegroundColor Yellow }
    Write-Host '請把上面這些檔案移出 evidence 資料夾（只留 .json／.md／.txt／.png／.jpg），再跑一次 -Pack。' -ForegroundColor Yellow; exit 1
  }
  $shots = @($files | Where-Object { $_.Extension -match '(?i)^\.(png|jpe?g)$' })
  if (Test-Path -LiteralPath $ZipPath) { Write-Host "桌面已有 $ZipPath；請先改名或移走舊檔，再跑一次 -Pack。" -ForegroundColor Yellow; exit 1 }
  $list = [ordered]@{
    schema = 'm063d-evidence-list/1'; taken_utc = (Get-Date).ToUniversalTime().ToString('o')
    files = @($files | ForEach-Object { [ordered]@{ path = $_.FullName.Substring($Evidence.Length + 1); size = $_.Length; sha256 = Get-Sha $_.FullName } })
  }
  $lp = Join-Path $Evidence 'evidence-list.json'
  if (Test-Path -LiteralPath $lp) { Assert-Writable $lp; Remove-Item -LiteralPath $lp }
  Write-Json $lp $list
  Compress-Archive -Path (Join-Path $Evidence '*') -DestinationPath $ZipPath
  Write-Host "已壓縮：$ZipPath（$($files.Count) 個檔，其中截圖 $($shots.Count) 張）" -ForegroundColor Green
  Write-Host "sha256 = $(Get-Sha $ZipPath)" -ForegroundColor Green
  Write-Host '把這個 zip 傳回來即可（裡面只有紀錄與截圖，沒有 EXE、存檔本體或 dump）。'
  exit 0
}

# ---------- G：收尾（唯讀比對） ----------
if ($Finalize) {
  if (-not (Test-Path -LiteralPath $StateFile)) { Stop-Run '尚未執行準備步驟 P' }
  $st = Read-Json $StateFile
  if (Get-Prop $st 'finalized') { Stop-Run '已完成 G，不重跑（下一步：-Pack）' }
  $before = Read-Json (Join-Path $Evidence 'hashes-before.json')
  $src = Assert-SourceExe
  Write-Host '計算來源清單 hash（略過 Usr\），與準備時比對…'
  $changed = Compare-Manifest $before.source_manifest @(Get-Manifest $SourceDir)
  $after = [ordered]@{
    schema = 'm063d-v4-enable-hashes-after/1'
    taken_utc = (Get-Date).ToUniversalTime().ToString('o')
    source_exe = $src
    source_exe_same_as_before = ($src.sha256 -eq $before.source_exe.sha256 -and (ConvertTo-TimeText $src.last_write_utc) -eq (ConvertTo-TimeText $before.source_exe.last_write_utc))
    source_manifest_changes = $changed
    store_original_sha256 = Get-Sha (Join-Path $Store 'Ld95.original.exe')
    store_inert_sha256 = Get-Sha (Join-Path $Store $InertName)
    store_enabled_sha256 = Get-Sha (Join-Path $Store $EnabledName)
    game_active_exe_sha256 = Get-Sha (Join-Path $Game 'Ld95.exe')
    steps_done = @($st.steps_done)
    stopped = (Get-Prop $st 'stopped')
    production_can_apply = $false
    release_approved = $false
  }
  Write-Json (Join-Path $Evidence 'hashes-after.json') $after
  $st | Add-Member -NotePropertyName finalized -NotePropertyValue $true -Force
  Add-Step $st 'G'
  Save-State $st
  if ($changed.Count -gt 0 -or -not $after.source_exe_same_as_before) { Write-Host '警告：原目錄有變動！見 hashes-after.json。' -ForegroundColor Red }
  else { Write-Host '原目錄未變動。G 完成。' -ForegroundColor Green }
  Write-Host '下一步：截圖放進 evidence\screens\、填 observations.md，然後跑 -Pack。'
  exit 0
}

# ---------- L1／E／L2 共通 ----------
if ($LaunchInert -or $Enable -or $LaunchEnabled) {
  if (-not (Test-Path -LiteralPath $StateFile)) { Stop-Run '尚未執行準備步驟 P' }
  $st = Read-Json $StateFile
  if (Get-Prop $st 'stopped') { Stop-Run "先前已停止（$($st.stopped)），不再繼續" }
  if (Get-Prop $st 'finalized') { Stop-Run '已完成 G' }
  $null = Assert-SourceExe
  $man = Assert-Delta
  $done = @($st.steps_done)

  if ($LaunchInert) {
    if ($done -contains 'L1') { Stop-Run '步驟 L1 已執行過（只啟動一次）' }
    $rec = Invoke-OneLaunch 'L1' $InertName $INERT_SHA $man @(
      '這是「惰性版」：畫面應和之前的 m045 一樣（清單多半還是日文），這是正常的。'
      '1) 標題畫面截圖 L1-title.png → 讀取存檔（第 2 格；沒有就第 1 格）'
      '2) 進任一商店，打開「購買」清單，截圖 L1-shop-buy.png'
      '3) 不要買賣、不要存檔；從遊戲選單「結束」離開')
    Add-Step $st 'L1'
    $st | Add-Member -NotePropertyName l1_policy -NotePropertyValue $rec.exit_policy -Force
    if ($rec.exit_policy -eq 'hard-stop') { Set-Stopped $st ("step L1 exit " + $rec.exit_code_hex) }
    Save-State $st
    switch ($rec.exit_policy) {
      'ok' { Write-Host 'L1 通過（結束碼 0、無錯誤事件）。下一步：-Enable' -ForegroundColor Green }
      'soft-warn-exit1' { Write-Host 'L1 通過（結束碼 1＝此遊戲從選單結束時的常見值；無錯誤事件／dump）。下一步：-Enable' -ForegroundColor Yellow }
      default { Write-Host "L1 未通過：結束碼 $($rec.exit_code_hex)、事件 $($rec.events_relevant)、dump $(@($rec.crash_dumps_new).Count)。不會換成啟用版；接著只跑 -Finalize 與 -Pack。" -ForegroundColor Red; exit 2 }
    }
    exit 0
  }

  if ($Enable) {
    if ($done -notcontains 'L1') { Stop-Run '要先跑 -LaunchInert（L1）且通過，才能換成啟用版' }
    if ($done -contains 'E') { Stop-Run '步驟 E 已執行過' }
    $l1 = Read-Json (Join-Path $Evidence 'launch-L1.json')
    if (@('ok', 'soft-warn-exit1') -notcontains [string]$l1.exit_policy) { Stop-Run "L1 判定為 $($l1.exit_policy)，不換成啟用版" }
    $gameExe = Join-Path $Game 'Ld95.exe'
    $enabledPath = Join-Path $Store $EnabledName
    if ((Get-Sha $gameExe) -ne $INERT_SHA) { Stop-Run 'game\Ld95.exe 目前不是惰性版（有人動過？）' }
    if ((Get-Sha $enabledPath) -ne $OUT_SHA) { Stop-Run 'exe-store 內的啟用版 hash 不符' }
    Assert-Writable $gameExe
    Copy-Item -LiteralPath $enabledPath -Destination $gameExe -Force
    if ((Get-Sha $gameExe) -ne $OUT_SHA) { Stop-Run '換版後 game\Ld95.exe hash 不符' }
    Write-Json (Join-Path $Evidence 'enable-E.json') ([ordered]@{
      step = 'E'; taken_utc = (Get-Date).ToUniversalTime().ToString('o'); from_sha256 = $INERT_SHA; to_sha256 = $OUT_SHA
      l1_exit_policy = [string]$l1.exit_policy; only_disposable_copy_changed = $true; production_can_apply = $false })
    Add-Step $st 'E'
    Save-State $st
    Write-Host '步驟 E 完成：副本內的 game\Ld95.exe 已換成 v4 啟用版（原安裝沒動）。下一步：-LaunchEnabled' -ForegroundColor Green
    exit 0
  }

  if ($LaunchEnabled) {
    if ($done -notcontains 'E') { Stop-Run '要先跑 -Enable（E）' }
    if ($done -contains 'L2') { Stop-Run '步驟 L2 已執行過（只啟動一次）' }
    $rec = Invoke-OneLaunch 'L2' $EnabledName $OUT_SHA $man @(
      '這是「v4 啟用版」。每個畫面截一張圖，檔名照 USER-STEPS 第 7 節；到不了的畫面就跳過。'
      ' 1) L2-title.png → 讀取存檔（第 2 格；沒有就第 1 格）'
      ' 2) L2-party-panel.png：主畫面下方的隊伍名字（6 格）'
      ' 3) L2-char-info.png：任一角色的資訊視窗（左上名字、下方頁尾名字）'
      ' 4) 商店：L2-shop-buy.png／L2-shop-sell.png／L2-shop-upgrade.png（有「波刃短劍」或「戟斧」請另截）'
      ' 5) L2-tavern.png：酒館冒險者清單（看男女名、有沒有「克莉絲」）'
      ' 6) L2-inn-commission.png／L2-commission-list.png／L2-commission-info.png（看裡面是人名還是物品）'
      ' 7) 能開的人名清單：隊伍、提案、教育、道具頁、道具整理（L2-list-*.png）'
      ' 8) L2-item-desc.png：任一道具說明視窗的名稱行'
      ' 9) 不要買賣、不要存檔；從遊戲選單「結束」離開')
    Add-Step $st 'L2'
    $st | Add-Member -NotePropertyName l2_policy -NotePropertyValue $rec.exit_policy -Force
    if ($rec.exit_policy -eq 'hard-stop') { Set-Stopped $st ("step L2 exit " + $rec.exit_code_hex) }
    Save-State $st
    switch ($rec.exit_policy) {
      'ok' { Write-Host 'L2 結束碼 0、無錯誤事件。下一步：-Finalize，然後填 observations.md、-Pack。' -ForegroundColor Green }
      'soft-warn-exit1' { Write-Host 'L2 結束碼 1（從選單結束時的常見值），無錯誤事件／dump。下一步：-Finalize，然後填 observations.md、-Pack。' -ForegroundColor Yellow }
      default { Write-Host "L2 未通過：結束碼 $($rec.exit_code_hex)、事件 $($rec.events_relevant)、dump $(@($rec.crash_dumps_new).Count)。接著只跑 -Finalize 與 -Pack。" -ForegroundColor Red; exit 2 }
    }
    exit 0
  }
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
$base = [IO.File]::ReadAllBytes($m045.path)
$enabledBytes = Build-Enabled $base $man
Write-Host "記憶體內合併 OK（v4 啟用版，清單模式 $LIST_MODE）：sha256 = $OUT_SHA（尚未寫檔）" -ForegroundColor Green
$inertBytes = Build-Inert $enabledBytes $base $man
Write-Host "記憶體內還原 OK（v4 惰性版）：sha256 = $INERT_SHA（尚未寫檔）" -ForegroundColor Green
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
$inertPath = Join-Path $Store $InertName
$enabledPath = Join-Path $Store $EnabledName
foreach ($pair in @(@($inertPath, $inertBytes, $INERT_SHA), @($enabledPath, $enabledBytes, $OUT_SHA))) {
  Assert-Writable $pair[0]
  [IO.File]::WriteAllBytes($pair[0], [byte[]]$pair[1])
  if ((Get-Sha $pair[0]) -ne $pair[2]) { Stop-Run "寫出後 $(Split-Path -Leaf $pair[0]) hash 不符" }
}
Assert-Writable $gameExe
Copy-Item -LiteralPath $inertPath -Destination $gameExe -Force
if ((Get-Sha $gameExe) -ne $INERT_SHA) { Stop-Run 'game\Ld95.exe 換成惰性版後 hash 不符' }
$srcAfter = Assert-SourceExe
if ($srcAfter.last_write_utc -ne $srcBefore.last_write_utc) { Stop-Run '來源 Ld95.exe 修改時間在複製期間改變' }

$before = [ordered]@{
  schema = 'm063d-v4-enable-hashes-before/1'
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
  inert_exe_sha256 = $INERT_SHA
  enabled_exe_sha256 = $OUT_SHA
  exe_size = $OUT_SIZE
  catalog_policy = $CATALOG_POLICY
  catalog_blob_sha256 = $BLOB_SHA
  list_mode = $LIST_MODE
  name_object_sha256 = $NAME_OBJ_SHA
  list_object_sha256 = $LIST_OBJ_SHA
  textout_object_sha256 = $TEXTOUT_OBJ_SHA
  hook_stub_sha256 = $man.hook_stub_sha256
  seed_usr_from = $SeedUsrFrom
  seeded_saves = $seeded
  game_active = 'inert'
  production_can_apply = $false
  release_approved = $false
}
Write-Json (Join-Path $Evidence 'hashes-before.json') $before
Save-State ([ordered]@{ steps_done = @('P'); stopped = $null; finalized = $false; list_mode = $LIST_MODE })
$tpl = Join-Path $PSScriptRoot 'observations.template.md'
if (Test-Path -LiteralPath $tpl) { Copy-Item -LiteralPath $tpl -Destination (Join-Path $Evidence 'observations.md') }
Write-Host "步驟 P 完成：副本已建立，game\Ld95.exe ＝ v4 惰性版（清單模式 $LIST_MODE）。下一步：-LaunchInert" -ForegroundColor Green
