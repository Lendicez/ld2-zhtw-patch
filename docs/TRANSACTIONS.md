# Single-file synthetic transactions (m027)

This milestone depends on PR #1, `feature/steam-discovery-dry-run`, at
`d1c6704f96013371c7334f8c2a0a5978b5409d08`. Review it as a stacked change, not a
replacement for main. No real installation entry point or live Windows adapter
has been added. Production `Plan.can_apply` remains false, the real AppID remains
null and the real version's `release_approved` remains false.

Run `python -B tools/check.py` without `LD2_TEST_EXE` or `--game-exe`. The new
transaction tests write only invented ASCII contents into automatically cleaned
`TemporaryDirectory` fixtures. Virtual Windows paths map inside that owned
temporary directory; they are never interpreted as live installation paths.

## Scope and review fixes

The core supports one target, exactly `Ld95.exe`. It does not implement multi-file
atomicity, upgrades or cleanup of prior diagnostic artifacts. Adding a second
target to a preview is rejected before any write. A future multi-file design
needs per-file recovery and cannot rely on the guarantees of this milestone.

The discovery/planner review fixed Boolean `schema_version=True` being accepted
as integer 1, malformed candidate objects escaping structured refusal,
inconsistent discovery claiming completeness despite a denial, and unbounded or
non-ASCII file-version fields. File versions now require four ASCII uint16 parts.

## Algorithm and injected filesystem contract

`plan_uninstall` is another read-only preview. `simulate_transaction` and
`recover_simulation` require an explicitly synthetic backend. This flag prevents
accidental use through the delivered interface; it is not a security boundary
against an untrusted Python caller or a malicious backend. The only write adapter
delivered is `tests/transaction_fixture.py`. Do not turn it into a live adapter by
changing a flag or path.

Before writing, the simulation locks the installation scope, re-creates the
preview from complete discovery, process and version evidence, and compares every
plan field. It rejects unapproved versions, changed plans, unsupported hashes,
wrong payload hash/size and any target outside the one-file set. A matching hash
does not waive identity, change-token or path checks.

The sequence is:

1. Exclusively create a new transaction journal. Collision or uncertain creation
   stops before backup/stage/target changes and never overwrites an older journal.
2. Create the original backup exclusively, or verify an existing one without
   replacing it. Re-read its exact original hash and size before proceeding.
3. Write and verify a transaction-local preimage (`before.bin`) and replacement
   (`after.bin`). The preimage also permits rollback of an interrupted uninstall.
4. Persist staged identities; re-read the target and process state; verify the
   original backup again; persist `replace_pending`.
5. Ask the backend to compare the exact target and stage metadata immediately
   before same-volume replacement. Re-read the replacement hash, size and file
   identity, then persist `committed`.

The backup path is deterministic from the allowlisted version and original hash.
Stage files use a new transaction ID. The journal stores paths, hashes, sizes and
identity evidence, not game contents. Production writes must also revalidate all
ancestor identities, reject symlinks/reparse points/hardlink aliases, and provide
durable flush, exclusive creation and compare/replace semantics. Those are
explicit backend obligations, not properties proven by a Python Protocol.

## Failure, recovery and uninstall

Errors before replacement leave the target unchanged when its original identity
can still be proved. Partial backups/stages and journals are retained for
diagnosis; a later attempt refuses an incomplete backup rather than overwriting
it. There is no broad recursive cleanup API.

If replacement happened but acknowledgement or final journaling failed, automatic
rollback is permitted only when current bytes, size, file identity and change
token match the recorded file produced by this transaction. Rollback stages the
verified preimage, journals that stage's identity, rechecks processes, and uses
the same compare/replace contract. An external change, invalid backup, unknown
process state or locked rollback target yields `recovery_required`; files are not
guessed at or forcibly replaced. The last durable journal and retained paths
remain available. Explicit recovery can resume after a simulated fault clears.

Recovery validates the transaction ID, scope, exact derived paths and allowlisted
hash/size pairs before using a journal. A committed journal is verified and left
committed. Interrupted work is reverted to its verified preimage when ownership
is known. Journals are not authenticated against an adversary; this is not a
tamper-proof recovery system. Unknown ownership always requires review.

Uninstall requires the exact known patched EXE plus a verified original backup.
It restores the original and retains that backup. If Steam or another mod changed
the EXE, uninstall refuses to overwrite it. Repeated install/uninstall are no-op
observations; repeated install additionally validates the original backup.
Synthetic USR/save sentinels remain unchanged throughout successful and failed
operations. No save path is part of the target set.

## Evidence and explicit limits

Local Windows run: **95 tests; 93 passed, 2 skipped**. Skips are the licensed-game
integration and real Windows symlink creation (no privilege change was requested).
The injected reparse-refusal test and a real hardlink-alias test both pass.
Windows native encoding checks pass. This is not Windows CI or a game test.

Failure tests include partial writes, synthetic ENOSPC and lock errors, modified
targets between planning and replacement, unknown process state, corrupt backups,
initial/final journal failures and ID collision, malformed/tampered journals,
crashes before/after replacement/commit and during rollback, and failed uninstall.
The crash signal is a test exception which skips ordinary recovery handlers;
recovery then reloads the persisted fixture journal. It is not a power-loss test.

The temporary adapter uses actual file writes, fsync and `os.replace` on one local
temporary volume, with fault hooks and an in-process lock. It does **not** prove
Windows production atomicity, directory durability, UAC/ACL/Defender behavior,
cross-process exclusivity or race resistance against an adversarial external
writer. It does not implement native handle-based reparse protection. Linux CI,
live Steam discovery, game GUI/save/load, packaging and real rollback remain
unverified. No blocked native program was compiled, loaded or run.
