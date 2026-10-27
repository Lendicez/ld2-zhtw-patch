# m034: real worker termination and disk-journal recovery

This milestone remains restricted to fresh, owned NTFS fixtures containing fixed
invented bytes. Production apply=false and the disabled GUI install button are
unchanged. No game, registry, existing user process, GUI, privilege, ACL, security
setting or dependency installation is involved.

## Process boundary and termination authority

`tools/capture_worker.py` runs in the existing Python interpreter with `-I -B`
and no console window. The controller retains the process handle created by
`subprocess.Popen`; it never opens or terminates a process obtained by name or a
PID search. Before each termination, it checks:

- the retained handle's PID, creation time and full executable path, both at
  creation and immediately before termination;
- the command line and executable path from a read-only `Win32_Process` query
  filtered to that one newly created PID;
- exact expected argv, a per-fixture nonce and the ready/paused checkpoint from
  the private child pipe, plus unchanged worker source SHA-256;
- the executable is the expected Python, and the process has not already exited.

Only then does `TerminateProcess` use the retained handle. Waiting on that same
process verifies exit code `0xe034`. No `taskkill`, process-name matching, PID-only
kill, elevated retry or alternate termination API exists. If a query/termination
is unavailable, further worker attempts stop and are explicitly skipped. A paused
worker otherwise aborts itself after 20 seconds without continuing mutation.
No such refusal occurred in the recorded run.

## Registration and journal trust

The original m033 prepared journal is still strict and bounded: no arbitrary
paths, commands or additional keys; exact root/original/backup/stage IDs, known
source/output hashes, types and alias checks precede mutations.

The new worker does not inherit the prior transaction object's memory. It reads
the prepared journal from disk. Independently, the controller created a receipt
outside the worker fixture root and retained its hash. For every fresh worker it
rereads that receipt, verifies the retained digest, then supplies the registration
over a private pipe. Registration binds schema, the fixed `invented-capture-v1`
recipe, source/output hashes, root leaf/ID, original ID, basic metadata and nonce.
The disk copy inside the fixture must exactly match this independent evidence.
The worker pins ancestors, verifies the existing root ID, refuses reparse paths,
and only permits its fixed invented `.bin`/journal names. It cannot attach by an
arbitrary journal-provided path.

This proves recovery across **worker** death. The controller remains alive and
retains the receipt digest. It does not prove trust recovery after controller loss,
reboot, a malicious same-account attacker controlling both code and evidence, or
arbitrary production installation. Those remain explicit integration gates.

## Persistent state and observed recovery

All prepared/intent/commit records use exclusive creation, native write, flush and
readback. They are retained, not overwritten. Recovery validates objects and known
content rather than trusting a phase marker alone. It always restores the original;
it never resumes installation merely because an untrusted marker says to do so.

| Worker termination checkpoint | State left on disk | Fresh recovery |
| --- | --- | --- |
| Original held, before staging | Original at target; no prepared journal | Confirm original identity/content/metadata, no write |
| Backup created, before prepared journal | Original at target; incomplete staging evidence | Confirm original, retain uncommitted artifacts |
| Prepared or capture intent flushed | Original at target, verified backup/stage | Already-original result; retain evidence |
| Original captured or promotion intent flushed | Target name absent, original reserved | Restore original with no-overwrite rename |
| Patch promoted, before commit marker | Patch at target, original reserved | Validate and restore original |
| Commit marker flushed, handles still held | Patch committed, original still retained | Explicit restore remains possible |
| Restore gap after patch moved aside | Target absent; original and patch reserved | Resume restoration without overwriting another name |
| Original restored, before/after restore marker | Original at target | Idempotent already-original recovery |

Repeated recovery starts another interpreter and leaves the same file contents
unchanged. Tampered prepared journals, changed patched targets and an unknown
restore destination are rejected; foreign files and reserved originals survive.
Before the prepared journal exists, recovery can only confirm the independently
known original at its original name and retain incomplete artifacts. It does not
invent ownership or clean up unknown staging files.

There are still two renames and a missing-name interval, including during rollback.
This is not atomic filename replacement. A competitor occupying the gap prevents
replacement; the original stays reserved for diagnosis. Journal flush plus real
process termination is not evidence of directory durability after power loss.

## Metadata policy

The original inode remains reserved even after a verified fixture commit. Native
queries confirmed original file ID, basic attributes, creation time and last-write
time before capture, while reserved and after restore. The worker rejects a change
to these independently registered original properties. Last-access time is recorded
but excluded from equality: the tests themselves read the file and Windows may
defer updating that value. No timestamps or ACLs are rewritten as a workaround.

The new staged file still has its own metadata. No claim is made that it inherits
the original ACL, alternate streams, compression, timestamps or signature status.
Production metadata handling must be decided before a real-copy installer trial.

## Actual results and reproduction

On Windows build 26200 / NTFS / existing non-admin x64 Python:

- Worker suite: **19 passed**, zero skips/failures: 16 Windows fixture cases and
  3 pure identity/registration validation cases.
- **43 owned workers** were launched; all recorded an exit. **14** were terminated
  after successful identity checks: 11 distinct transaction/restore checkpoints,
  plus 3 post-termination refusal scenarios. Remaining exits were normal success
  or expected refusal. No user process was queried or terminated.
- The m033 capture regression suite: **24 passed**, zero skips/failures (20 native
  cases and 4 schema cases), after adding the new no-op-default checkpoint hooks.
- Outside and save sentinels remain unchanged; original metadata equality passed.

```powershell
python -I -B tools/run_windows_crash.py --parent "<owned-project-test-parent>"
```

This creates fresh fixture roots and retains per-worker PID/time/command/exit
evidence plus path/hash manifests locally. Those machine-specific logs and fixture
files are not uploaded. The default suite does not opt into native worker killing.
The m032 refused replacement and symlink-privilege probes were not retried.

## Official references

- [TerminateProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess): required handle access, asynchronous termination and waiting for completion.
- [GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes): creation time on the retained process handle.
- [Win32_Process](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-process): read-only command-line and executable identity fields; the query is restricted to the owned PID.
- [BY_HANDLE_FILE_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/ns-fileapi-by_handle_file_information): attributes, timestamps and file-ID limitations.

Remaining user-facing gates and the proposed disposable-copy scope are listed in
[NEXT-ACCEPTANCE.md](NEXT-ACCEPTANCE.md). This branch is a draft, not a release.

Full default suite: **218 tests, 166 pass, 52 explicit skips** (49 opt-in
native cases, two licensed integrations and the existing symlink case). The
separate worker/capture suites are 19/19 and 24/24; their 7 pure methods overlap
the default suite. Skips are not counted as successful integrations.
