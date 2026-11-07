# m061b HANDOFF-COMPILE-M061B: MSVC compile-only of list_insert_u.cpp (list helper v2,
# Unicode-flip policy word) + mock link/run. Does NOT open the game, does NOT write any
# game EXE, does NOT set production_can_apply.
# Stages:
#   A) cl /c list_insert_u.cpp  -> runs\m061b\compile-only\list_insert_u.obj (+ .asm)
#   B) cl mock + link with Stage A object -> runs\m061b\mock\list-mock-u.once.exe ; run once
#      expected stdout last line: cases=22 assertions=1116 failed=0 game_or_user32_called=false
# After Stage A, copy list_insert_u.obj back to Linux for: audit_list_obj.py --profile u
param(
  # Re-use an existing Stage A object instead of recompiling (keeps the reported sha256).
  [switch]$SkipStageA,
  # No v2 object is pinned yet; set this only when re-using a reported Stage A object.
  [string]$ExpectListSha = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = $env:LD2_ZHTW_LAB
if (-not $Root) {
  foreach ($cand in @(
      (Join-Path $PSScriptRoot '..\..\..'),
      (Join-Path $PSScriptRoot '..\..')
    )) {
    $t = Join-Path $cand 'toolchains\msvc2022'
    if (Test-Path $t) { $Root = (Resolve-Path $cand).Path; break }
  }
}
if (-not $Root) {
  throw 'Set $env:LD2_ZHTW_LAB to your zhTW_lab directory (the one that contains toolchains\msvc2022).'
}

$Vc = Join-Path $Root 'toolchains\msvc2022\VC\Tools\MSVC\14.44.35207'
$Cl = Join-Path $Vc 'bin\Hostx64\x86\cl.exe'
$Link = Join-Path $Vc 'bin\Hostx64\x86\link.exe'
$VcLib = Join-Path $Vc 'lib\x86'
$SdkRoot = 'C:\Program Files (x86)\Windows Kits\10'
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

function Assert-Sha([string]$Path, [string]$Expect) {
  $h = (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLower()
  if ($h -ne $Expect.ToLower()) { throw "hash mismatch $Path got $h expect $Expect" }
}

if (-not (Test-Path $Cl)) { throw "cl.exe missing: $Cl" }
if (-not (Test-Path $Link)) { throw "link.exe missing: $Link" }

$SrcDir = Join-Path $PSScriptRoot 'native'
$OutCompile = Join-Path $Root 'runs\m061b\compile-only'
$OutMock = Join-Path $Root 'runs\m061b\mock'
New-Item -ItemType Directory -Force -Path $OutCompile | Out-Null
New-Item -ItemType Directory -Force -Path $OutMock | Out-Null

$ListCpp = Join-Path $SrcDir 'list_insert_u.cpp'
$MockCpp = Join-Path $SrcDir 'list_mock_test_u.cpp'
foreach ($f in @('list_insert_u.cpp','list_mock_test_u.cpp','list_core_u.h','list_bindings_u.h')) {
  $p = Join-Path $SrcDir $f
  if (-not (Test-Path $p)) { throw "missing source $p" }
}

$ListObj = Join-Path $OutCompile 'list_insert_u.obj'
$ListAsm = Join-Path $OutCompile 'list_insert_u.asm'
$MockObj = Join-Path $OutMock 'list_mock_test_u.obj'
$MockAsm = Join-Path $OutMock 'list_mock_test_u.asm'
$MockExe = Join-Path $OutMock 'list-mock-u.once.exe'

if ($SkipStageA) {
  Write-Host '=== Stage A skipped (-SkipStageA): re-using existing object ==='
  if (-not (Test-Path $ListObj)) { throw "-SkipStageA but missing $ListObj" }
  if ($ExpectListSha) { Assert-Sha $ListObj $ExpectListSha }
  $ListSha = (Get-FileHash -Algorithm SHA256 -Path $ListObj).Hash.ToLower()
  Write-Host "Stage A object sha256=$ListSha"
} else {
  Write-Host '=== Stage A: compile-only list_insert_u.cpp (/EHs /Zl /GS, no link) ==='
  # Same flag set as m058 name_pair.EHs.obj. /Zl keeps DEFAULTLIB out of the object.
  & $Cl /nologo /c /W4 /WX /O2 /Oi /Oy- /GS /Gy /Zl /EHs `
    /I$SrcDir $ListCpp `
    /Fo$ListObj /FAsc /Fa$ListAsm
  if ($LASTEXITCODE -ne 0) { throw "Stage A cl failed $LASTEXITCODE" }
  $ListSha = (Get-FileHash -Algorithm SHA256 -Path $ListObj).Hash.ToLower()
  Write-Host "Stage A OK list_insert_u.obj sha256=$ListSha"
  @{
    stage = 'A-compile-only'
    object = 'list_insert_u.obj'
    profile = 'u'
    object_sha256 = $ListSha
    object_bytes = (Get-Item $ListObj).Length
    asm_bytes = (Get-Item $ListAsm).Length
    flags = @('/c','/W4','/WX','/O2','/Oi','/Oy-','/GS','/Gy','/Zl','/EHs')
    native_executed = $false
    linked = $false
    game_touched = $false
    production_can_apply = $false
  } | ConvertTo-Json | Set-Content -Path (Join-Path $OutCompile 'compile-command.json') -Encoding utf8

}

$SdkVer = Find-SdkVersion $SdkRoot $PreferredSdk
$UmLib = Join-Path $SdkRoot "Lib\$SdkVer\um\x86"
$UcrtLib = Join-Path $SdkRoot "Lib\$SdkVer\ucrt\x86"
$RcExe = Find-RcExe $SdkRoot $SdkVer
$SdkBin = Split-Path -Parent $RcExe
$env:PATH = @((Join-Path $Vc 'bin\Hostx64\x86'), $SdkBin, $env:PATH) -join ';'
$env:LIB = ($VcLib, $UcrtLib, $UmLib) -join ';'
# Stage B needs the C++ standard library + UCRT headers (Stage A used only local headers).
# The portable toolchain has no vcvars environment, so set INCLUDE explicitly.
$VcInclude = Join-Path $Vc 'include'
$SdkInc = Join-Path $SdkRoot "Include\$SdkVer"
$IncDirs = @($VcInclude, (Join-Path $SdkInc 'ucrt'), (Join-Path $SdkInc 'um'), (Join-Path $SdkInc 'shared'))
foreach ($d in $IncDirs) { if (-not (Test-Path $d)) { throw "include dir missing: $d (install Windows SDK headers / MSVC include)" } }
if (-not (Test-Path (Join-Path $VcInclude 'cstdio'))) { throw "cstdio not found in $VcInclude" }
if (-not (Test-Path (Join-Path $SdkInc 'ucrt\stdio.h'))) { throw "ucrt stdio.h not found in $SdkInc\ucrt" }
foreach ($lib in @((Join-Path $VcLib 'libcmt.lib'), (Join-Path $UcrtLib 'libucrt.lib'))) {
  if (-not (Test-Path $lib)) { throw "CRT lib missing: $lib" }
}
$env:INCLUDE = $IncDirs -join ';'
Write-Host "INCLUDE=$env:INCLUDE"
$env:TMP = $OutMock
$env:TEMP = $OutMock
Write-Host "Using Windows SDK $SdkVer"

Write-Host '=== Stage B: compile mock harness + link with Stage A object (no game) ==='
& $Cl /nologo /c /W4 /WX /utf-8 /MT /EHs /O2 /Oy- /GS `
  /I$SrcDir $MockCpp `
  /Fo$MockObj /FAsc /Fa$MockAsm
if ($LASTEXITCODE -ne 0) { throw "Stage B cl (mock) failed $LASTEXITCODE" }

& $Link /nologo /MACHINE:X86 /SUBSYSTEM:CONSOLE /INCREMENTAL:NO /DYNAMICBASE /NXCOMPAT `
  /MANIFEST:EMBED "/MANIFESTUAC:level='asInvoker' uiAccess='false'" `
  $MockObj $ListObj kernel32.lib /OUT:$MockExe `
  "/LIBPATH:$VcLib" "/LIBPATH:$UcrtLib" "/LIBPATH:$UmLib"
if ($LASTEXITCODE -ne 0) { throw "Stage B link failed $LASTEXITCODE" }

$stdout = Join-Path $OutMock 'stdout.txt'
$stderr = Join-Path $OutMock 'stderr.txt'
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $MockExe
$psi.WorkingDirectory = $OutMock
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
$p = [System.Diagnostics.Process]::Start($psi)
$out = $p.StandardOutput.ReadToEnd()
$err = $p.StandardError.ReadToEnd()
$p.WaitForExit()
Set-Content -Path $stdout -Value $out -Encoding utf8
Set-Content -Path $stderr -Value $err -Encoding utf8
$exeSha = (Get-FileHash -Algorithm SHA256 -Path $MockExe).Hash.ToLower()
@{
  stage = 'B-mock-link-run'
  exit_code = $p.ExitCode
  sdk_version = $SdkVer
  list_object_sha256 = $ListSha
  mock_exe_sha256 = $exeSha
  stdout_bytes = [Text.Encoding]::UTF8.GetByteCount($out)
  stderr_bytes = [Text.Encoding]::UTF8.GetByteCount($err)
  game_touched = $false
  production_can_apply = $false
} | ConvertTo-Json | Set-Content -Path (Join-Path $OutMock 'once-result.json') -Encoding utf8
Write-Host "Stage B done exit=$($p.ExitCode) exe_sha256=$exeSha"
if ($out -notmatch 'cases=22 assertions=1116 failed=0 game_or_user32_called=false') { throw 'mock harness output did not match the expected summary line' }
Write-Host "NEXT: copy $ListObj, $ListAsm, compile-command.json and once-result.json back for Linux audit_list_obj.py --profile u"
if ($p.ExitCode -ne 0) { throw "mock harness failed exit=$($p.ExitCode)" }
Write-Host 'HANDOFF-COMPILE-M061B finished OK'
