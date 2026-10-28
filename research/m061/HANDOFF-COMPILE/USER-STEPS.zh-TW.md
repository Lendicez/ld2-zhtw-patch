# 使用者步驟（約 10–20 分鐘）

1. 解壓 `m061-handoff-compile.zip`。
2. 若實驗室不在預設路徑，先設定：`$env:LD2_ZHTW_LAB = '<LD2_ROOT>\zhTW_lab'`。
3. 在 `HANDOFF-COMPILE` 目錄執行：`powershell -ExecutionPolicy Bypass -File .\WINDOWS-COMPILE.ps1`。若 Stage A 已成功過，改用 `... -File .\WINDOWS-COMPILE.ps1 -SkipStageA` 只跑 Stage B。
4. 確認結束無 throw；stdout 含 `failed=0` 與 `HANDOFF-COMPILE finished OK`。
5. 把 `runs\m061\compile-only\list_insert_w.obj` 與同目錄的 `compile-command.json` 打成 zip 傳回（不要包含 mock EXE 或遊戲檔）。
6. 完成。不必開遊戲。
