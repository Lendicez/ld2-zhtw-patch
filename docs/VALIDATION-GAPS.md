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
