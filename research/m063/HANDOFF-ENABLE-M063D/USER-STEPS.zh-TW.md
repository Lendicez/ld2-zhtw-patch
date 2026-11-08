# m063d v4 啟用驗收：使用者步驟（Win11）

**這一包不用編譯**，只會在「拋棄式副本」裡開兩次遊戲：先開「惰性版」（應該和以前一樣），通過後才換成「v4 啟用版」再開一次觀察。原本的安裝只會被讀取，不會被改。

每一段指令都可以**整段複製 → 貼到 PowerShell → 按 Enter**。每段上面一行是「這段在做什麼」。

## 開始前確認（勾完再開始）

- [ ] 遊戲已完全關閉（包含 Steam 啟動的那個）。
- [ ] 遊戲安裝在 C 槽的 `\GameDev\LD2\LunaticDawnPotB\`（不是的話看最後一節）。
- [ ] 之前 m060 的副本還在：C 槽的 `\GameDev\LD2\zhTW_lab\game-acceptance\m060\`（裡面有 m045 版 EXE 和存檔）。
- [ ] 已把交接 zip 解壓到 C 槽的 `\GameDev\LD2\zhTW_lab\research\m063\`，並看到 `HANDOFF-ENABLE-M063D` 資料夾。
- [ ] 預留約 30–45 分鐘；需要能截圖（Win＋Shift＋S）。
- 不需要 Visual Studio／MSVC，也不需要網路。

開 PowerShell：按「開始」，輸入 `PowerShell`，按 Enter。

> 指令裡的 `$env:SystemDrive` 會自動變成 `C:`，照貼即可。黃字「結束碼 1」是這款遊戲從選單結束時的正常值。

## 1. 進入資料夾、解除封鎖、設定副本路徑

這段：切到交接包資料夾、解除 Windows 對下載檔的封鎖、設定這次副本放哪（`$D`）。

```powershell
cd "$env:SystemDrive\GameDev\LD2\zhTW_lab\research\m063\HANDOFF-ENABLE-M063D"
Unblock-File .\WINDOWS-ENABLE-M063D.ps1
$D = "$env:SystemDrive\GameDev\LD2\zhTW_lab\game-acceptance\m063d-v4-enable"
```

> 中途關掉 PowerShell 的話，重新開啟後要**先再貼一次這一段**（`$D` 只在同一個視窗有效）。

## 2. 只檢查（CheckOnly，不寫任何檔案）

這段：確認原版 EXE、m045、交接檔都對，並在記憶體裡合出兩個 EXE 比對 hash；不寫檔。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ENABLE-M063D.ps1 -DisposableRoot $D -CheckOnly
```

應該看到綠字：「記憶體內合併 OK（v4 啟用版，清單模式 2）：sha256 = 240ab04d…」、「記憶體內還原 OK（v4 惰性版）：sha256 = c796bc12…」、「-CheckOnly：前置全部通過」。
出現紅字「停止」：把整段輸出貼回來，先不要往下。黃字「沒有存檔」也先回報。

## 3. 建立拋棄式副本（P）

這段：複製一份遊戲到 `$D\game`，放入存檔副本，把副本裡的 `Ld95.exe` 換成「惰性版」。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ENABLE-M063D.ps1 -DisposableRoot $D
```

最後應該看到綠字「步驟 P 完成 … 下一步：-LaunchInert」。

## 4. 惰性版啟動一次（L1）

這段：用惰性版開一次遊戲，確認新加的段落本身不會讓遊戲壞掉。畫面應該和以前 m045 一樣（清單多半是日文，這是正常的）。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ENABLE-M063D.ps1 -DisposableRoot $D -LaunchInert
```

遊戲開啟後：

1. 標題畫面截圖 `L1-title.png` → 讀取**第 2 格**存檔（沒有就第 1 格）。
2. 進任一商店，打開「購買」清單，截圖 `L1-shop-buy.png`。
3. 不要買賣、不要存檔；從遊戲選單「結束」離開。

遊戲關掉後看 PowerShell：

- 綠字或黃字「L1 通過 … 下一步：-Enable」→ 繼續第 5 步。
- 紅字「L1 未通過」或跳錯誤框／崩潰／卡住 → **不要做第 5、6 步**，直接跳到第 8 步收尾。

## 5. 換成啟用版（E，只換副本裡的檔）

這段：確認 L1 通過後，把**副本**裡的 `Ld95.exe` 從惰性版換成 v4 啟用版（原安裝不動）。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ENABLE-M063D.ps1 -DisposableRoot $D -Enable
```

應該看到綠字「步驟 E 完成」。

## 6. 啟用版啟動一次並觀察（L2）

這段：用 v4 啟用版開一次遊戲，依第 7 節逐一截圖觀察。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ENABLE-M063D.ps1 -DisposableRoot $D -LaunchEnabled
```

## 7. L2 要看的畫面與截圖檔名

到不了的畫面就跳過，在 observations.md 寫「未到達」。**不要真的買賣、不要存檔。**

| 順序 | 畫面 | 截圖檔名 | 看什麼 |
|---|---|---|---|
| 1 | 標題 → 讀第 2 格存檔 | `L2-title.png` | 能正常讀檔 |
| 2 | 主畫面下方隊伍名字（6 格） | `L2-party-panel.png` | 名字是繁中／日文／亂碼／空白；陰影有沒有疊歪 |
| 3 | 任一角色資訊視窗 | `L2-char-info.png` | 左上角名字、下方頁尾名字 |
| 4 | 商店「購買」 | `L2-shop-buy.png` | 道具名；有「波刃短劍」「戟斧」就另截 `L2-kris-item.png`、`L2-halberd.png` |
| 5 | 商店「出售」「強化」 | `L2-shop-sell.png`、`L2-shop-upgrade.png` | 道具名、選取後價格是否對得上 |
| 6 | 酒館冒險者清單 | `L2-tavern.png` | 男女名字；若看到「克莉絲」截 `L2-kris-name.png`（應是人名，不是短劍） |
| 7 | 旅館委託、委託一覽、委託資訊 | `L2-inn-commission.png`、`L2-commission-list.png`、`L2-commission-info.png` | **清單裡是人名、物品，還是混合**（這題決定下一版怎麼分類） |
| 8 | 其他人名清單（能開的就開） | `L2-list-party.png`、`L2-list-proposal.png`、`L2-list-education.png`、`L2-list-item-page.png`、`L2-list-item-arrange.png` | 名字是否正常、選取是否正常 |
| 9 | 任一道具說明視窗 | `L2-item-desc.png` | 名稱那一行 |
| 10 | 從遊戲選單「結束」離開 | — | — |

順便留意（看到才記）：

- 名字裡有這 7 個字之一：**咲 宍 惣 杢 梶 榊 笹**（原本 CP950 打不出來）→ 截 `L2-rare-char.png`，記是否正常顯示。
- 說明文字和名字對不太上的道具（24 筆已收錄的那一批）→ 記在 observations.md 的「其他」。
- 若跳出錯誤框、崩潰，或卡住超過約 60 秒：先截 `L2-error.png`，再關掉，**不要重試**。

## 8. 收尾（G，一定要跑，前面失敗也要跑）

這段：唯讀比對原安裝，確認原目錄完全沒被動過，寫下 hashes-after.json。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ENABLE-M063D.ps1 -DisposableRoot $D -Finalize
```

應該看到綠字「原目錄未變動。G 完成。」

## 9. 放截圖、填觀察

這段：打開放截圖的資料夾（把 Win＋Shift＋S 存下的圖拖進去）。

```powershell
explorer "$env:SystemDrive\GameDev\LD2\zhTW_lab\game-acceptance\m063d-v4-enable\evidence\screens"
```

這段：用記事本打開觀察表，照裡面的格子填寫，存檔後關閉。

```powershell
notepad "$env:SystemDrive\GameDev\LD2\zhTW_lab\game-acceptance\m063d-v4-enable\evidence\observations.md"
```

## 10. 打包回傳（Z）

這段：檢查證據資料夾只有紀錄與截圖（沒有 EXE、存檔、dump），壓成桌面上的 zip。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ENABLE-M063D.ps1 -DisposableRoot $D -Pack
```

應該看到綠字「已壓縮：…\Desktop\m063d-v4-enable-mode2-evidence.zip」。若黃字說 observations.md 還沒填，回第 9 步填完再跑一次。

## 要回傳什麼

1. 桌面上的 `m063d-v4-enable-mode2-evidence.zip`。
2. 如果哪一步出現紅字「停止」：那一步 PowerShell 的完整輸出（文字貼上即可）。

## 如果模式 2 出問題（只在 Mona 要求時才做）

用保底版（模式 0）另建**新的**副本：所有指令都多加 `-Mode0`，副本換新路徑 `$D0`。

這段：設定模式 0 副本路徑，並先做只檢查。

```powershell
cd "$env:SystemDrive\GameDev\LD2\zhTW_lab\research\m063\HANDOFF-ENABLE-M063D"
$D0 = "$env:SystemDrive\GameDev\LD2\zhTW_lab\game-acceptance\m063d-v4-enable-mode0"
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ENABLE-M063D.ps1 -DisposableRoot $D0 -Mode0 -CheckOnly
```

之後第 3–10 步照做，只是把 `$D` 換成 `$D0` 並在每行最後加 `-Mode0`；第 9 步的路徑資料夾名改成 `m063d-v4-enable-mode0`。

## 遊戲不在 C 槽時

把上面指令裡所有 `$env:SystemDrive` 換成實際磁碟代號（例如 `E:`），並在每一行 `-DisposableRoot $D` 後面加上 `-LD2Root "E:` 與 `\GameDev\LD2"` 連在一起的路徑（也就是 E 槽的 GameDev\LD2 資料夾）。
