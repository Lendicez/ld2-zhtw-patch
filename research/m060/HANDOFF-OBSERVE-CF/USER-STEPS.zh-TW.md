# m060 第二次觀察：只跑 C～F（Win11 操作清單）

使用者已於 2026-10-28 批准續跑（t33u）。**只在第一次的可丟棄副本上操作**（`<LD2_ROOT>\zhTW_lab\game-acceptance\m060\`），不碰正式安裝、不重跑 A／B。
以下 `RUN` 代表：`powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -Run2`

**紅字「停止」、崩潰、錯誤框（MFC／C++ runtime）、卡住超過約 60 秒、被安全軟體擋下 → 停在那裡，只截圖，跳到第 7 步。**
黃字「警告（軟警告，可繼續）」＝結束碼 1 但沒有崩潰跡象且有存檔：可以繼續下一步，但**若你當下有看到錯誤框，一律當作停止**。

1. 關閉遊戲與 Steam 的遊戲程序。把 zip 解壓到 `<LD2_ROOT>\zhTW_lab\research\m060\`（會產生 `HANDOFF-OBSERVE-CF\`），在該資料夾開 PowerShell，執行 `Unblock-File .\WINDOWS-ONCE.ps1`。
2. **R 檢查＋準備**：先 `RUN -CheckOnly`（只檢查，必須出現綠字「完整性檢查全部通過」），再 `RUN`。會建立 `game-acceptance\m060\evidence-run2\`。第一次的 `evidence\` 不會被改動。
   - 遊戲或副本不在 C 槽（例如 E 槽）時，兩個指令都加 `-LD2Root "<磁碟>:\GameDev\LD2"`（把 `<磁碟>` 換成實際磁碟代號，例如 E）。
3. **C m045**：`RUN -LaunchStep C`。截圖主選單、檔案選單、F1 說明、狀態列。
4. **D**（同一次遊戲）：讀**第 1 格**（第一次觀察時原版存的），角色／道具／設施／戰鬥畫面能開的各開一次並截圖。道具名稱還是日文屬正常。
5. **E**（同一次遊戲）：存到**第 2 格**（不要覆蓋第 1 格），然後**從遊戲選單「結束」**離開。
6. **F 原版讀回**：`RUN -LaunchStep F`。讀**第 2 格**並截圖（日期欄「?」是已知問題）；再存到**第 3 格**（新格，不覆蓋 1、2），然後從選單「結束」離開。
7. **G 收尾**：`RUN -Finalize`（就算前面停止了也要跑；它不會啟動遊戲）。應出現綠字「原目錄未變動」。
8. 截圖檔名以步驟字母開頭（如 `C-main-menu.png`、`D-item.png`、`F-load.png`），放進 `game-acceptance\m060\evidence-run2\screens\`。
9. 填好 `evidence-run2\observations.md`，**特別是每次是不是從遊戲選單正常結束**、有沒有看到錯誤框、字型問題在哪個畫面。
10. 把 `evidence-run2\` 的全部內容複製到 `<LD2_ROOT>\zhTW_lab\runs\m060-observe-run2\`，壓成 `m060-observe-run2-evidence.zip` 回傳。**只放證據**：不放 EXE、遊戲素材、存檔本體、dump 本體。
