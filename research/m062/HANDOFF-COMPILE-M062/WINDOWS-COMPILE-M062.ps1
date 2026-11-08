# m062 HANDOFF-COMPILE-M062: MSVC compile-only of the two v3-catalog helpers + mock link/run.
# Does NOT open the game, does NOT read or write any game EXE, does NOT set production_can_apply.
# Stages:
#   A) cl /c name_pair_v3.cpp     -> runs\m062\compile-only\name_pair_v3.obj (+ .asm)
#      cl /c list_insert_v3.cpp   -> runs\m062\compile-only\list_insert_v3.obj (+ .asm)
#      (same flags as the pinned m058 name_pair.EHs.obj and m061b list_insert_u.obj)
#   B) link each mock with its Stage A object -> runs\m062\mock\*.once.exe ; run each once
#      list mock last line : cases=29 assertions=1164 failed=0 game_or_user32_called=false
#      name mock last line : JSON with "cases":38 ... "failed":0 ... "game_or_gdi_called":false
#   C) pack the return zip (objects, asm, json, stdout; NO exe) on the Desktop.
param(
  # Re-use existing Stage A objects instead of recompiling (keeps the reported sha256).
  [switch]$SkipStageA,
  # Where the return zip goes (default: Desktop).
  [string]$ReturnZip = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = $env:LD2_ZHTW_LAB
if (-not $Root) {
  foreach ($cand in @(
      (Join-Path $PSScriptRoot '..\..\..'),
      (Join-Path $PSScriptRoot '..\..'),
      (Join-Path $env:SystemDrive 'GameDev\LD2\zhTW_lab')
    )) {
    $t = Join-Path $cand 'toolchains\msvc2022'
    if (Test-Path $t) { $Root = (Resolve-Path $cand).Path; break }
  }
}
if (-not $Root) {
  throw 'Set $env:LD2_ZHTW_LAB to your zhTW_lab directory (the one that contains toolchains\msvc2022).'
}
Write-Host "Lab root: $Root"

$Vc = Join-Path $Root 'toolchains\msvc2022\VC\Tools\MSVC\14.44.35207'
$Cl = Join-Path $Vc 'bin\Hostx64\x86\cl.exe'
$Link = Join-Path $Vc 'bin\Hostx64\x86\link.exe'
$VcLib = Join-Path $Vc 'lib\x86'
$SdkRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10'
$PreferredSdk = '10.0.26100.0'

function Find-SdkVersion([string]$SdkRoot, [string]$Preferred) {
  $libRoot = Join-Path $SdkRoot 'Lib'
  if (-not (Test-Path $libRoot)) { throw "Windows Kits Lib missing: $libRoot" }
  $preferredUm = Join-Path $libRoot "$Preferred\um\x86\kernel32.lib"
  if (Test-Path $preferredUm) { return $Preferred }
  $candidates = Get-ChildItem -Path $libRoot -Directory | Sort-Object Name -Descending
  foreach ($dir in $candidates) {
    $k32 = Join-Path $dir.FullName 'um\x86\kernel32.lib'
    if (Test-Path $k32) { return $dir.Name }
  }
  throw "kernel32.lib not found under $libRoot"
}
function Find-RcExe([string]$SdkRoot, [string]$SdkVer) {
  foreach ($arch in @('x64', 'x86')) {
    $candidate = Join-Path $SdkRoot "bin\$SdkVer\$arch\rc.exe"
    if (Test-Path $candidate) { return $candidate }
  }
  throw "rc.exe not found under $SdkRoot\bin\$SdkVer"
}
function Sha([string]$Path) { (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLower() }

if (-not (Test-Path $Cl)) { throw "cl.exe missing: $Cl" }
if (-not (Test-Path $Link)) { throw "link.exe missing: $Link" }

$SrcDir = Join-Path $PSScriptRoot 'native'
$OutCompile = Join-Path $Root 'runs\m062\compile-only'
$OutMock = Join-Path $Root 'runs\m062\mock'
New-Item -ItemType Directory -Force -Path $OutCompile | Out-Null
New-Item -ItemType Directory -Force -Path $OutMock | Out-Null

foreach ($f in @('catalog_core_v3.h','name_pair_v3.h','name_pair_v3.cpp','list_core_v3.h','list_bindings_v3.h',
                 'list_insert_v3.cpp','v3_mock_blob.h','name_pair_mock_v3.cpp','list_mock_test_v3.cpp')) {
  $p = Join-Path $SrcDir $f
  if (-not (Test-Path $p)) { throw "missing source $p" }
}

$Helpers = @(
  @{ name = 'name_pair_v3'; entry = '_LD2_NamePair@16' },
  @{ name = 'list_insert_v3'; entry = '@LD2_ListInsertV3@24' }
)
$Flags = @('/c','/W4','/WX','/O2','/Oi','/Oy-','/GS','/Gy','/Zl','/EHs')
$Shas = @{}
if ($SkipStageA) {
  Write-Host '=== Stage A skipped (-SkipStageA): re-using existing objects ==='
  foreach ($h in $Helpers) {
    $obj = Join-Path $OutCompile "$($h.name).obj"
    if (-not (Test-Path $obj)) { throw "-SkipStageA but missing $obj" }
    $Shas[$h.name] = Sha $obj
  }
} else {
  $objects = @()
  foreach ($h in $Helpers) {
    $cpp = Join-Path $SrcDir "$($h.name).cpp"
    $obj = Join-Path $OutCompile "$($h.name).obj"
    $asm = Join-Path $OutCompile "$($h.name).asm"
    Write-Host "=== Stage A: compile-only $($h.name).cpp (/EHs /Zl /GS, no link) ==="
    & $Cl /nologo /c /W4 /WX /O2 /Oi /Oy- /GS /Gy /Zl /EHs "/I$SrcDir" $cpp "/Fo$obj" /FAsc "/Fa$asm" | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Stage A cl failed for $($h.name) ($LASTEXITCODE)" }
    $Shas[$h.name] = Sha $obj
    Write-Host "Stage A OK $($h.name).obj sha256=$($Shas[$h.name])"
    $objects += @{
      object = "$($h.name).obj"; entry = $h.entry; object_sha256 = $Shas[$h.name]
      object_bytes = (Get-Item $obj).Length; asm_bytes = (Get-Item $asm).Length
    }
  }
  @{
    stage = 'A-compile-only'
    milestone = 'm062'
    catalog_format = 'LD2C v3 (catalog_core_v3.h)'
    objects = $objects
    flags = $Flags
    native_executed = $false
    linked = $false
    game_touched = $false
    production_can_apply = $false
  } | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $OutCompile 'compile-command.json') -Encoding utf8
}

$SdkVer = Find-SdkVersion $SdkRoot $PreferredSdk
$UmLib = Join-Path $SdkRoot "Lib\$SdkVer\um\x86"
$UcrtLib = Join-Path $SdkRoot "Lib\$SdkVer\ucrt\x86"
$RcExe = Find-RcExe $SdkRoot $SdkVer
$SdkBin = Split-Path -Parent $RcExe
$env:PATH = @((Join-Path $Vc 'bin\Hostx64\x86'), $SdkBin, $env:PATH) -join ';'
$env:LIB = ($VcLib, $UcrtLib, $UmLib) -join ';'
$VcInclude = Join-Path $Vc 'include'
$SdkInc = Join-Path $SdkRoot "Include\$SdkVer"
$IncDirs = @($VcInclude, (Join-Path $SdkInc 'ucrt'), (Join-Path $SdkInc 'um'), (Join-Path $SdkInc 'shared'))
foreach ($d in $IncDirs) { if (-not (Test-Path $d)) { throw "include dir missing: $d (install Windows SDK headers / MSVC include)" } }
foreach ($lib in @((Join-Path $VcLib 'libcmt.lib'), (Join-Path $UcrtLib 'libucrt.lib'))) {
  if (-not (Test-Path $lib)) { throw "CRT lib missing: $lib" }
}
$env:INCLUDE = $IncDirs -join ';'
$env:TMP = $OutMock
$env:TEMP = $OutMock
Write-Host "Using Windows SDK $SdkVer"

function Run-Mock([string]$Name, [string]$MockCpp, [string]$HelperObj) {
  $mobj = Join-Path $OutMock "$Name.obj"
  $masm = Join-Path $OutMock "$Name.asm"
  $exe = Join-Path $OutMock "$Name.once.exe"
  Write-Host "=== Stage B: $Name (mock + Stage A object, no game) ==="
  & $Cl /nologo /c /W4 /WX /utf-8 /MT /EHs /O2 /Oy- /GS "/I$SrcDir" (Join-Path $SrcDir $MockCpp) "/Fo$mobj" /FAsc "/Fa$masm" | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "Stage B cl failed for $Name ($LASTEXITCODE)" }
  & $Link /nologo /MACHINE:X86 /SUBSYSTEM:CONSOLE /INCREMENTAL:NO /DYNAMICBASE /NXCOMPAT `
    /MANIFEST:EMBED "/MANIFESTUAC:level='asInvoker' uiAccess='false'" `
    $mobj $HelperObj kernel32.lib "/OUT:$exe" "/LIBPATH:$VcLib" "/LIBPATH:$UcrtLib" "/LIBPATH:$UmLib" | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "Stage B link failed for $Name ($LASTEXITCODE)" }
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $exe
  $psi.WorkingDirectory = $OutMock
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true
  $p = [System.Diagnostics.Process]::Start($psi)
  $errTask = $p.StandardError.ReadToEndAsync()
  $out = $p.StandardOutput.ReadToEnd()
  $err = $errTask.Result
  $p.WaitForExit()
  Set-Content -Path (Join-Path $OutMock "stdout-$Name.txt") -Value $out -Encoding utf8
  Set-Content -Path (Join-Path $OutMock "stderr-$Name.txt") -Value $err -Encoding utf8
  $last = ($out -split "`r?`n" | Where-Object { $_ -ne '' } | Select-Object -Last 1)
  Write-Host "  exit=$($p.ExitCode) last line: $last"
  return @{ name = $Name; exit_code = $p.ExitCode; last_line = $last; mock_exe_sha256 = (Sha $exe) }
}

$list = Run-Mock 'list-mock-v3' 'list_mock_test_v3.cpp' (Join-Path $OutCompile 'list_insert_v3.obj')
$name = Run-Mock 'name-mock-v3' 'name_pair_mock_v3.cpp' (Join-Path $OutCompile 'name_pair_v3.obj')
$listOk = ($list.exit_code -eq 0) -and ($list.last_line -eq 'cases=29 assertions=1164 failed=0 game_or_user32_called=false')
$nameOk = ($name.exit_code -eq 0) -and ($name.last_line -match '^\{"cases":38,') -and ($name.last_line -match '"failed":0,') -and ($name.last_line -match '"game_or_gdi_called":false\}$')
if ($nameOk -and ($name.last_line -notmatch '"assertions":25815,')) {
  Write-Host '  note: name mock assertion count differs from the Linux rehearsal (25815); report it, not an error by itself' -ForegroundColor Yellow
}
@{
  stage = 'B-mock-link-run'
  sdk_version = $SdkVer
  object_sha256 = $Shas
  list_mock = $list
  name_mock = $name
  list_ok = $listOk
  name_ok = $nameOk
  game_touched = $false
  production_can_apply = $false
} | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $OutMock 'once-result.json') -Encoding utf8

# Stage C: return zip with only the allowed files (no exe, no game file).
if (-not $ReturnZip) { $ReturnZip = Join-Path ([Environment]::GetFolderPath('Desktop')) 'm062-v3-compile-return.zip' }
$pack = @(
  (Join-Path $OutCompile 'name_pair_v3.obj'), (Join-Path $OutCompile 'name_pair_v3.asm'),
  (Join-Path $OutCompile 'list_insert_v3.obj'), (Join-Path $OutCompile 'list_insert_v3.asm'),
  (Join-Path $OutCompile 'compile-command.json'), (Join-Path $OutMock 'once-result.json'),
  (Join-Path $OutMock 'stdout-list-mock-v3.txt'), (Join-Path $OutMock 'stdout-name-mock-v3.txt'),
  (Join-Path $OutMock 'stderr-list-mock-v3.txt'), (Join-Path $OutMock 'stderr-name-mock-v3.txt')
) | Where-Object { Test-Path $_ }
Compress-Archive -Path $pack -DestinationPath $ReturnZip -Force
Write-Host "Return zip: $ReturnZip  sha256=$(Sha $ReturnZip)"

if (-not $listOk) { throw 'list mock did not print the expected summary line (see stdout-list-mock-v3.txt). Send the return zip anyway.' }
if (-not $nameOk) { throw 'name mock did not report cases=38 failed=0 (see stdout-name-mock-v3.txt). Send the return zip anyway.' }
Write-Host 'HANDOFF-COMPILE-M062 finished OK' -ForegroundColor Green
