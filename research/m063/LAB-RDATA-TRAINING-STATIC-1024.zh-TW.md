# Lab-only：訓練所 Static 1024 `.rdata` 原位替換（draft7）

> 狀態：**DRAFT / lab_preview only / 未接線**。`production_can_apply=false`、`release_approved=false`、`rendering_verified=false`。不得用於正式補丁或發佈。

- 譯文來源：`research/translations/m063-draft7-training-static-1024.zh-TW.json`（Mona 已核可 draft7，5 列）
- 草稿 profile（不接線）：`research/m063/lab-rdata-training-static-1024.DRAFT.json`
- 背景：`research/m063/TRAINING-STATIC-1024.zh-TW.md`
- 來源 EXE pin（pristine Ld95.exe）sha256：`6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2`

## 條目

| offset | src_len | zh-TW | cp950_len | NUL pad | cp950 hex |
|---|---|---|---|---|---|
| 0x165b74 (1465204) | 24 | 已達能力上限 | 12 | 12 | `a477b946afe0a44fa457adad` |
| 0x165b90 (1465232) | 22 | 仍需更多經驗 | 12 | 10 | `a4b4bbdda7f3a668b867c5e7` |
| 0x165ba8 (1465256) | 24 | 可透過訓練提升能力 | 18 | 6 | `a569b37ab94cb056bd6db4a3a4c9afe0a44f` |
| 0x165bc4 (1465284) | 14 | 要訓練嗎？ | 10 | 4 | `ad6eb056bd6db6dca148` |
| 0x165bd4 (1465300) | 30 | 訓練約需兩週。 | 14 | 16 | `b056bd6dacf9bbdda8e2b667a143` |

## 原位替換流程（lab 僅限）

1. **只在可丟棄複本上操作**：複製 pristine `Ld95.exe` 到 disposable run 目錄；絕不改原檔、不提交 EXE／存檔／截圖／zip／.bin。
2. **整檔 pin**：複本 sha256 必須等於上方 pin，否則中止。
3. **逐槽核對**：對每列計算 `sha256(exe[offset : offset+source_bytes_len])`，須等於譯文檔 `source_name_sha256`。任一不符 → **soft-warn，整個 profile 跳過**（不做部分寫入）。
4. **寫入**：`cp950 bytes + 0x00 × pad`，總長恰為 `source_bytes_len`；不越界、不動相鄰字串、不改指標。
5. **事後核對**：重讀每槽，確認位元組與 profile 一致；記錄輸出 sha256 於 run 目錄（不提交二進位）。
6. 結果僅標 `lab_preview`；不得進 controller 正式路徑或 release。

## 風險

- **執行期 ANSI code page**：字串以 ANSI API（`SetWindowTextA`／`TextOutA` 等）顯示時依系統 ANSI CP 解碼。zh-TW Windows（CP950）一般可正確顯示 Big5；若在日文 locale（CP932）或經 Locale Emulator 以 932 執行，將顯示亂碼。需確認 lab 機的 ANSI CP。
- 若同一 run 另疊 m063 v4 hook／TextOut 轉換層，可能對已是 cp950 的位元組再轉碼 → 亂碼；建議先單獨套此 profile 測。
- 字串可能被他處以長度或比較引用（未發現，但未證明）；縮短後 NUL 提前結束可能影響依長度的邏輯。
- Static 控制項寬度／字型若依日文設計，可能截斷或換行異常（`rendering_verified=false`）。
- offset 僅對 pinned EXE 有效；其他版本必須重新定位。

## Rona 下一步（lab apply 之後）

1. 用修好的 harness（`sheet_tab` 用 0x465）在 disposable 複本套此 profile，記錄 pre/post sha256。
2. 擷取訓練所 3 種狀態：**已達上限**、**經驗不足**、**可訓練**。
3. 擷取 **確認對話「要訓練嗎？」** 與 **所需時間「訓練約需兩週。」**。
4. 回報 run 路徑、locale／ANSI CP、是否亂碼或截斷；不提交截圖，只交路徑。
5. 結果經 Mona 審後才能討論是否接線；在此之前本 profile 保持 NOT WIRED。
