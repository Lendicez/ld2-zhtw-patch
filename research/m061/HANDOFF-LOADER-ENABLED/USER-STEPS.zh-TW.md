# m061 啟用版驗收：使用者步驟（Win11）

**絕對不碰正式安裝。** 只寫到你指定的「新」副本資料夾，`production_can_apply` 永遠是 false。這次 EXE 會真的啟用清單和說明視窗的翻譯 helper。

```powershell
$D = "$env:SystemDrive\GameDev\LD2\zhTW_lab\game-acceptance\m061-loader-enabled"
```
遊戲或 lab 不在 C 槽時，把 `$env:SystemDrive` 換成實際的磁碟代號（例如 `E:`），並在每個指令後面加 `-LD2Root "<磁碟>:\GameDev\LD2"`。

1. 先關閉遊戲。把 zip 解壓到 `<LD2_ROOT>\zhTW_lab\research\m061\`，在 `HANDOFF-LOADER-ENABLED\` 資料夾開 PowerShell，執行上面那行 `$D = ...`，再執行 `Unblock-File .\WINDOWS-LOADER-ENABLED.ps1`。
2. **檢查**：
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-ENABLED.ps1 -DisposableRoot $D -CheckOnly`
   要看到綠字「存檔來源 OK」「記憶體內合併 OK（啟用版）：sha256 = 57103342…」「前置全部通過」。如果出現黃字「沒有存檔」，請先回報，不要往下做。
3. **P 準備**：
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-ENABLED.ps1 -DisposableRoot $D`
4. **L 啟動一次**：
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-ENABLED.ps1 -DisposableRoot $D -Launch`
   在同一次遊戲裡依序操作，每個畫面都截圖：
   - `L-title.png`：標題畫面。接著讀**第 2 格**存檔（沒有的話讀第 1 格）。
   - `L-shop-buy.png`、`L-shop-sell.png`、`L-shop-upgrade.png`：商店的購買、出售、強化清單。
   - `L-tavern.png`：酒館清單。`L-inn-commission.png`：旅館委託清單。`L-commission-list.png`／`L-commission-info.png`：委託一覽和委託資訊。
   - `L-item-desc.png`：任何一個道具的說明視窗（看名稱那一行）。
   - 打不開的畫面就跳過，並在觀察紀錄寫「未到達」。**不要存檔。** 最後從遊戲選單「結束」離開。
   - 如果出現錯誤框、程式崩潰，或卡住超過約 60 秒：先截圖 `L-error.png`，再關掉，**不要重試**。
5. **G 收尾**（就算前面失敗也要跑）：
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-ENABLED.ps1 -DisposableRoot $D -Finalize`
   應該出現綠字「原目錄未變動」。
6. 把截圖放進 `$D\evidence\screens\`。**務必填好 `$D\evidence\observations.md`**，包括：每個清單顯示的是繁中、日文還是 `?`／亂碼；有沒有出現錯誤框；是不是從選單「結束」離開。
7. 把 `$D\evidence\` 整個資料夾壓成 `m061-loader-enabled-evidence.zip` 回傳。不要放 EXE、存檔本體或 dump。
