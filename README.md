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

The m026 core discovers Steam candidates from injected roots and bounded VDF files, then plans an EXE-only change without writing. Run `python -B tools/dry_run_demo.py` for an entirely synthetic example. See [DRY-RUN.md](docs/DRY-RUN.md) for evidence requirements and refusal reasons. No live registry/filesystem adapter or installer is implemented; AppID remains unverified and real release approval remains false.

## Synthetic transaction experiments

The stacked m027 change adds a single-file install/uninstall and recovery algorithm behind synthetic filesystem ports. Tests use private temporary files only; production apply remains disabled. See [TRANSACTIONS.md](docs/TRANSACTIONS.md) for the failure model and unverified Windows guarantees.
