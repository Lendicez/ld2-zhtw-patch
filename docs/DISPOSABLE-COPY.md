# m035: real EXE disposable-copy acceptance

The reviewed 1.0.3.16 EXE was read without write access, rebuilt with the existing
PE resource builder, installed into a newly created disposable case-01, and
restored in another Python process. No game EXE was executed. Original source
identity, bytes, attributes, creation/write times and owner/group/DACL digest
were unchanged at the final check. No save directories or other game assets were
copied. The restored copy retained its pre-install file identity and metadata.

| State | Bytes | SHA-256 |
| --- | ---: | --- |
| Source and restored copy | 7,090,176 | 6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2 |
| Installed m020 resource output | 7,102,464 | a15bf7313636a7c19a065b388345f93b46bbce8eb6bf3c9b910a7dc192c3da81 |

This establishes the offline file transformation and restore for this version.
It does not establish game runtime or complete translation. Production
can_apply=false and the disabled GUI install button are unchanged.

## Scope and protocol

disposable.py is a separate acceptance adapter, not a production TransactionFS.
The runner pins reviewed source/output hashes and sizes; the existing builder
also validates catalog, PE version and allowed resource/header differences.
The .text, .rdata and .data bytes are unchanged. The output has 239 translated
text locations and 15 font locations, not a full-game coverage percentage.

Native read/write operations use 1 MiB chunks and a 16 MiB total limit. The PE
builder works on bounded in-memory bytes. Prepare exclusively creates case-01;
existing directories are refused. The target is always Ld95.exe. Journals never
supply absolute paths, commands or arbitrary filenames.

Preparation flushes the source copy, backup, stage, journal and receipt before
any rename. Installation pins ancestors, opens files exclusively, checks IDs,
hashes and metadata, and calls the existing read-only process adapter.
Incomplete process evidence or a running target refuses installation.
The original is renamed to captured.bin, then stage to the vacant target, both
without replacement. Original and backup remain after commit. Restore moves
the known patch to revoked.bin and returns the same original inode. Repeated
restore is read-only.

These two renames are not atomic. A third party creating a name during either
gap is retained; the operation fails rather than overwriting it. Process
snapshots cannot prevent future process starts. This is offline-copy acceptance,
not permission to install while other software is active.

## Recovery without a live transaction controller

The exclusive-created, flushed receipt binds version, sizes, hashes,
root/original/backup/stage identities and supported metadata. Prepare returns
its SHA-256. The caller must retain that digest independently outside the case,
then explicitly provide it to every new install/restore process. A missing or
mismatching anchor is refused; recovery never calculates and trusts its own anchor.

Every identity must also appear in the anchored receipt if the journal changes
between comparison and reread. Identical-content foreign files are not adopted.
No signing key, credential, DPAPI setup, ACL change or policy is introduced.

Three native tests kill the entire disposable transaction controller at capture,
promotion and restore-gap. The newly owned child is checked by retained process
handle, PID, creation time, executable, exact command and nonce before termination.
Fresh controllers restore and repeat recovery from disk plus the external digest;
no private registration from the dead transaction controller is needed.

This covers process lifetime loss when the external digest survives. It does not
defend against a malicious same-user actor changing code and the external anchor.
Reboot and power-loss durability, including directory-entry persistence, are
unproven. Original, backup and diagnostic files are retained, not cleaned up.

## Metadata policy

Only ordinary single-link Archive files on local NTFS are supported. Reparse
points, hardlinks, extra DATA streams (including zone markers), unusual
attributes and differing security descriptors are refused; nothing is stripped.
Source is opened read-only. New files inherit the case ACL; owner/group/DACL are
read and compared, never changed. SACL or privileged security access is not used.

Backup and stage receive the original disposable copy's creation/write times.
Attributes, times and owner/group/DACL digest are checked after reopening.
Restore returns the original inode. Access time is not asserted unchanged:
NTFS may defer its updates. Initial fresh-copy timestamps are not claimed to
clone source timestamps. SACL equivalence and unusual metadata are unsupported.

Official API references:
- [SetFileTime](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfiletime)
- [GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)
- [FILE_STREAM_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_stream_info)

## Reproduction

Use only the authorized project-owned disposable parent, never a Steam directory.
The parent must exist; case-01 must not. Preserve prepare JSON outside the case.

    python -I -B tools/run_disposable_tests.py --parent <synthetic-parent>
    python -I -B tools/run_disposable.py prepare --parent <disposable-parent> --source <original-Ld95.exe>
    python -I -B tools/run_disposable.py install --parent <same-parent> --receipt-sha <saved-digest>
    python -I -B tools/run_disposable.py restore --parent <same-parent> --receipt-sha <saved-digest>
    python -I -B tools/run_disposable.py restore --parent <same-parent> --receipt-sha <saved-digest>
    python -B tools/check.py

Each real-copy step ran in a separate non-admin Python process. Final repeated
restore returned already_original. Original/modified EXEs, receipts, machine
identities and raw local evidence are not uploaded.

## Results and remaining acceptance

- Default: 236 tests, 172 pass, 64 explicit skips, zero failures.
  Skips are 61 opt-in native and three existing platform/licensed-input cases.
- New disposable suite: 18 pass (12 native, six pure), zero skips.
- Capture regression: 24 pass (20 native, four pure), zero skips.
- Worker regression: 19 pass (16 native, three pure), zero skips.
- Real-copy acceptance: build/install/restore hashes match; source unchanged;
  restored copy ID/metadata match; repeated restore makes no content/ID/metadata change.

Pure cases overlap the default run; suite totals are not additive unique coverage.
Extra receipt identity binding was added during review after the first real
roundtrip, then verified by the final native suite, full checks, and another real
already_original check. No second real installation was attempted.

Next is confirmation/recovery UI integration and packaging with the same backup
and trust requirements. Before real-directory installation, review missing-name
availability, preview freshness/process evidence and metadata support.
A later short GUI session must validate Chinese display, cancellation/navigation,
save, exit and restart/load. Elevated installation, full-game Unicode, coverage,
gameplay stability and visual improvements remain unverified. Background source
work needs no new dependency or protection change.

