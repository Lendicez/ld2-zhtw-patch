# Windows installation backend gates and next fixture milestone

The delivered Tk entry and read-only adapters do not implement installation.
`Plan.can_apply=false`, release approval=false, and the install button is disabled.
No native helper, UAC entry, service, credential or security-setting change exists.

## First supported scope: user-writable local paths

Start with one allowlisted target, `Ld95.exe`, in a user-owned local NTFS test
directory. Never use Steam/game paths or saves as transaction fixtures. Do not
classify writability using `os.access` alone or make preflight write probes in a
user's installation. Actual authorized writes must fail closed on ACL/lock errors;
no ACL changes, elevated retry or fallback destination. Network/removable volumes,
reparse paths and multi-file installation remain unsupported until independently
specified and tested.

A production backend must implement and demonstrate all of these obligations:

1. Bind the user's selected directory and exact allowlisted target to stable
   volume/file IDs. Walk and inspect ancestors without following reparse points;
   reject hardlink aliases. Hold appropriate native handles and revalidate final
   paths/identities. Path strings plus lstat snapshots are insufficient.
2. Establish cross-process exclusion and a documented identity-preserving replace
   contract. Investigate CreateFileW sharing modes and ReplaceFileW/handle rename
   behavior on fixture files. **Do not close a protective handle and silently
   accept a check-to-replace race** if sharing modes prevent replacement. This is
   an unresolved implementation gate, not a promised Windows compare-and-swap.
3. Create the original backup exclusively, flush it, read/hash it back and retain
   it. Stage verified output on the same volume. Journal intent/ownership before
   mutations and flush required evidence. Validate sizes, hashes, paths, IDs and
   free-space errors; do not overwrite mismatched backups or unknown orphan files.
4. Integrate the m029 bounded rollback slots and validated journal schemas with
   the real backend. Preserve external changes and diagnostics; support repeated
   install/uninstall only after proving ownership and original backup validity.
   Never touch USR/save or a third-party modification.
5. Separate ordinary write failures, process interruption and power loss. Tests of
   FlushFileBuffers and same-volume replacement do not alone prove directory or
   power-loss durability. Explicitly document remaining uncertainty before release.

## Protected paths and UAC: blocked, separate design

Program Files and other protected installations are not covered by the initial
user-writable implementation. The PyInstaller onefile executable must remain
asInvoker; its temporary extraction cannot be made the trusted elevated installer.
It must not restart itself elevated or change security settings to gain access.

If protected-path support is later approved, design a separate narrowly scoped
native helper with an independently reviewed, integrity-protected distribution
location and authenticated caller/request channel. Helper trust, signing, secure
placement and invocation are unresolved; no helper installation is currently
authorized. Never run a user-writable or extracted helper as administrator merely
because its filename/hash was checked earlier.

The helper would accept only a canonical selected target and reviewed recipe/version
ID, never arbitrary commands, DLLs, scripts or caller-supplied path lists. It must
independently revalidate target IDs, source/output hashes, backup/journal state,
process status and permitted operations immediately before writing. UAC cancellation
must leave the original unchanged. No credentials, persistent service or broad
elevation is part of the plan. If this cannot be justified, protected installations
remain blocked rather than elevating the Python bundle.

## Next bounded milestone: actual Windows APIs on owned synthetic fixtures

Use the existing Python/ctypes environment in the background; no new EXE, dependency,
elevation, GUI, registry read or game access. Create a fresh private work directory
containing invented ASCII source/stage/backup bytes and a save sentinel. Restrict
every helper argument to that fixture root and make accidental live paths fail
before any OS call. Keep production apply disabled.

First implement only native read/identity/handle-lifetime probes. Verify volume/file
IDs, final paths, sharing conflicts and closure on both success and exceptions.
Then, only if the handle/replace contract is demonstrable, integrate single-file
exclusive staging and replacement. Test locked source/target, changed target,
backup conflict, partial staging, injected failure before/after replacement,
restart from the durable fixture journal, orphan preservation and uninstall of
known versus externally modified files. Confirm the synthetic save sentinel and
all paths outside the owned root remain unchanged.

No privilege-dependent reparse/symlink creation is assumed. Use injected rejection
tests for those cases and explicitly skip unavailable native cases; do not enable
Developer Mode or change policy. On access or application-control refusal, stop
that action without another API, identity, filename or privilege attempt.

Deliver a reproducible fixture command, native API evidence and exact remaining
gates. A successful fixture milestone is not authorization to run against the
user's Steam installation. GUI inspection and game/save/load acceptance remain
separate, concentrated sessions, not recurring desktop interruptions.

## m032 outcome

The bounded native fixture milestone has been executed; see
[WINDOWS-NATIVE-FIXTURE.md](WINDOWS-NATIVE-FIXTURE.md). Identity, locking and staging
primitives passed, but protected existing-target replacement was refused with
WinError 5. The protective handle was not dropped for a retry. Integration with
the m029 transaction is still gated on an independently justified replacement
protocol. Do not repeat the same locked replacement probe expecting installation.

## m033 revised candidate

A supported handle sequence has now passed actual fixture tests: capture the
original by its own DELETE-capable share-zero handle, then promote the stage with
replace=False. It retains original identity and refuses competing names. See
[WINDOWS-CAPTURE-EXPERIMENT.md](WINDOWS-CAPTURE-EXPERIMENT.md). This is a multi-step
transaction with a missing-name interval; it cannot honestly implement an atomic
compare-and-swap port. Production recovery trust, metadata policy and acceptance
of that interval require review before integration. No security relaxation is
required by the tested protocol; production apply remains disabled.

## m034 actual worker-death recovery

Fresh-worker disk-journal restoration after verified termination now passes on
owned NTFS fixtures. Basic original metadata is checked and the reserved original
is retained. See `WINDOWS-WORKER-RECOVERY.md`. The missing-name interval remains;
controller-loss trust, new-file metadata policy, bounded real-EXE I/O and production
integration remain gates before disposable-original-copy acceptance. No UAC, ACL
or security setting adjustment is part of the tested path.
