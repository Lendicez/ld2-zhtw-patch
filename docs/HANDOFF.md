# 雲端開發自足交接

目標：自用繁中與遊戲優化，改以 GitHub 開發 Patch，最終單一 Windows 安裝 EXE。
Repository：https://github.com/Lendicez/ld2-zhtw-patch，owner Lendicez；使用者已批准公開。
透過既有 GitHub connector 的 blob/tree/commit/ref API 搬移，保留初始 README 與 parent commit。
本機 Git 可用，gh 不在 PATH；沒有新增登入、憑證或工具，也沒有啟用 Actions。
既有 Git index/白名單已透過正式核准入口複核一致。不要上傳原 laboratory 或任何遊戲資產。

從 `python -B tools/check.py` 開始，雲端缺合法原檔時保持整合 SKIPPED。
不要尋找/下載遊戲來補 fixture，不把大量候選數當翻譯覆蓋率。
本機 `--game-exe` 路線在記憶體重建並核對歷史 m020，無寫入/執行遊戲。

下一個可交付切片：以合成 filesystem/Steam VDF 完成 discovery + planner，保持 dry-run，
補足 AppID 核實管道、unknown version/running game/路徑穿越/多候選測試。
再做單檔 transaction 故障注入，才接 installer UI/原生包裝。現在不要先寫入使用者安裝位置。
catalog 的翻譯改動需建立新版本 output hash，不可跳過本機比對；目錄內沒有原文全文，
要上下文時由本機持有原檔的抽取流程審閱後回填 target-only 記錄，不上傳資產。

發行前卡點：本地 appmanifest 核實 AppID、CI 預算控制與啟用批准、
安裝交易安全實作、Win11 集中 GUI/save/load/restore 驗收。公開授權尚未選定，不宣稱擁有遊戲資產權利。
所有舊成果仍留在本機 laboratory；此 staging 不取代它們。讀 `MIGRATION-INVENTORY.md` 了解取捨。

## m026 continuation

Read-only discovery and dry-run planning are implemented with synthetic ports; see `DRY-RUN.md`. Run `python -B tools/check.py` without licensed input, and `python -B tools/dry_run_demo.py`. Keep AppID null and release approval false until their independent gates are satisfied. Next development should test transaction design with synthetic fault injection and define live Windows evidence adapters; do not connect them to the user's game implicitly. This milestone uses the existing local executor in the background, not a configured cloud executor. No Actions/workflow or game/native-harness execution is authorized by these examples.

## m027 continuation

This stacked milestone is based on PR #1 head `d1c6704f96013371c7334f8c2a0a5978b5409d08`; its PR targets `feature/steam-discovery-dry-run`, not main. `transaction.py` and temporary fixtures exercise single-file backup/stage/replace/rollback/uninstall. Run the existing check command without licensed input: 95 tests, 93 passed, 2 explicit skips on Windows. Do not treat the synthetic flag as a production capability or point the test adapter at a live installation. Next review should focus on journal durability and native Windows evidence/locking contracts before any real installer implementation. No merge, release, Actions, GUI or security change is included.

## m028 continuation

This stacked milestone depends on PR #2 head `7c443a04ed26831eed950dfeb835ac56fe6b6f8e`. Offline CLI rebuild of the explicitly authorized local original reproduced m020 exactly twice; input stayed unchanged. Two real-input tests pass locally but must be skipped in an executor without licensed input. The asset-free recipe and build verification are committed; original/full patched EXEs remain private local artifacts. Next minimal packaging experiment is an unelevated offline builder, with bundled JSON resource paths and a content audit. Project Python currently lacks PyInstaller/Nuitka; installation needs separate approval. Do not turn a one-file Python bundle into a privileged installer. Real installer evidence/adapters and GUI acceptance remain separate gates.

## m029 continuation

The recovery fix is stacked on PR #3 head `d85eaedb0fbdd3facc15f71d3e0faf3050ea0982`.
See `TRANSACTIONS.md` for the two confirmed reproductions, bounded orphan-preserving
recovery, schema 1 compatibility and complete journal validation. Ten new regression
methods pass; full checks without licensed input report 127 tests, 124 passed and
3 explicit skips. No game input or execution, installation, packaging dependency,
Actions or production write path is included. Existing original assets, catalogs,
recipes and expected m020 output hashes are unchanged. Review this fix before
continuing packaging or designing a native Windows transaction adapter.

## m030 continuation

A Windows x64 asInvoker offline generator is packaged and tested locally. See
`PACKAGING.md` for the pinned PyPI wheel provenance, commands, 1 GB budget and
limits. The onefile tool produced an exact m020 result from the read-only original;
it did not install or execute the game. Binaries and wheels remain local. Full
checks: 135 tests, 132 pass/3 skip, plus a separate successful packaged licensed
integration. Next steps must keep privileged installation separate from onefile
extraction, preserve production apply=false and address remaining runtime text,
GUI/save/load and real Windows transaction gates. No merge/release/Actions.

## m031 continuation

Official Steam product AppID 335420 is verified; local installation is not. Lazy
Windows read-only registry/files/process ports, a headless preview controller and
a Traditional Chinese Tk entry are implemented. Imports/window construction do
not trigger detection. Native host detection and GUI were not run; only injected
ports/headless tests and packaged CLI synthetic checks were used. Full suite:
158 tests, 155 pass/3 skip. Existing Tk and packaging venv were reused. See
`DESKTOP.md`, `steam-product.json` and `m031-verification.json`. The next bounded
step is actual Windows handle/replace probes on owned synthetic fixtures as
specified in `WINDOWS-BACKEND-PLAN.md`; keep production apply disabled and protected
path/UAC support blocked. No original input, game, new dependencies or Actions.

## m032 continuation

Stacked on PR #6 head `26b71aedd7be57b86d9acf7881fb231dc906ae5c`. Native fixture
primitives are in `windows_fixture.py`; the explicit runner preserves fresh local
synthetic evidence without game access. Read `WINDOWS-NATIVE-FIXTURE.md` before
using them. The protected-target rename experiment returned WinError 5 and was
not retried without its protective handle. Existing-target compare-and-replace
semantics are the next design gate, not permission to weaken locking, elevate,
change security settings or retry historically blocked programs. Production apply
and GUI installation remain disabled. Do not mistake passing native primitives
for a completed native transaction/rollback backend.

## m033 continuation

Stacked on PR #7 head `53bb8f2d1593c3f1469258764ca87a2df5af105b`. Read
`WINDOWS-CAPTURE-EXPERIMENT.md` for the documented m032 self-lock conflict and
the successful fixture-only capture/promote/restore protocol. Do not retry the
old locked replacement or reinterpret WinError 5 as SAC evidence. Native results
are stronger than mocks but still include a missing-name gap and injected process
evidence. Production apply/install remains disabled. The next gate is reviewing
that availability tradeoff and designing trusted persistent recovery/metadata
handling, not deployment into a real Steam installation.

## m034 continuation

Stacked on PR #8 head `9131c28548f520f25b6283c372617565bfc2d55b`. Actual owned-worker
termination and new-interpreter journal recovery are verified, using retained
process handles and PID/creation/image/command/nonce checks. Read
`WINDOWS-WORKER-RECOVERY.md`: 19 worker tests and 24 capture regression tests pass.
No original/game/registry/GUI access occurred. The independent registration digest
is retained by the live controller; do not claim reboot recovery or production
installation. Next integration must replace only fixed synthetic assumptions under
known version/hash constraints, settle metadata/recovery trust, and obtain an
explicit disposable-original-copy test scope as described in `NEXT-ACCEPTANCE.md`.

## m035 continuation

Base PR #9 ff4fb134da8ef438b6a9e674c05ad88b7e8c2a08.
Real 1.0.3.16 disposable-copy install/restore passed; see DISPOSABLE-COPY.md
and m035-verification.json. Original input was read-only, EXE outputs stay local.
Receipt SHA-256 must survive independently; never auto-trust disk journals.
Source work can proceed to confirmation/recovery UI integration, but production
apply and GUI installation remain disabled. No game/GUI or Steam installation
is authorized by these offline results. Read NEXT-ACCEPTANCE.md.

## m036 continuation

Base PR #10: 3747c2053b1b4aca5ffee34bedbc866845869fb4.
Read CANDIDATE-ACCEPTANCE.md and TRANSLATION-STATUS.md first. The headless
controller, Tk interface source and asInvoker single EXE now use the m035
disposable-copy API. A build-bound parent path and native identity restrict the
candidate to new random workspaces; no runtime parent override or production
apply switch exists. The local scope policy and all binaries remain unpublished.

The independent receipt digest is automatically protected with CurrentUser DPAPI
in a sibling recovery-store before any rename. Fresh processes verify the protected
anchor, envelope and native identities; they never reconstruct trust from journals.
Keep the complete workspace and the same Windows profile. This does not defend
against a malicious process already controlling that account or guarantee power-loss
recovery. Production installation remains disabled.

Final checks: 254 total, 186 passed and 68 explicit skips. The dedicated 18-test
trial suite includes 14 headless cases and 4 native store cases, all passing; the
headless cases overlap the general suite. Final onedir/onefile CLI checks passed,
and final onefile installed/restored a fresh real-EXE copy in separate processes.
No game, GUI, registry detection, elevation, new dependency or security change.
See packaging/m036-verification.json. Next: one short visual acceptance window
and a bounded translation batch, not further general installer expansion.

## m037 continuation

Base PR #11 b91bdc1150f11855cfe1d56e5ec9c93fe2c85ac2.
Read M037-COMBAT-UI.md. The new patches/m037 offline profile adds 32 text
locations and 5 dialog fonts, preserving all m020 rows and files. Schema 2 uses
explicit expected-output fields; every source/catalog/version/output check stays
mandatory. It is not accepted by the production planner and does not update the
m036 package or disposable installer. Default generation remains m020.

Full checks: 266 tests, 196 passed/70 skipped without licensed input; 200 passed/
66 skipped with it. Separate new CLI outputs and metadata match exactly. Original
input unchanged; code/data proof and native CP950 checks passed. No game/GUI.
Next content priority: confirmed static fields in quest detail 292, movement 168
and rest 173, keeping dynamic names/placeholders and unknown contexts untouched.

## m038 local continuation
Base PR #12 c96d16a706c98855876c6ad6c028839cd22771ed.
Read M038-TRAVEL-PARTY-QUEST.md and TRANSLATION-STATUS.md.
24 new locations / 22 distinct translations; 295 total locations. General tests:
274 total, 200 passed, 74 skipped; licensed run: 208 passed, 66 skipped.
Two offline builds match. Prior profiles unchanged; no game/GUI or remote write.
Next content boundary: UTF-16 deadline formatting and evidence for one control
setter. Do not globally switch API width or assume buffer/HWND/ABI safety.
The complete candidate manifest/classification is local. Obtain batch approval
for new source anchors and static evidence before any remote publication.

## m039 offline deadline research

Read M039-DEADLINE-TEXT.md. The pure formatter and synthetic control-boundary
preview have no native runtime integration and always refuse application.
The original numeric field is signed int32 at the formatting boundary; business
range/sentinels and live Unicode HWND remain unknown. A three-digit value already
exceeds the estimated existing label width. Do not globally switch A/W APIs or
reuse an unverified game buffer. Profiles/output and packaging remain unchanged.
Full tests: 290, with 215 pass/75 skip general; 224 pass/66 skip licensed.
This local snapshot depends on m038; it is not a separate installable patch.


## m040 bounded deadline layout (local, not published)

Read M040-DEADLINE-LAYOUT.md. One dialog 292 geometry candidate widens the deadline
to 115 DLU and moves the adjacent row/buttons; no text, font, code, ABI, hook or
installer profile changes. Hash-locked rebuild is reproducible. Offscreen GDI
passes 44 numeric and 40 existing-label measurements; actual game remains unseen.
Full suites: 296 total, 220 pass / 76 skip general, 230 pass / 66 skip licensed.
The single numeric setter callsite is known, but live Unicode/control-site and
native lifetime/ABI are not proven. Stop integration until a bounded observation.
One complete playable candidate requires 193818896 bytes plus saves/headroom.
Folder separation is not security isolation for the elevated original game.
The inventory has 381 untranslated UI context candidates, not a coverage rate.
All earlier profiles and production can_apply=false remain unchanged.


## m041 complete facility-category disposition (local only)

Read M041-FACILITY-UI.md and TRANSLATION-STATUS.md. Profile m041 extends m038,
not the separate m040 geometry candidate. Of 171 facility candidates, 123 changed
(77 exact strings / 71 without trailing padding), 39 identity-preserved, 9 deferred.
27 resource pages are bound to 28 class/factory/constructor chains; DarkInfo uses
142, not the unproven 462. Resource 464 also remains untouched.
418 translated locations total; 219 ordinary UI context candidates remain.
540 offscreen measurements pass; page-tab width and dynamic overwrites remain
unobserved. Tests: 304 total, 225 pass / 79 skip general, 238 pass / 66 skip licensed.
Source/output hashes are pinned, two builds match, all original 1029 files match.
No game, GUI, installation, security changes, new dependencies or remote writes.
Combined m040+m041 publication manifest is local; no original assets are included.


## m042 static UI disposition (local only)

Based on PR #15 a74c1f542bfb6631f631a53325446a86396118e7. Read M042-STATIC-UI.md,
TRANSLATION-STATUS.md and research/ui/m042-disposition.json. All remaining 210
candidates are classified: 134 translated, 33 identical, 8 setting identifiers,
35 deferred. With m041's 9 deferred, 44 of the original 381 candidates remain.
552 translated locations, 377 exact output strings; no whole-game coverage claim.
Resource 180 is a character/filter UI, not proven player creation. Internal RT_STRING
setting names are preserved. No unknown HF/DAT data or dynamic setter is patched.
m042 output SHA256: 9fea1172e92167d435a8ec26baf085ab45a2a56468690bf7bfec1f8ba29dc367.
314 tests: general 232 passed/82 skipped; licensed 248 passed/66 skipped. Two final
builds match. No GUI/game, installation, security changes, new dependencies or
remote writes. m040 geometry remains independent; production can_apply=false.
The pending publication manifest is complete and local. Do not upload game assets.


## m043 local source checkpoint

Candidate source defaults to m042 (552 locations) and preserves all prior pinned profiles. The protected recovery anchor now binds the exact profile. General regression: 241 pass / 85 skip; licensed-input regression: 258 pass / 68 skip, each 326 total and zero failures. Native DPAPI profile tests and packaging remain unexecuted after a tool approval rejection before setup. No m043 EXE exists; do not use the older m036 artifact as current. See M043-CANDIDATE-PROFILES.md and M043-ACCEPTANCE.md. No remote writes; production can_apply=false.


## m043 packaged candidate completion (supersedes source-only checkpoint)

The local m043 onefile now passed 13 background CLI invocations, including exact m042 installation, independent-process DPAPI restore and idempotent restore. The default trial profile is m042 (552 locations); m020/m037/m038/m041 remain selectable. Protected recovery identifies the stored profile even when a different profile is selected at restart. Native store suite: 20/20 pass (6 native, 14 headless). PE manifest is asInvoker/uiAccess=false; unsigned. See M043-CANDIDATE-PROFILES.md, M043-ACCEPTANCE.md and packaging/m043-verification.json. GUI and game have not run; full-game copies have not been prepared. Production can_apply=false. No remote writes.


## m045 local status-prompt candidate

Two previously untranslated standard status/help prompts (IDs 57345 and 57346) are now a separate offline profile: 554 positions, 71 unchanged font locations. See M045-STATUS-PROMPTS.md and patches/m045/build-verification.json. Keep m042 and the m043 trial default intact. No GUI/game execution, new package, remote write or repackaging in this milestone. The observed ACP950 conversion loss is supported; the actual runtime chain and automatic-input failure remain unproven.


## m047: pinned m045 candidate integration

The new local candidate defaults to m045 (554 positions), retaining all five prior profiles unchanged. Packaged CLI passed 13 invocations including exact install, protected cross-process profile-aware restore, original identity/metadata restoration, and no-write repeated restore. General: 248 pass/87 skip; licensed: 267 pass/68 skip; each 335 total. Separate native store suite: 20 pass, overlaps general. Manifest remains asInvoker. No production install, GUI/game launch, new dependency or full game copy. See M047-CANDIDATE.md, M047-ACCEPTANCE.md and packaging/m047-verification.json. m046 runtime evidence is limited to the directly seen F1 prompt and user-reported manual menu; save/load and normal exit remain unverified. The m046 directory was not accessed. Publication is pending; no remote writes in this milestone.
