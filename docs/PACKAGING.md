# Offline Windows generator (m030)

This is an **unelevated offline generator**, not an installer. It reads the one
allowlisted original, writes a new EXE and metadata outside the input directory,
and never executes the generated game. It does not discover Steam, write registry
values, install into a game directory, invoke transaction apply or request UAC.
Production `can_apply` and release approval remain false. The output retains the
game's existing manifest; this tool does not alter it.

The console tool accepts only these operations:

```powershell
.\ld2-patch-generator.exe --help
.\ld2-patch-generator.exe --version
.\ld2-patch-generator.exe --input 'D:\OwnedGame\Ld95.exe' --out 'D:\PatchBuild\Ld95-generated.exe' --metadata-out 'D:\PatchBuild\Ld95-generated.json'
```

The output directory must already exist. Both output paths must be new, distinct
siblings outside the source directory and its descendants. Unknown source
hash/version, existing output, relative/traversal paths, symlinks/reparse paths,
hardlinked source and detected source changes are refused. Failure during writes
can leave partial new artifacts; they are retained, never installed or silently
overwritten. These path checks are not a native handle-based defense against an
adversarial concurrent writer. Use a controlled private build directory.

Successful generation returns exit 0 and JSON `status: built_only`. Validation
or I/O failure returns exit 1 and `status: refused_or_failed`; argument errors
return exit 2. A Windows application-control denial is not a normal validation
failure: stop without changing names, loaders, environments or security settings.

## Pinned environment and build

The validated environment uses existing PSF-signed CPython 3.14.0 x64 on Windows
11 build 26200. A separate venv shares that interpreter; no global Python change
or additional Python/Visual Studio installation was made. The exact official
PyPI wheels, URLs, versions, sizes and SHA256 values are in
`packaging/dependency-sources.json` and `requirements-win-py314.lock`.
Seven wheels total 3,050,807 bytes; installed dependencies passed `pip check`.
PyInstaller and hooks-contrib are pinned together, as recommended by its
[official installation documentation](https://pyinstaller.org/en/v6.22.3/installation.html).

The dedicated packaging root has `venv`, `downloads`, `temp`, `cache`, `build`,
`dist`, `testbuild` and `evidence` directories. Bootstrap with the already
installed Python's `venv`; download only the listed official wheel URLs, verify
each SHA256, then install without network resolution:

```powershell
& "$pack\venv\Scripts\python.exe" -m pip install --no-index --no-deps --no-compile --require-hashes --find-links "$pack\downloads" -r packaging/requirements-win-py314.lock
& "$pack\venv\Scripts\python.exe" -I -B tools/package_generator.py --pack-root $pack --mode onedir
```

Run normally, not as administrator. Verify the onedir tool's help/version and
negative cases before building onefile, following the
[official onefile guidance](https://pyinstaller.org/en/v6.22.3/operating-mode.html#bundling-to-one-file):

```powershell
& "$pack\venv\Scripts\python.exe" -I -B tools/package_generator.py --pack-root $pack --mode onefile
```

`$pack` is an explicit dedicated absolute path, not a game path. Existing build
or dist paths are refused rather than erased. The driver verifies Windows/Python
architecture and installed versions, reserves 350 MB before a build, and samples
total disk usage while building. At 950 MB it stops only its child builder and
retains evidence. This is a conservative budget guard, not an OS-enforced quota;
the actual milestone stayed far below the 1,000,000,000-byte authorization.
All build cache/temp paths and validation runtime TEMP/TMP were inside this root.

The spec bundles only source modules, their runtime dependencies and three
reviewed JSON files: recipe, translation catalog and version allowlist. It does
not bundle a game EXE, save, native adapter or game asset. `asInvoker` and
`uiAccess=false` are explicit and were verified from both produced PE manifests.
The generator also refuses elevated generation before reading its inputs.
Onefile extracts runtime files to Windows TEMP before Python code starts: do not
use Run as administrator. It is not suitable for a future privileged installer.

## Actual validation and limits

- Full suite: 135 tests, 132 pass and 3 explicit skips (both licensed-input test
  methods and real Windows symlink creation). Eight generator regressions cover
  synthetic output, elevation refusal, unknown input, existing output,
  traversal/source-directory protection, hardlinks, reparse evidence and help.
- Onedir and onefile each ran help/version (exit 0), unknown-input rejection
  (exit 1) and existing-output preservation (exit 1) as background non-admin
  processes. These were successful runs, not blocked or skipped tests.
- The onefile generator read the authorized local original without changing it.
  Its output was byte-identical to the previously verified m020 build. This
  separate packaged integration does not change the three suite skips above.
- Exact artifact hashes, sizes and local disk accounting are recorded in
  `packaging/m030-verification.json`. Binaries, wheel files and game outputs
  remain local and are excluded from Git. No Actions or release was created.

The artifact is unsigned. Success on this host does not guarantee acceptance on
other Windows installations; no application-control policy was changed and no
historically blocked binary was retried. The packaged game output was not run.
Translation still covers the existing 239 resource locations and 15 font settings,
not all game text. GUI/save/load, installer transactions, Windows production
rollback/UAC, signature and redistribution/license review remain separate gates.
The generator EXE itself is not claimed bit-reproducible across builds; the m020
game output is constrained to its exact expected hash and bytes.

## m031 incremental package

The new source supports `--gui` or no-argument Tk launch, but those paths were
not executed in m031. `--help`/`--version` stay console-only. Four reviewed JSON
files now include public Steam product identity. The existing interpreter's Tk
runtime is bundled without new dependencies. Use `--build-tag m031` to preserve
m030 artifacts. See `DESKTOP.md` and `m031-verification.json` for actual CLI-only
checks and the shared cumulative 1 GB budget. This is still not an installer.
