# 使用者步驟（約 10–20 分鐘，不開遊戲）

0. 若 m061 啟用版還沒收尾，先在原 `HANDOFF-LOADER-ENABLED` 目錄跑一次 `.\WINDOWS-LOADER-ENABLED.ps1 -DisposableRoot $D -Finalize`（`$D` 與當時步驟 L 相同）。本包與它互不影響，順序不限。
1. 解壓 `m061b-handoff-compile.zip`。
2. 若實驗室不在預設路徑：`$env:LD2_ZHTW_LAB = '<LD2_ROOT>\zhTW_lab'`。
3. 在 `HANDOFF-COMPILE-M061B` 目錄執行：`powershell -ExecutionPolicy Bypass -File .\WINDOWS-COMPILE.ps1`。
4. 確認沒有 throw，並出現 `cases=22 assertions=1116 failed=0` 與 `HANDOFF-COMPILE-M061B finished OK`。
5. 把 `runs\m061b\compile-only\` 內的 `list_insert_u.obj`、`list_insert_u.asm`、`compile-command.json`，以及 `runs\m061b\mock\once-result.json`、`stdout.txt` 打成 zip 傳回。不要放 mock EXE、遊戲檔、截圖或存檔。
