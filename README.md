# ld2-zhtw-patch
ld2-zhtw-patch

繁體中文化與適度優化的 Patch 開發準備庫。**目前不是可安裝發行版。**
Repository：[Lendicez/ld2-zhtw-patch](https://github.com/Lendicez/ld2-zhtw-patch)。
原始碼經使用者批准公開；尚未發布可安裝版本，也未啟用 Actions。

目前移植 m020 已審核資源文字：239 個位置、181 組原文/譯文對應、178 種譯文內容。
這些數字不是遊戲文字覆蓋率。目錄只含繁中譯文、來源雜湊和定位資訊，不包含整份原文。
資源分支限定 ACP950；沒有全域改碼頁、程式碼 hook 或 native adapter。

## 重跑

使用 Python 3.11+，只需標準函式庫，不安裝套件：

```sh
python -B tools/check.py
```

本機持有合法原檔時，可額外做唯讀、記憶體內重建：

```sh
python -B tools/check.py --game-exe "你的遊戲副本/Ld95.exe"
```

缺原檔時 integration 顯示 SKIPPED；Windows 原生 CP950 API 測試在非 Windows 也顯示 SKIPPED。
重建結果只在記憶體比對 m020 雜湊，不寫入或啟動遊戲。雲端不得上傳原檔來補測。
GitHub Windows runner 不等於 Windows 11 GUI 遊玩驗收。

完整接續說明見 [HANDOFF](docs/HANDOFF.md)、[安裝器規格](docs/INSTALLER-SPEC.md)、
[架構](docs/ARCHITECTURE.md)、[驗證缺口](docs/VALIDATION-GAPS.md)。

## Read-only install preview

The m026 core discovers Steam candidates from injected roots and bounded VDF files, then plans an EXE-only change without writing. Run `python -B tools/dry_run_demo.py` for an entirely synthetic example. See [DRY-RUN.md](docs/DRY-RUN.md) for evidence requirements and refusal reasons. Lazy read-only Windows ports and the official Steam AppID are now implemented/verified in m031, but local installation detection remains untested. No production installer is implemented and real release approval remains false.

## Synthetic transaction experiments

The stacked m027 change adds a single-file install/uninstall and recovery algorithm behind synthetic filesystem ports. Tests use private temporary files only; production apply remains disabled. See [TRANSACTIONS.md](docs/TRANSACTIONS.md) for the failure model and unverified Windows guarantees.

## Rebuild the reviewed resource patch offline

`tools/build_patch.py` now accepts an explicitly supplied original EXE and writes new build artifacts outside its directory. It verifies the original version, catalog recipe and exact historical m020 output; it never installs or runs the EXE. See [BUILD.md](docs/BUILD.md) for the command, actual local evidence and the still-unverified gameplay scope. Do not upload the generated EXE.

## Native Windows fixture evidence

The m032 backend primitives were tested on fresh synthetic NTFS files, including
cross-process locks, file IDs and verified staging. Safe replacement of an existing
locked target remains unresolved, so installation and native recovery stay disabled.
See [the actual results and limits](docs/WINDOWS-NATIVE-FIXTURE.md).

The m033 [capture experiment](docs/WINDOWS-CAPTURE-EXPERIMENT.md) demonstrates
actual synthetic commit/rollback without unlocking the original inode or
overwriting a competing name. It has a temporary missing-name interval and remains
fixture-only; it does not enable installation.

The m034 [worker recovery tests](docs/WINDOWS-WORKER-RECOVERY.md) terminate only
newly owned, identity-verified fixture workers and recover in fresh interpreters.
Production installation remains disabled; see the [remaining acceptance steps](docs/NEXT-ACCEPTANCE.md).

## m035 offline disposable-copy acceptance

The reviewed real EXE was rebuilt, installed into a new disposable copy, and
restored in another process with matching original hash/identity/metadata.
No game execution occurred; production installation remains disabled.
Read [the bounded protocol and evidence](docs/DISPOSABLE-COPY.md).

## m036 集中驗收候選版

單一 EXE 已接上繁中確認介面、僅限新建可丟棄副本的安裝流程，以及
由目前 Windows 使用者 DPAPI 保護的獨立復原憑據。確認前不寫入，
不需抄 hash 或編輯 JSON；憑據缺失、損壞或身分不符時拒絕復原。
正式 can_apply 仍為 false，既有遊戲目錄安裝停用。

最終 onefile 已完成 CLI 新副本安裝、跨程序還原與原版完整性核對；
GUI 視覺、遊戲操作和主機 Steam 偵測仍未驗收，沒有執行遊戲。
請讀 [候選版與一次驗收清單](docs/CANDIDATE-ACCEPTANCE.md) 和
[翻譯現況](docs/TRANSLATION-STATUS.md)。下一輪優先回到文字內容。

## m037 戰鬥 UI 文字增量

新增 32 個未翻譯資源位置、24 組不同譯文，涵蓋目標選擇、特殊技能、
陣形轉向、逃跑確認及戰鬥選單／提示。m037 合計 271 個文字位置，
不是全遊戲覆蓋率。使用獨立 profile 與嚴格輸出雜湊，m020 保留不變。
用 tools/build_patch.py --profile m037 明確選擇；預設工具和 m036 候選
仍使用 m020。兩次離線重建與原檔完整性已驗證，遊戲與 GUI 尚未實測。
詳見 [本批內容與證據](docs/M037-COMBAT-UI.md)。

## m038 本機離線內容
新增 24 個位置、22 組不同譯文，累計 295 個位置，涵蓋移動、離隊、
分配道具及委託詳情。--profile m038 可離線產生新輸出，預設仍為 m020。
原版、m020、m037 參考均保留，尚未遊戲驗收或開放正式安裝。
[完整範圍](docs/M038-TRAVEL-PARTY-QUEST.md)。
