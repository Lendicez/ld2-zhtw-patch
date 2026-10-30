# m061 惰性 loader 驗收：使用者步驟（Win11）

**絕對不碰正式安裝**：腳本只讀遊戲資料夾，只寫到你指定的「新」副本資料夾。`production_can_apply` 永遠是 false。
本次 EXE 不含任何啟用的翻譯功能；只看「能不能正常開到標題畫面」。

以下 `$D` 是副本資料夾，**必須是還不存在的新路徑**（預設在系統磁碟，通常是 C 槽）：

```powershell
$D = "$env:SystemDrive\GameDev\LD2\zhTW_lab\game-acceptance\m061-loader-inert"
```

遊戲或 lab 不在 C 槽時，把 `$env:SystemDrive` 換成實際磁碟（例如 `E:`），並在下面每個指令加上 `-LD2Root "<磁碟>:\GameDev\LD2"`。

1. 關閉遊戲與 Steam 的遊戲程序。把 zip 解壓到 `<LD2_ROOT>\zhTW_lab\research\m061\`（會產生 `HANDOFF-LOADER-INERT\`），在該資料夾開 PowerShell，先執行上面的 `$D = ...`，再執行 `Unblock-File .\WINDOWS-LOADER-INERT.ps1`。
2. **檢查（不寫檔）**：
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-INERT.ps1 -DisposableRoot $D -CheckOnly`
   必須出現綠字「記憶體內合併 OK：sha256 = 6a43dc4e…」與「前置全部通過」。
3. **P 準備**（建立副本、寫入惰性 EXE）：
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-INERT.ps1 -DisposableRoot $D`
4. **L 啟動一次**：
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-INERT.ps1 -DisposableRoot $D -Launch`
   - 看到標題畫面 → 截圖存成 `L-title.png` → 從標題選單「結束」離開（不用開新遊戲、不用讀檔）。
   - 若跳出錯誤框（找不到程序進入點、0xc000007b、MFC 錯誤等）→ 截圖 `L-error.png` → 按確定關閉。**不要重試。**
5. **G 收尾**（就算第 4 步失敗也要跑；不會啟動遊戲）：
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-INERT.ps1 -DisposableRoot $D -Finalize`
   應出現綠字「原目錄未變動」。
6. 截圖放 `$D\evidence\screens\`；填 `$D\evidence\observations.md`（有沒有看到標題畫面、有沒有錯誤框、是不是從選單結束）。
7. 把 `$D\evidence\` 整個資料夾壓成 `m061-loader-inert-evidence.zip` 回傳。

**要回傳的證據**：`hashes-before.json`、`launch-L.json`（含結束碼、事件數、dump、`module_probe`）、`launch-L-events.txt`（若有）、`hashes-after.json`、`state.json`、`observations.md`、`screens\*.png`。
**不要放**：EXE、遊戲素材、存檔、dump 本體。
