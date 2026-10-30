# m063 計畫：冒險者名 TextOut helper（`LD2_NameTextOut`）與改寫點（Linux 設計＋靜態，研究用）

最後更新：2026-10-29 11:50（台北）。`production_can_apply=false`、`release_approved=false` 不變。

- 靜態資料：`name_draw_sites.py` → `name_draw_sites.summary.json`。內容只有 VA、座標立即值、數量、分類標籤、程式碼 sha256 前 8 碼。
- helper 草稿：`native-m063/name_textout_v3.{h,cpp}`。i386 mock：`native-m063/name_textout_mock_v3.cpp`。測試：`test_name_draw_sites.py`。
- 原版 sha256 `6c817a09…d5d2`。

## 1. 結論

- **NamePair v3 不夠用。** 它只能用在道具說明的兩個點，原因有三：
  - 座標寫死在 (57,21)/(56,21)；
  - 用 stored_id 查表；
  - 旗標是 0，不查女名的 `full_any`，也不做男名拼接。
- 名字的 TextOut 點座標各不相同，而且不帶 id。所以**需要一個新的通用 helper**，查表方式和 ListInsertV3 相同：`id=-1`，旗標 `ALLOW_ANY|ALLOW_JOIN`。
- 整串都是名字、可以直接查表的 TextOut 點共 **26 個**，分在 5 個函式。
  - 其中 **25 個**可以用 5 bytes 的「vtable 讀取對」改寫，不必搬動程式碼。
  - 剩下 1 個（`0x48f484`）要改寫 8 bytes 的尾段。
- 清單：除了酒館之外，還有 **10 個整名清單點**沒有被 m061b 改寫，其中 8 個是 `LB_INSERTSTRING`、2 個是 `CB_INSERTSTRING`。這些點直接加進 ListInsertV3 的改寫清單即可，**不需要新的 helper**。
- 以下三類延後處理：
  - 複合字串：4 個 TextOut 點和 4 個清單點；
  - 靜態文字和視窗標題：3＋2 個點；
  - 句子裡的名字。

## 2. 顯示點（流程敏感的 CString 追蹤）

分類標籤的意思：

- `name`／`bare`／`appended`：整串就是一個名字。
- `composite`：名字和別的文字接在一起。

| 函式 | 呼叫點 | 座標 | 類別 | 安裝方式 |
|---|---|---|---|---|
| `0x438910` 隊伍面板（6 格，每格畫 3 次做陰影） | `0x438a1c` `0x438a4b` `0x438a61` `0x438ae7` `0x438b16` `0x438b2c` `0x438bb2` `0x438be1` `0x438bf7` `0x438c80` `0x438cb2` `0x438ccb` `0x438d4f` `0x438d81` `0x438d9a` `0x438e1e` `0x438e50` `0x438e69` | x∈{10,11,12,282,283,284}，y∈{232,233,262,263,292,293} | name ×18 | pair5 ×18 |
| `0x4b92d0` | `0x4b9580` `0x4b9597` | (13,9)/(12,9) | name ×2 | pair5 ×2 |
| `0x48f220`（座標表 `0x55a008`；先建空 CString，再 Append(name)） | `0x48f464` `0x48f484` | 查表取得，陰影 +1 | bare ×2（人工確認） | pair5 ×1、tail8 ×1 |
| `0x4d77a0`／`0x4dbcb0` 頁尾（預設建構 `0x405490`；index≠-1 時 Append(name)，否則 Append(占位字 `0x52f80c`)） | `0x4d9729` `0x4d98e1`／`0x4ddcd9` `0x4dde91` | (13,235)/(12,235) | bare ×4（人工確認） | pair5 ×4 |
| `0x4d77a0`／`0x4dbcb0` 標題 | `0x4d79dd` `0x4d79f0`／`0x4dbefc` `0x4dbf0f` | (13,9)/(12,9) | composite ×4：`0x44dab0`（角色+0x19 的字串）＋1 個空白＋名字 | 延後 |
| 清單，未改寫，整名 | `0x4735f6` `0x474ead` `0x47502c` `0x475bbe` `0x47c242` `0x481d42` `0x497a20` `0x4cb4b2`（訊息 0x181）、`0x46e73a` `0x47db6a`（訊息 0x14a） | — | name／bare ×10 | ListInsertV3 加改寫點 |
| 清單，已改寫 | `0x4b2d1f` 酒館 | — | bare | m061b 已涵蓋 |
| 清單，複合 | `0x457985` `0x4582f6` `0x459005` `0x4595a5`（「2 個 ASCII 空白＋名字」再經 `wsprintfA "%s"`） | — | composite ×4 | 延後（見 §6） |
| SetDlgItemText | `0x460680` `0x470200` `0x470410` | — | bare ×3 | 延後 |
| SetWindowText | `0x4d737a` `0x4db87d` | — | name ×2 | 延後 |

補充說明：

- 修正舊追蹤：舊的「`0x4dc720`」其實是 `0x4dbcb0` 的後半段，舊的函式邊界啟發式切錯了。
- 舊追蹤只要和 GetName 在同一個函式就列為「清單點」。這次的資料流沒有追到下列各點送的是名字：`0x460730`、`0x4702b0`、`0x4704c0`、`0x4750bb`、`0x49793d`、`0x4abaf6`、`0x4abb11`、`0x4abcab`、`0x4b71c2`…`0x4b72e9`（6 點），以及標題 `0x4d73c1`／`0x4db8c5`（立即值字串）。可能是送別的字串，也可能是追蹤追不到。要擴充時再逐點人工確認。
- 80 個呼叫 GetName 的函式裡，有 25 個在同一函式內就有名字輸出點；其餘的把名字回傳、存起來或組進句子。

## 3. helper ABI（`@LD2_NameTextOut@24`）

```
int __fastcall LD2_NameTextOut(LD2Cdc* cdc /*ECX*/, int unused /*EDX*/, int x, int y, const char* s, int n); // ret 16
```

- 進入時的堆疊與 `CDC::TextOut`（`0x4e13d7`，thiscall，`ret 0x10`）完全相同：ECX 是 CDC，堆疊上是 x、y、s、n。
- EDX 放的是 helper 自己的位址，helper 忽略它。
- 處理流程：
  1. 從**當下的** vtable 讀 `+0x5c`。只有在它等於 `LD2_ExpectedTextOutA`、而且 1≤n≤64 時，才去查表。
  2. 查表條件：`LD2C3_Lookup(id=-1, ALLOW_ANY|ALLOW_JOIN)`，結果要通過 UTF-16 檢查（沒有控制字元、沒有孤立代理），才用 `TextOutW(cdc->m_hDC=[cdc+4], x, y, …)`。
  3. 其餘情況一律呼叫原本的虛擬函式，參數原封不動，並回傳它的回傳值。
- 例外：helper 不 catch，例外照原樣往外傳。
- 函式名刻意和 NamePair v3 不同（`LD2N_FindCopy`、`LD2N_Wipe`），兩個物件可以並排合併。綁定仍是同樣三個：`LD2_Catalog`／`LD2_CatalogBytes`、`LD2_ExpectedTextOutA`、`LD2_TextOutW`，新匯入是 0。
- 已知限制：`id=-1` 也會命中 `full_id` 道具列，只要該譯文在各 id 之間唯一。這和 ListInsertV3 相同。如果名字和道具名同形，就會顯示道具譯名。

## 4. 改寫方式

**pair5（25 點）**

- 把 `mov R1,[cdc]; mov R2,[R1+0x5c]`（2＋3＝5 bytes）換成 `mov R2, imm32(helper VA)`（5 bytes）。後面原本的 `mov ecx,cdc; call R2` 和 4 個 push 都不動。
- `name_draw_sites.py` 對每一點檢查四件事：
  - 兩條指令相鄰；
  - R1 是 eax／ecx／edx，而且到 call 之前沒有再被讀；
  - (pair, call] 之間沒有分支目標；
  - 25 個 pair 位址互不重複。
- 每一點都記錄了原 5 bytes 的 sha256 前 8 碼，給之後的 enable_plan 鎖定用。
- 需要的前提是 helper 的 VA 固定，也就是合併在 EXE 新區段內，與 m061 的 rel32 改寫相同。

**tail8（`0x48f484`）**

- 原本是 `mov edx,[eax+0x5c]; push ecx; mov ecx,esi; call edx`，共 8 bytes，改成 `push ecx; mov ecx,esi; call rel32 helper`，也是 8 bytes。
- 分支目標檢查是 0。EAX／EDX 在 call 之後本來就會被覆寫。
- 這一點要在 enable_plan 裡單獨列為例外。

**不改的部分**

- 不改全域的 `CDC::TextOut`：MFC 的 vtable 和 `0x4e13d7` 都不動。原因是同一個 vtable 也畫非名字的文字，例如隊伍面板 x=0xe6..0xe8 的另一串字。
- 只改名單上的點，其他 TextOut 呼叫者完全不受影響。

## 5. 還需要 Win11 證據的項目（現在**不**準備交接）

1. **MSVC 編譯＋COFF 稽核一次**：比照 m062 的 `HANDOFF-COMPILE-M062`，目標是 `/O2 /GS /EHs /Zl`、唯一公開符號 `@LD2_NameTextOut@24`、正常路徑 `ret 16`。
   - Linux 上的 zig/clang 物件只是預演，不能當成最終依據。
   - 建議和下一輪 ListInsertV3 改寫點擴充一起打包，只跑一次 Win11。
2. **實機觀察一次**：確認隊伍面板（6 格 × 3 次陰影）用 TextOutW 時的字型和寬度。名字變長之後，可能和 x=0xe6 那一欄重疊。這一項需要啟用版 EXE 和可丟棄副本，要等 catalog 有已審核的名字才有意義。
3. 例外和 unwind：和 m061／m062 一樣，目前只有設計推論。

## 6. 延後項目與建議

- 複合清單（4 點）的前綴固定是 2 個 ASCII 空白。最便宜的做法：ListInsertV3 的下一版在每段查表前，先把開頭的 ASCII 空白原樣保留，再查剩下的部分。這要改 helper，也就需要重新編譯，可以和 §5-1 合併。
- 複合標題（4 點）的前段是另一個角色字串（`角色+0x19`），可能也需要翻譯。這要「最後一個空白之後是名字」的拆分規則，再加上前段的 catalog，**先不做**。
- SetDlgItemText／SetWindowText（5 點）都是 ANSI 視窗。W 文字送進去會被轉成系統 ANSI 碼頁，和 m061 run1 的 `?` 問題相同，需要另外設計，例如沿用 m061b 的切換模式。
- 句子裡的名字（約 55 個函式）：整串查表一定查不到，需要子字串替換或改資料層。

## 7. 建議的下一個里程碑

1. ~~**m063a（Linux）**~~ **已完成（2026-10-29 台北，Linux 靜態，以 clang 預演物件驗證）**，見 `research/m063/RESULT-M063A.zh-TW.md`。原文：在 `merge_plan_v3` 加第三個物件槽，在 enable_plan 加 25 個 pair5、1 個 tail8，以及 10 個清單點改寫。用合成物件做靜態驗證，項目包括 ESP、分支、checksum 和 sha 前碼。
2. **m063c（Linux）已完成核心**：catalog v4（地區標籤＋NAME_ONLY）解 Kris／戟斧／跨地區假切分，見 `research/m063/DESIGN-M063C-CATALOG-V4.zh-TW.md`；helper 原始碼改用 v4 尚未做。
3. **m063b（Win11，一次）**：編譯 `name_textout_v3.cpp`；如果要做空白前綴，就同時編譯 ListInsertV3 的下一版。
4. 等 Mina 名字草稿有一批 `human_reviewed` 之後，再準備一次可丟棄副本的觀察。
