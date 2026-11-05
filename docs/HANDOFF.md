# 接續說明（2026-11-05 起由 Claude 接手）

目標：《Lunatic Dawn II》自用繁中化與 Win11 可執行調整，最終單一 Windows 安裝 EXE。
Repository：https://github.com/Lendicez/ld2-zhtw-patch（owner Lendicez）。開發主線：PR #26（Draft）。

## 分工與環境
- 雲端 Claude：repo 讀寫與推送（GitHub App）、工具與測試開發、文件。
- 本機 Win11（lab 機，ACP 950）：`<LD2>\zhTW_lab\ld2-autotest\`（本機 lab 根，不在本庫） 的 harness 與 `watch_jobs.py` 工作佇列
  （`bridge\queue\*.json` → `bridge\results\`）。可執行 python／git／claude（Claude Code CLI，看圖判讀）／Codex（經 `dispatch.py`，繪圖與譯稿）。
- 本機工作樹 `<LD2>\ld2-zhtw-patch-claude`（pull only）。lab 資料、截圖、圖檔一律留在本機。

## lab 建置流程（m064）
1. 起點：m063d 啟用版 `Ld95.exe`（sha256 `240ab04d…4121`；`.rdata` 與 pristine 相同）。
2. `research/m064/rdata_ansi.py apply --catalog research/translations/m063-draft*.json --catalog research/m064/lab-extra-*.json --exclude-subcategory place_ui --exclude-subcategory road_name`
3. 本機 `m064-lab\img\apply_images.py`：RES BMP／EXE RT_BITMAP／RES BMH 換成重繪版（格式、調色盤逐位元組不變）。
4. harness 回歸（讀檔、旅館、酒館、委託、訓練所、道具店、武器店、傳聞、UI 煙霧、角色視窗）＋截圖判讀，
   逐列記入 `research/m064/SITE-LEDGER.json`。

## 規則
- `production_can_apply`／`release_approved` 維持 false；正式套用需擁有者批准。
- hook 路徑（m063 v4 TextOut）字串不可原位改 Big5 → 走 v4 catalog。
- 新增入庫檔案須同時列入 `.gitignore` 白名單與 `UPLOAD_ALLOWLIST.json`；`python -B tools/check.py`、`tools/audit_upload.py` 必須無新 finding。
- 不上傳遊戲資產與其衍生圖；不動 Steam 原安裝與 lab `baseline`。傳聞多頁彈窗不可送 WM_CLOSE（用左鍵 dismiss）。

## 目前待辦
見 PR #26 說明與 `research/m064/RESULT-M064-RDATA-LAB.zh-TW.md`。重點：狀態面板字形定稿、角色狀態視窗路徑、
移動地圖 17 張、place_ui／road_name／城鎮名進 v4 catalog、裝備視窗與讀檔清單亂碼、`0x166e28` 修稿。

歷史（m020～m063 的雲端 staging 交接、安裝器與 CI 規劃）見 `MIGRATION-INVENTORY.md`、`INSTALLER-SPEC.md`、`CI-PLAN.md`。
