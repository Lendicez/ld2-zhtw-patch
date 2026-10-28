# m060 觀察：Win11 操作清單（只做一次）

所有指令都在 `<LD2_ROOT>\zhTW_lab\research\m060\HANDOFF-OBSERVE\` 的 PowerShell 執行。以下 `RUN` 代表 `powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1`。
**任何一步出現紅字「停止」、崩潰、錯誤框、卡住超過約 60 秒，或被安全軟體擋下：就停在那裡，只截圖，跳到第 10 步。**

1. 關閉遊戲與 Steam 的遊戲程序。把 zip 解壓到 `<LD2_ROOT>\zhTW_lab\research\m060\`（會產生 `HANDOFF-OBSERVE\`），執行 `Unblock-File .\WINDOWS-ONCE.ps1`。
2. **檢查**：`RUN -CheckOnly`，必須出現綠字「前置全部通過」。找不到 m045 時，照畫面上的指令離線生成，再跑一次本步。
3. **A 複製＋hash**：`RUN`。會建立 `zhTW_lab\game-acceptance\m060\`（不含你的 `Usr\` 存檔）和 `evidence\hashes-before.json`。
4. **B 原版**：`RUN -LaunchStep B`。開新遊戲，存到**第 1 格**，截圖（標題、存檔畫面），然後從選單正常退出。
5. **C m045**：`RUN -LaunchStep C`。截圖主選單、檔案選單、F1 說明、狀態列。
6. **D**（同一次遊戲）：讀**第 1 格**，角色／道具／設施／戰鬥畫面能開的各開一次並截圖。道具名稱還是日文屬正常。
7. **E**（同一次遊戲）：存到**第 2 格**（不要覆蓋第 1 格），然後正常退出。
8. **F 原版讀回**：`RUN -LaunchStep F`。讀**第 2 格**並截圖；日期欄顯示「?」是已知問題。然後退出。
9. **G 收尾**：`RUN -Finalize`。應出現綠字「原目錄未變動」。
10. 截圖檔名以步驟字母開頭（如 `C-main-menu.png`），放進 `game-acceptance\m060\evidence\screens\`。填好 `evidence\observations.md`。
11. 把 `evidence\` 的全部內容複製到 `<LD2_ROOT>\zhTW_lab\runs\m060-observe\`，壓縮成 `m060-observe-evidence.zip` 回傳。**只放證據**：不放 EXE、遊戲素材、私人存檔、dump 本體。
