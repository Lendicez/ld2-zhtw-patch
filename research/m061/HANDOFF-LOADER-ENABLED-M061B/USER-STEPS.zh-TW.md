# m061b 清單 Unicode 版驗收：使用者步驟（Win11）

**這一包會在「拋棄式副本」裡開一次遊戲。** 原本的安裝只會被讀取，不會被改。下面每一段都可以整段複製、貼到 PowerShell，再按 Enter。

## 0. 準備

1. 先關閉遊戲（包含 Steam 啟動的那個）。
2. 把 zip 解壓到這個資料夾：
   C 槽的 `\GameDev\LD2\zhTW_lab\research\m061\`
   解壓後應該會出現 C 槽的 `\GameDev\LD2\zhTW_lab\research\m061\HANDOFF-LOADER-ENABLED-M061B\`。
3. 開 PowerShell：按「開始」，輸入 `PowerShell`，按 Enter。

> 指令裡的 `$env:SystemDrive` 會自動變成 `C:`，照貼即可。

## 1. 進入資料夾、解除封鎖、設定副本路徑

整段貼上（意思：切到交接包資料夾；解除 Windows 對下載檔案的封鎖；設定這次副本要放在哪）：

```powershell
cd "$env:SystemDrive\GameDev\LD2\zhTW_lab\research\m061\HANDOFF-LOADER-ENABLED-M061B"
Unblock-File .\WINDOWS-LOADER-ENABLED-M061B.ps1
$D = "$env:SystemDrive\GameDev\LD2\zhTW_lab\game-acceptance\m061b-loader-enabled"
```

> 如果中途關掉了 PowerShell，重新開啟後要**再貼一次這一段**（`$D` 只在同一個視窗裡有效）。

## 2. 只檢查（不寫任何檔案）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-ENABLED-M061B.ps1 -DisposableRoot $D -CheckOnly
```

應該看到綠字：「存檔來源 OK」、「記憶體內合併 OK（m061b 啟用版，清單模式 2）：sha256 = 3a1b75b3…」、「-CheckOnly：前置全部通過」。
出現黃字「沒有存檔」或紅字「停止」：把整段輸出貼給 Mona，先不要往下。

## 3. 建立拋棄式副本（P）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-ENABLED-M061B.ps1 -DisposableRoot $D
```

最後應該看到綠字「步驟 P 完成」。

## 4. 啟動一次並觀察（L）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-ENABLED-M061B.ps1 -DisposableRoot $D -Launch
```

遊戲開啟後，依序操作、每個畫面截一張圖（Win＋Shift＋S 截圖後存檔），檔名照下面：

- `L-title.png`：標題畫面。接著讀**第 2 格**存檔（沒有就第 1 格）。
- `L-shop-buy.png`、`L-shop-sell.png`、`L-shop-upgrade.png`：商店的購買、出售、強化清單。
- `L-tavern.png`：酒館清單。
- `L-inn-commission.png`：旅館委託清單。
- `L-commission-list.png`、`L-commission-info.png`：委託一覽、委託資訊。
- `L-item-desc.png`：任一道具的說明視窗（看名稱那一行）。
- **這次重點**：清單裡的片假名／平假名是否正常顯示（上次是 `?`）。在清單裡上下選幾個項目看看有沒有異常，但**不要真的買賣、不要存檔**。
- 最後從遊戲選單「結束」離開。
- 若跳出錯誤框、崩潰，或卡住超過約 60 秒：先截 `L-error.png`，再關掉，**不要重試**。

遊戲關掉後，PowerShell 會印出結果（黃字「結束碼 1」是這款遊戲正常結束的值）。

## 5. 收尾（G，一定要跑，就算前面失敗也要）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-ENABLED-M061B.ps1 -DisposableRoot $D -Finalize
```

應該看到綠字「原目錄未變動。G 完成。」

## 6. 放截圖、填觀察、壓縮回傳

1. 把截圖放進：C 槽的 `\GameDev\LD2\zhTW_lab\game-acceptance\m061b-loader-enabled\evidence\screens\`
2. 用記事本打開並填寫（每個畫面寫繁中／日文正常／`?` 亂碼／未到達；有沒有錯誤框；是否從選單結束）：

```powershell
notepad "$env:SystemDrive\GameDev\LD2\zhTW_lab\game-acceptance\m061b-loader-enabled\evidence\observations.md"
```

3. 存檔關閉記事本後，貼上這行把證據壓成 zip（會放到桌面）：

```powershell
Compress-Archive -Path "$env:SystemDrive\GameDev\LD2\zhTW_lab\game-acceptance\m061b-loader-enabled\evidence\*" -DestinationPath "$env:USERPROFILE\Desktop\m061b-loader-enabled-evidence.zip"
```

4. 把桌面上的 `m061b-loader-enabled-evidence.zip` 傳回來。（裡面只有紀錄與截圖，沒有 EXE、存檔本體或 dump。）

## 如果模式 2 出問題（只在 Mona 要求時才做）

用保底版（模式 0）另建**新的**副本，所有指令都多加 `-Mode0`，副本換一個新路徑：

```powershell
cd "$env:SystemDrive\GameDev\LD2\zhTW_lab\research\m061\HANDOFF-LOADER-ENABLED-M061B"
$D0 = "$env:SystemDrive\GameDev\LD2\zhTW_lab\game-acceptance\m061b-loader-enabled-mode0"
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-LOADER-ENABLED-M061B.ps1 -DisposableRoot $D0 -Mode0 -CheckOnly
```

（後續 P／`-Launch`／`-Finalize` 也同樣把 `$D` 換成 `$D0` 並加 `-Mode0`。）

## 遊戲不在 C 槽時

把上面指令裡所有 `$env:SystemDrive` 換成實際的磁碟代號（例如 `E:`）。另外在每一行 `-DisposableRoot $D` 後面加上 `-LD2Root "E:` 與 `\GameDev\LD2"` 連在一起的路徑（也就是 E 槽的 GameDev\LD2 資料夾）。
