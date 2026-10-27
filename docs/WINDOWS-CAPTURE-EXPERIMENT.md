# m033: diagnose the lock conflict and test a bounded capture transaction

This is a new **fixture-only** experiment stacked on PR #7. Production apply and
the GUI install button remain disabled. It uses invented constant bytes, fresh
local NTFS directories, the existing non-admin Python interpreter and documented
Win32 handle operations. It does not install, run or read a game.

## Diagnosis from the exact m032 code and Microsoft references

The successful m032 buffer correction is retained. Its x64 `FILE_RENAME_INFO`
layout uses a DWORD-sized union, HANDLE, DWORD byte count and UTF-16 filename at
offset 20, with an explicit NUL outside the length. Class 3 (`FileRenameInfo`)
was used, with ReplaceIfExists true and no extended flags. The staged handle had
GENERIC_READ | GENERIC_WRITE | DELETE (`0xc0010000`), share zero. The destination
was independently open with GENERIC_READ (`0x80000000`), also share zero.

That design asks an ordinary rename to replace a destination that is still open.
Microsoft documents that share zero excludes other read/write/delete opens, and
that a normal rename fails when an existing destination has open handles. Thus
the fixture itself violates the documented replacement precondition. WinError 5
is consistent with this conflict; it is **not evidence of SAC/Defender/WDAC**.
No unrelated policy inspection or attribution is needed. The exact error alone
would not identify a cause, and this result does not prove no filter can ever
affect another operation.

The target lacking DELETE in m032 is not a missing administrator privilege: the
old code never asked that target handle to rename itself. The new protocol opens
the original once with GENERIC_READ | DELETE (`0x80010000`), share zero, and uses
that same handle to capture its own inode under an absent name. It does not
unlock the original, add delete sharing, alter ACLs or retry the old operation.
The existing same-volume handle-rename primitive supports this different order.

References reviewed on 2026-10-27:

- [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew): desired access versus share flags; delete includes rename; sharing lasts until handle closure.
- [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle): handle access requirements and FileRenameInfo class 3.
- [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info): byte length, union, target-exists behavior.
- [FILE_RENAME_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information): DELETE requirement, same-volume boundary and existing-destination open-handle restrictions. Extended POSIX semantics were not used.
- [ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew): opens files internally, preserves selected metadata and has partial-failure cases; it is not an identity-conditioned compare-and-swap. Not called as a fallback.
- [MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw): name-based replacement/cross-volume/reboot flags do not provide the missing identity condition. Not called; no reboot scheduling or registry writes.

## Implemented sequence and its race boundary

`windows_capture.py` intentionally is not an implementation of the old atomic
`TransactionFS.replace_if_unchanged` port. Its multi-step semantics require a
different journal model; pretending otherwise would conceal the missing-name gap.

1. Require injected process evidence exactly `clear`. Open the original exclusively
   with READ | DELETE, check independently retained original volume/file ID and
   exact known invented content. A changed file is refused before staging.
2. Exclusively create an owner marker, original backup and patch stage. Write,
   flush and read back through retained handles. Persist a bounded, strict prepared
   journal with root/original/backup/stage IDs and known hashes, never paths or
   commands. Unknown existing backups and markers are not overwritten.
3. Recheck process evidence, original identity/content, backup and stage. Flush
   a capture intent. The original's **own still-open handle** renames it to
   `captured.bin`, with replace=False. The same original ID remains protected.
4. Recheck evidence and persist promotion intent. The stage's held handle renames
   it to `target.bin`, again with replace=False. A competing target name makes this
   fail instead of replacing that file. Original, backup and stage are retained.
5. Verify the held new target and backup, persist the commit marker, then close
   handles. This is a fixture commit, not authorization for production apply.

Ordinary injected failure can roll back while handles remain held. Explicit
restore after handles close validates the prepared schema, independent original
ID, root, backup and current target. It moves only the known patched inode to
`revoked.bin`, then renames the captured original back with replace=False. A
foreign/modified target, backup or journal is refused before restoration writes.
Three exclusive intent slots preserve unknown orphans; exhaustion stops safely.
Repeated install is refused; repeated restore to the original is a read-only no-op.

**There is a visibility gap:** after capture, `target.bin` may not exist. If process
evidence becomes unknown there, the experiment leaves the original captured for
explicit diagnosis/restore. A competitor may occupy the vacant name; both install
and restore preserve it and retain the original elsewhere. This is fail-closed
preservation, not uninterrupted availability or atomic replacement of the name.

## Actual evidence

A minimal non-admin probe first verified capture, promotion and return using the
same retained handles and file IDs. No m032 denied replacement was retried.

The final explicit suite passed **24 methods**: 20 actual Windows fixture cases
plus four journal-schema methods. It covers commit/restore and original file ID,
unknown/changing process evidence, changed input, failure before/after capture and
after promotion, journal-driven restore after handles close, interruption between
restore renames, competing names during both gaps, modified patched target,
tampered backup/journal, duplicate install, backup collision, orphan preservation
and bounded rollback slots. All outside and save sentinels stayed unchanged.

The interruption cases raise a controlled BaseException and close handles, then
instantiate a new controller using persisted evidence. They are **not** an OS
process kill, reboot, power failure or test of storage-controller cache behavior.
Competing-name cases create actual NTFS files at deterministic hook points; they
do not measure arbitrary scheduler races. Process evidence is injected, not a
claim that the live Windows game-process detector has been validated.

Reproduce only in a new owned fixture subtree:

```powershell
python -I -B tools/run_windows_capture.py --parent "<owned-project-test-parent>"
```

The runner retains every fixture and a hash manifest. The default check command
skips opt-in native cases, and must not be pointed at a game or an old fixture.
The m032 symlink privilege case and locked replacement probe were not rerun.

## Remaining production gates

- Decide whether a recoverable missing-name interval is acceptable. If uninterrupted
  filename availability is required, this protocol is not sufficient.
- A production restart loader needs independently trusted version/recipe and
  original identity evidence. The fixture currently retains the original token
  independently in its controller; arbitrary on-disk journals are not trusted.
- Generalize from fixed invented bytes/64 KiB to the reviewed game recipe only
  after integrating the new phases with the production planner. This branch does
  not weaken m029 validation or force this protocol into its atomic replace port.
- Persistent process-crash recovery, actual ENOSPC/short-write handling, directory
  and journal durability, hostile writable mappings/namespace attacks and metadata
  policy remain unverified. Share-zero handles do not claim to defeat every prior
  memory mapping or malicious actor with the same account's powers.
- Capturing preserves the original inode; the new stage does not automatically
  inherit all original ACLs, streams, attributes, timestamps or compression like
  ReplaceFile may. No ACL/metadata rewrite was authorized or implemented here.
- Real process detection, game/save/load acceptance, UAC/protected directories,
  multi-file upgrades, signing and security-product acceptance remain separate.

There are no new dependencies, binary artifacts, GUI operations or security changes.

Full default suite: 199 tests, 163 pass, 36 explicit skips (33 opt-in native
cases, two licensed-input integrations and the existing symlink skip). The
separate 24-method capture run has no skips; its four schema tests overlap.
