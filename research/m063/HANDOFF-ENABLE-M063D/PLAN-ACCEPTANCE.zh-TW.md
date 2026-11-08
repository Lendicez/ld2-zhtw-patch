# m063d v4 啟用驗收計畫

> 狀態：Linux 端準備完成，**未在 Win11 執行**。`production_can_apply=false`、`release_approved=false`。

## 目的

在 Win11 實機確認 v4 三個 helper（NamePair／ListInsert v4／NameTextOut）啟用後：

1. 遊戲能載入、能讀檔、能從選單正常結束（穩定性）。
2. 名字與道具在清單、TextOut 上的實際顯示（STATUS 阻礙表 #1、#2、#4 與 commission 分類）。

不包含：編譯（m063b 已完成並 pin）、發行用 catalog、任何對正式安裝的寫入。

## 階段

| 代號 | 指令開關 | 做什麼 | 寫入 | 通過條件 |
|---|---|---|---|---|
| C | `-CheckOnly` | 驗來源原版、找 m045、驗 delta、記憶體內合成啟用版＋還原惰性版並比 hash | 無 | 全綠 |
| P | （無） | 建副本；exe-store 放原版／惰性版／啟用版；`game\Ld95.exe`＝惰性版；hashes-before.json | 只寫副本 | 全綠 |
| L1 | `-LaunchInert` | 惰性版啟動一次：標題→讀檔→商店購買→選單結束 | launch-L1.json | `ok` 或 `soft-warn-exit1` |
| E | `-Enable` | L1 通過才允許；把**副本**的 `game\Ld95.exe` 換成啟用版 | enable-E.json | hash 相符 |
| L2 | `-LaunchEnabled` | 啟用版啟動一次：觀察巡迴（見 USER-STEPS 第 7 節） | launch-L2.json | `ok` 或 `soft-warn-exit1`＋觀察表 |
| G | `-Finalize` | 唯讀比對原安裝 manifest | hashes-after.json | 原目錄 0 變動 |
| Z | `-Pack` | 檢查證據副檔名／大小、觀察表已填，壓縮到桌面 | 桌面 zip | 產出 zip |

任何 `hard-stop` 之後：只跑 G 與 Z。L1 `hard-stop` 時 E／L2 會被腳本拒絕。

## 預期 hash

| 項目 | 值 |
|---|---|
| 來源原版 `Ld95.exe` | `6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2`（7,090,176 B） |
| m045 基底 | `4a0910243d159af8007b5e77369c21f262d9e7a402bcb92a991e4c368ccd9da7`（7,118,848 B） |
| 惰性版 模式 2／0 | `c796bc12…6e37`／`811c0788…675c` |
| 啟用版 模式 2／0 | `240ab04d…4121`／`bdba6fb0…16d3`（7,393,280 B，SizeOfImage 0x726000） |
| delta.bin 模式 2／0 | `6dd23ce1…6490`／`023f6e15…2dd1`（274,780 B） |
| delta.json 模式 2／0 | `2b84a4d5…390d`／`de9d284e…e556` |
| catalog blob（lab_preview v4，6148 列） | `bbe4974f321ca128e4479e774b84da9080de7b4fa351d1f7c3ecc2e6223d1502` |
| MSVC 物件 NamePair／ListInsert／NameTextOut | `bf33cfc6…92e6`／`cb74d585…2b35`／`76d0adb7…c0f6` |
| hook stub | `d70b10c7a53e1d6ed4a77e4a3a10cf9bd4220f00283a26c1359c768bc0f6b522` |

啟用版與惰性版只差 45 個核准位置（hook 區段 40 B、18 個清單點 rel32、25 個 pair5、1 個 tail8；窗共 245 B，其中 228 B 不同）與 PE CheckSum（offset 328）。

## 判定規則

| 判定 | 條件 | 處置 |
|---|---|---|
| `ok` | 結束碼 0，且無 Ld95 相關錯誤事件、無新 dump | 繼續 |
| `soft-warn-exit1`（軟警告） | 結束碼 1（此遊戲從選單結束的常見值），且無錯誤事件、無新 dump、無新 WER 報告 | 繼續；觀察表寫明是否從選單結束 |
| `hard-stop`（硬停止） | 其他任何情況（崩潰、錯誤事件、dump、WER、其他結束碼） | 停；只跑 G、Z；不重試、不換方法 |

另外（不影響自動判定，但人工判讀）：

- 載入檢查（ReadProcessMemory）失敗或錯誤 5：只記錄，不影響判定（m061 已知現象）。
- 載入檢查成功但 SizeOfImage 不是 0x726000、新匯入未綁定、或 45 個位置記憶體≠檔案：視為**需調查**（黃字），回報後由 Mona 判斷。
- 觀察表出現「錯誤框」「選取後買錯／價格不符」：即使結束碼 1，也視為**功能失敗**（人工 hard-fail）。

## 證據 zip（`m063d-v4-enable-mode2-evidence.zip`）內容

- `hashes-before.json`、`hashes-after.json`：原安裝 manifest（略過 Usr\ 與 LUNAS*）、m045、各 EXE hash。
- `state.json`：已完成步驟、停止原因。
- `launch-L1.json`、`launch-L2.json`（＋`launch-*-events.txt` 若有事件）：結束碼、判定、事件數、dump／WER 名稱、載入檢查。
- `enable-E.json`：換版紀錄。
- `observations.md`：使用者填寫的觀察表。
- `screens\*.png`：截圖（檔名見 USER-STEPS 第 7 節）。
- `evidence-list.json`：上述每個檔案的大小與 hash。
- **不含**：EXE、存檔本體（`.LDP`）、dump 本體、遊戲素材。

## 回傳後 Linux 端會做

1. 驗 zip 內 hash 與本計畫一致；判讀 L1／L2 判定與載入檢查。
2. 依觀察表決定：commission 3 點（`0x492431`／`0x4b1153`／`0x4b3477`）要不要從 `unclassified_list` 改成 `name`；非 CP950 7 字；Kris／戟斧／男名結果是否關閉阻礙 #1、#2、#4。
3. 更新 STATUS／ROADMAP。即使全部通過，也只代表「lab_preview v4 啟用版在副本可用」；`production_can_apply` 仍為 false，正式套用需另行決定與另一個交接包。
