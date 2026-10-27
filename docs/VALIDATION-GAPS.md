# 已驗證與未驗證

- 歷史 m014：部分主選單、存讀檔與確認對話框在 guest 可見；不代表每個字串都看過。
- m020：239 個累計變更位置；本分支整體尚無 Win11 主機 GUI/save/load 通過證據。
- m023：baseline-a 曾啟動一次，畫面可觀察；自動選單輸入無反應，使用者回報手動遠端操作正常。
  這輪暫停 GUI 驗收，未關閉/重啟遊戲；仍有 3 次舊批次額度，不在遷移工作使用。
- 原生 Unicode：未與遊戲接入；獨立程式曾被 SAC 阻擋，不能用 CI、新環境或換 hash 偷渡重試。
- ACP950 的標準資源譯文不是全引擎 Unicode 解法。未翻譯 CP932 動態文字、DBCS 切割/長度、ANSI API 仍有問題。
- 日期問號來源為存檔標頭已有文字；不能任意修改格式候選宣稱修好。私人 saves 不帶入 repo。
- 剩餘文字：標準 UI 未審核項、動態列表、外部 HF/資料記錄、故事/任務/物品/魔法描述、MFC 錯誤提示；圖片內文字仍排除。
- m020 形成/委託/開鎖/魔法/道具具有局部靜態命令路徑證據，動態可到達性與完整流程未驗。
- 版面/GDI 離屏估算不是 GUI 裁切證明；about copyright 與動態 property-sheet 字型仍有風險。
- 優化尚未實作：Win11 穩定性、字型大小與適度畫質須分開量測，不與翻譯一併宣稱完成。
- PE parser 是版本鎖定實驗核心，非通用安全 parser；正式 installer 前需 fuzz、大小/深度/溢位/路徑完整審查。

最終集中驗收：先原版副本 save/load，再資源 Patch 安裝/退出/取消/儲存/重啟讀回，最後解除安裝與 hash 還原。
每次只在已核准範圍操作；不中斷使用者日常桌面。新增版本可另訂短批次，不能沿用舊已耗額度假稱新批准。

## m026 evidence and remaining gaps

New tests cover injected Steam roots, modern/legacy VDF, multiple candidates, incomplete discovery, missing manifests, Unicode/space paths, path attacks, bounded reads, permission failures, changing files, unknown hashes/versions/process state, backup conflicts and idempotent previews. These are synthetic unit tests only. No actual Steam AppID or installation is verified. No live Windows registry/file-identity/reparse/process adapter, TOCTOU-safe transaction, real backup/rollback, installer UX, packaging or GUI/save/load acceptance is demonstrated. Historical licensed-input integration is explicitly skipped in this milestone. Windows native encoding checks are not Windows CI or game validation. The dormant native source is neither compiled nor executed.

## m027 scope and remaining gates

Local synthetic transaction tests cover original-preserving backups, partial writes/ENOSPC, locked targets, external modifications, journal failures/collisions, simulated crash recovery and uninstall. There are 95 tests: 93 pass, licensed input and real Windows symlink creation are explicitly skipped; injected reparse rejection and actual temporary hardlink rejection pass. These checks do not prove power-loss recovery, production Windows atomic replace/directory durability, native handle/reparse checks, multi-process locking, UAC/ACL or security-product behavior. Only one target is supported; multi-file plans are rejected. Diagnostics and partial stages/backups remain on uncertainty. No production adapter, real game/save access or actual installation has occurred. See `TRANSACTIONS.md`.

## m028 actual resource-build verification

The known original was read locally under explicit authorization. Two standalone offline outputs and metadata were identical to historical m020; the original pre/post hash and complete `.text`/`.rdata`/`.data` bytes were unchanged. Only 27 approved resource payloads and enumerated PE header/data-entry fields differ. This carries 239 text locations and 15 font settings, not whole-game coverage. No game was executed or installed. Full checks: 117 tests; without licensed input 114 pass/3 skip, with authorized input 116 pass/1 skip (Windows real symlink creation). Cloud/Actions, runtime layout, dynamic text, save/load and production installer recovery remain unverified. See `BUILD.md` and the asset-free build metadata.

## m029 recovery regression evidence

The early restore-file creation crash and list/dict phase TypeError were reproduced
on PR #3, then fixed with bounded exclusive restore slots and pre-mutation schema
validation. Targeted regressions: 10 pass. Full synthetic checks: 127 tests,
124 pass/3 skip (two licensed-input tests, Windows real symlink creation). Unknown
orphans remain untouched; three exhausted slots deliberately require diagnosis.
These are fault-injection tests, not OS crash/power-loss tests. Actual production
filesystem atomicity/durability, Windows security/UAC, native handles, concurrent
writers and real-game installation/recovery remain unverified. No licensed-input
test was rerun in this milestone. Production apply remains disabled.

## m030 packaging evidence

The asInvoker onedir and onefile tools passed actual background non-admin
help/version and synthetic refusal checks. The onefile tool's licensed output
is byte-identical to verified m020 and its original input hash is unchanged.
This proves offline generation on this host, not game execution or installation.
Full suite: 135 tests, 132 pass, 3 explicit skips; packaged licensed integration
is recorded separately. Unsigned acceptance elsewhere, native handle-based
concurrency safety, GUI/save/load, privileged installation/rollback, licensing
and release signing remain unverified. Production apply is still disabled.

## m031 preview and Windows port gaps

Public Steam AppID 335420 is evidenced by the official store, not local registry
or appmanifest reads. Twenty-three new injected-port/headless tests pass; full
suite 158/155/3. Native registry views, Tool Help structures/calls, process image
queries and real installation filesystem evidence remain untested. Tk code/data
were packaged, but no window, visual layout, focus, DPI or file dialog was tested.
Onedir/onefile CLI help/version and synthetic refusals passed without invoking
native detection. No licensed original was read in this milestone. The stat-based
read adapter cannot be used as a TOCTOU-safe writer. User-writable fixture backend
work is the next gate; privileged helper/trust/UAC support remains blocked.

## m032 actual native fixture evidence

The explicit native runner on Windows build 26200/NTFS ran 17 methods: 16 pass,
1 skip (real symlink privilege WinError 1314; no retry). File IDs, same/cross-process
sharing exclusion, exclusive backups, flush/readback, same-volume new-name rename,
real hardlink refusal and content-tamper checks have actual OS evidence. A first
wrapper-buffer defect was caught, corrected and retained in the local failure
manifest. Protected existing-target replacement returned WinError 5; no unlocked
retry was made. Native apply/recovery/uninstall therefore remain gated. These
results do not prove transaction rollback, hostile-directory safety, power-loss
durability or installation. See `WINDOWS-NATIVE-FIXTURE.md`.

Full default suite: **175 tests, 159 pass, 16 explicit skips** (13 native
fixture cases opt out; two licensed-input integrations and one existing symlink
case skip). The separate explicit native run is 17 tests, 16 pass, 1 skip; its
four policy tests overlap the default suite. No real-game integration was run.

## m033 capture transaction evidence

The m032 replacement failure is explained by its documented open-destination
conflict, not evidence of an application-control policy block. A different
fixture-only sequence retains DELETE-capable exclusive handles, captures the
original inode, then promotes with replace=False; 24 explicit methods pass
(20 native cases plus 4 schema cases). Journal-guided restoration after handles
close, rollback-gap interruptions, competing names and tamper refusal are tested.
This protocol has a missing-name interval and is not an atomic replacement. Real
process kill/power loss, independent production restart trust, metadata preservation
and live process detection remain unverified. Production apply remains false.
See `WINDOWS-CAPTURE-EXPERIMENT.md`.

Full default suite: 199 tests, 163 pass, 36 explicit skips (33 opt-in native
cases, two licensed-input integrations and the existing symlink skip). The
separate 24-method capture run has no skips; its four schema tests overlap.

## m034 actual process-termination evidence

The explicit worker suite passes 19 methods (16 native cases, 3 pure identity/schema
cases). Fourteen identity-verified TerminateProcess calls against newly owned
workers cover 11 commit/restore checkpoints and 3 refusal cases. All 43 workers
recorded exits. Fresh workers read persisted journals, and repeated restoration
is idempotent. Original IDs/basic attributes/creation/write times and sentinels
remain unchanged. The control process still retains an independent registration
digest; controller-loss/reboot trust and power-loss durability are not proved.
The m033 native regression suite also passes all 24 methods. Production apply
remains disabled; fixed invented bytes/64 KiB are not yet a real-copy installer.
See `WINDOWS-WORKER-RECOVERY.md` and `NEXT-ACCEPTANCE.md`.

Full default suite: **218 tests, 166 pass, 52 explicit skips** (49 opt-in
native cases, two licensed integrations and the existing symlink case). The
separate worker/capture suites are 19/19 and 24/24; their 7 pure methods overlap
the default suite. Skips are not counted as successful integrations.

## m035 update

Closed for the local disposable EXE: synthetic-only/64 KiB restriction, reviewed
PE builder integration, copy metadata roundtrip, and restart without a live
transaction controller (external receipt digest required). See DISPOSABLE-COPY.md.
Still open: power-loss durability, two-rename gap, hostile same-user tampering,
SACL/unusual metadata, production UI integration, elevated installation, runtime
and full-game translation coverage. No Actions/cloud game integration was run.

## m036 candidate boundary

Resolved offline: explicit confirmation/cancel/back/reentrant submission states,
fresh-copy install, protected independent recovery anchor, fresh-process restore,
already-restored state, asInvoker onefile CLI end-to-end and source integrity.
Native access denial is latched in the controller; that case was injected in a
test, not an actual security block. Missing/corrupt store never enables recovery.

Still unverified: actual Tk rendering, DPI/focus/dialogs and interactive transitions;
current-version gameplay, saves/reload and all 239 translated resource locations;
live Steam registry discovery; production target installation/UAC, malicious
same-account tampering, power loss/reboot and whole-engine Unicode/stability.
The executable-only disposable case cannot be launched as a complete game.
Do not count skipped native/licensed tests as passes or old limited observations
as current candidate gameplay. See CANDIDATE-ACCEPTANCE.md for bounded next steps.
