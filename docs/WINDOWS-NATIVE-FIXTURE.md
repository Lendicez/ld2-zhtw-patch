# m032 native Windows fixture boundary

This is a fixture-only backend, not a production `TransactionFS`. The generator,
catalog, release approval, `Plan.can_apply=false` and disabled GUI install button
are unchanged. No game, Steam installation, registry, UAC helper or GUI was used.

## Reproduce deliberately

Use a non-administrator Windows Python process and an existing project-owned local
NTFS parent. This creates a new random subtree and retains it, including synthetic
files, an outside sentinel, per-test save sentinels and `result.json` with hashes:

```powershell
python -I -B tools/run_windows_fixture.py --parent "<owned-project-test-parent>"
```

The ordinary `python -B tools/check.py` does not opt into these native probes.
It skips the 13 native methods unless the explicit runner supplies its fresh
fixture parent. It never silently falls back to memory mocks. Do not manually set
that test environment variable to an installation. Test files have invented bytes
and `.bin` names, never game executable names. No generated binary is needed.

`NativeFixture` has no attach-existing operation. It pins ancestors top-down with
native handles, opens reparse points rather than following them, checks final paths,
rejects hardlink files and restricts operations to declared leaf names. This bounds
the test work, but is not a claim of complete hostile-directory protection suitable
for production. Low-level ctypes helpers are internal experimental primitives.

## Observed on Windows build 26200, x64 Python 3.14, NTFS

- Native `FileIdInfo` provides a 128-bit file ID and volume serial. Identity remains
  stable across close/reopen and a handle rename to a previously absent filename.
- `CreateFileW(CREATE_NEW)` rejects a conflicting backup without overwriting it.
- A handle opened with share mode zero prevents a writer open both in the same
  process and a separate existing Python process: WinError 32. No write occurs.
- `WriteFile`, `FlushFileBuffers`, seek/readback and post-read identity checks pass.
  Handles close on an injected ordinary exception; a fresh open then succeeds.
- Staged content with a mismatched hash is retained, not promoted. Same-volume
  promotion to a new name is verified; an occupied destination is not overwritten.
- Same-file-ID external content changes and tampered backup content are detected.
  Restore/uninstall remains gated, so neither case overwrites the current target.
- A real hardlink is rejected. Injected reparse metadata is rejected. Creating a
  real symlink returned WinError 1314 (privilege absent): skipped, no retry,
  Developer Mode, ACL or privilege changes.
- All synthetic save sentinels and the sentinel outside individual test roots are
  unchanged. Artifacts and manifests from both runs remain available locally.

## Actual replacement gate

With the target handle still open at share mode zero,
`SetFileInformationByHandle(FileRenameInfo, ReplaceIfExists=TRUE)` returned
**WinError 5**. The target and stage bytes stayed unchanged. There was one attempt;
the handle was not released to retry replacement. This is an expected negative
fixture result, not an unexpected security-product block or a successful commit.

The result proves that this exact protective-handle/rename combination cannot
perform the replacement on the tested host. It does not prove that every Windows
replacement design is impossible, or identify an access-control policy root cause.
Allowing delete sharing would weaken protection of the name; closing the handle
would reintroduce a check-to-replace race. Neither is silently substituted here.

Accordingly `apply`, `recover` and `uninstall` raise `ReplacementGate` before any
OS mutation. No real-backend rollback or install/uninstall is claimed. The existing
m029 transaction algorithm remains tested separately with synthetic fault injection.

## Defect found and corrected during the first run

The first run stopped after seven tests (six passed, one failed). The original
rename buffer omitted an explicit UTF-16 NUL beyond `FileNameLength`. The native
call returned success but created a filename with an unexpected trailing character;
the occupied intended destination remained intact. This was a wrapper defect, not
a permission denial. The initial fixture and its exact path/hash manifest were
retained without cleanup or retry against those files.

The corrected buffer reserves a UTF-16 terminator while keeping `FileNameLength`
exclusive of that terminator, and verifies the resulting handle's final path. A
fresh fixture run passed 16 of 17 methods, with the real symlink case skipped.
The successful new-name and occupied-name cases cover this regression. The SDK
26100 declaration was checked: native alignment, DWORD-sized union, HANDLE,
DWORD byte length, then WCHAR data (offset 20 on x64). No global packing is used.

## Still required before user-writable installation

1. Design and review an existing-target replacement protocol that binds the target
   identity without dropping protection. Document the permitted concurrent-writer
   threat model and the exact Windows semantics; do not call name-based replacement
   an atomic compare-and-swap. Another independent protocol investigation is needed.
2. Only then connect the native backend to the m029 validated journal and bounded
   rollback slots. Demonstrate real recovery across process termination and restart,
   reinstall/upgrade/uninstall, hostile backup/journal changes and external edits.
3. Actual short writes, ENOSPC and sharing failures during commit, directory/journal
   durability and power-loss behavior remain untested. An intentionally incomplete
   staged file is a negative validator test, not a simulated or real power cut.
4. Production source/version/recipe/process revalidation and UI consent must remain
   connected to the final backend. Program Files, UAC, multi-file support, signing,
   security-product acceptance, game/save/load and GUI acceptance remain separate.

No new packaging build was needed: native fixture modules are not imported by the
desktop/generator entry. Existing onefile artifacts stay local and unreleased.

## Primary API references

- [CreateFileW sharing modes](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
- [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle)
- [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)
- [ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)

`ReplaceFileW` was researched but not used as a fallback after the refused handle
rename. Documentation and this fixture do not establish power-loss atomicity.

Full default suite: **175 tests, 159 pass, 16 explicit skips** (13 native
fixture cases opt out; two licensed-input integrations and one existing symlink
case skip). The separate explicit native run is 17 tests, 16 pass, 1 skip; its
four policy tests overlap the default suite. No real-game integration was run.
