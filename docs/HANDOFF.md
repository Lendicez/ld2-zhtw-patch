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
