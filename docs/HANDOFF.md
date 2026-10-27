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
