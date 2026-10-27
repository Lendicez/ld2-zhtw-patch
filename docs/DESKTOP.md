# Read-only Windows discovery and Traditional Chinese entry (m031)

Public product identity was verified on 2026-10-27 from the
[official Steam store](https://store.steampowered.com/app/335420/?l=english):
AppID **335420**, page title **ルナティックドーン 前途への道標**, purchase name
**Lunatic Dawn : Passage of the Book**. The URL and two headings identify the
product; this is not proof of a local installation. `steam-product.json` records
that distinction, and `versions.json` now permits discovery of this public AppID.
The known original/output hashes and release approval remain unchanged. No local
appmanifest or previously denied registry location was queried in this milestone.

## Entry and available actions

The new binary opens the Traditional Chinese Tk view when invoked with `--gui`
or no arguments. `--help`, `--version` and explicit generator arguments remain
console-only. No GUI was opened during development or validation. Existing
Python Tk/_tkinter/Tcl files were available and bundled without installing a new
package. Presence in the bundle is not proof of visual correctness.

The view provides explicit Steam discovery, manual folder selection, candidate
selection, inspection, source SHA256/version/size, and confirmation before writing
two new output artifacts. No detection occurs at import, controller construction
or window creation. Multiple candidates require explicit inspection; changing
selection discards the previous readiness state. Manual folders are labeled as
manual evidence, not asserted to be Steam installations. Unknown source hashes,
versions or process state disable generation. The installed-game action is always
disabled, even for synthetic versions marked release-approved.

The controller rechecks the selected source and process evidence before invoking
the existing offline writer. The writer retains its known-hash/version, new-output,
source-directory, reparse/hardlink and source-change checks. These are offline
artifact safeguards, not a production install transaction. A writer error can
leave new partial artifacts for diagnosis; it never installs them.

## Lazy Windows ports

`windows_readonly.py` contains real read functions, but tests inject every native
registry/process/filesystem source. None of the following native detection calls
was invoked against this host:

- Registry: only HKCU `Software\\Valve\\Steam` / `SteamPath`, and HKLM
  `Software\\Valve\\Steam` / `InstallPath` in the 32-bit and 64-bit views.
  Access is KEY_QUERY_VALUE. Missing values may continue; a denial immediately
  ends enumeration before trying another hive. Only REG_SZ is accepted; no
  environment expansion, recursive registry search or whole-drive scan.
- Files: the existing bounded libraryfolders/appmanifest parser visits only roots
  returned by those values and explicit libraries. Every candidate still needs
  a matching manifest AppID and known EXE hash/size/version. The stat-based read
  adapter rejects observed reparse points, symlinks, hardlinks and unknown IDs;
  it has no write methods. It is not a handle-pinning or adversarial race guarantee.
- Processes: Tool Help snapshot with explicit bounded Unicode structures; normal
  completion requires ERROR_NO_MORE_FILES. An empty snapshot is unknown. Only
  matching Ld95.exe entries request QUERY_LIMITED_INFORMATION and an image path;
  denial, disappearance, partial enumeration or malformed evidence is unknown,
  never proof that the game stopped. No termination, injection or alternate query
  interface exists. See Microsoft's [Process32NextW](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-process32nextw)
  and [QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew) contracts.

An access denial latches the controller into a stopped state: no retry, manual
fallback, generation or alternative source query in that session. The repository
does not grant permission to retry the historically denied host registry read.

## Evidence and packaging

Twenty-three new test methods cover missing/denied/invalid registry sources,
multiple candidates and manual selection, empty/incomplete/denied process evidence,
explicit-path stat reads and reparse/hardlink refusal, stale preview invalidation,
confirmation and permanent install disablement. Full checks: **158 tests,
155 passed, 3 skipped** (two licensed-input integrations and Windows real symlink
creation). No licensed game input was used in m031.

The same pinned m030 packaging venv is reused. New build paths use
`--build-tag m031`, preserving all m030 artifacts and counting both milestones in
the same 1,000,000,000-byte budget:

```powershell
& "$pack\venv\Scripts\python.exe" -I -B tools/package_generator.py --pack-root $pack --build-tag m031 --mode onedir
# Only after the onedir CLI-only checks succeed:
& "$pack\venv\Scripts\python.exe" -I -B tools/package_generator.py --pack-root $pack --build-tag m031 --mode onefile
```

The reviewed PyInstaller `_tkinter` hook collects Tcl/Tk data through a Tcl-only
interpreter; the optional window-creation probe is not used by this hook. This
milestone checks manifests and bundled files statically, and runs only help/version
plus synthetic invalid-input/preserved-output cases. No --gui/no-argument invocation,
live discovery, original game read, game launch, installation or UAC occurs.
Artifact sizes, hashes and disk accounting are recorded in
`packaging/m031-verification.json`; binaries stay local.

Unverified: actual registry views, native process structures/calls on this host,
native read adapter behavior on real installation paths, Tk appearance/focus/DPI,
file-dialog interaction and game runtime. Public AppID proof and mocked ports do
not close these gaps. See `WINDOWS-BACKEND-PLAN.md` for the next bounded step.

## m036 bounded disposable-copy interface

The local candidate wraps the read-only controller with trial_controller.py and
trial_ui.py. Source selection and preparation remain read-only until explicit
confirmation. Multi-candidate selection, cancel/back, version/process rechecks,
double-submit suppression, failure/recovery and already-restored state have
headless coverage. UI worker tasks return to the Tk main thread; controls and
closing are disabled while an operation runs.

The production install button is still disabled. The separate trial action only
creates a new workspace under the build-bound parent. Steam detection is disabled
in this candidate UI because the historical host registry query was not approved
for retry; injected detection logic remains tested. No live discovery ran.

Recovery selection accepts only an existing tool-created workspace under that
parent and validates the external DPAPI anchor before presenting confirmation.
No hash entry, JSON editing, credential prompt or trust-from-journal fallback.
Keep the whole workspace and Windows profile. GUI visuals, focus, DPI and actual
user interaction are still untested; see CANDIDATE-ACCEPTANCE.md.
