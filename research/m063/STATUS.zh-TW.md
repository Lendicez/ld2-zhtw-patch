# m062／m063 狀態與等待項目（Linux 端）

最後更新：2026-10-29（台北）。分支 `research/m062-catalog-capacity`（PR #26，Draft，不合併）。`production_can_apply=false`、`release_approved=false`。

## 已完成（Linux）
- m063a：NameTextOut 第三物件槽、25 pair5＋1 tail8＋18 清單點改寫計畫、靜態驗證（`RESULT-M063A.zh-TW.md`）。
- 男女同 bytes 名定稿「薩拉」（3 列 user_decided）與 lab_preview 靜態重建。
- **Mina draft5-kris-24 收進 #26（2026-10-29，使用者經 Mina 定稿）**：Kris 短劍 extended 28 定稿「**波刃短劍**」（新增 1 列 user_decided，公開 JSON 1817 列）；24 筆標籤／說明不一致（primary 272–295）**名字＋說明都收**，`review_status=user_decided_include_name_and_description`（不等實機）。lab_preview 重建：v3 子集 1816 列（只排除 Kris，因 v3 人名點分不開），v3 blob `668143b7…678e`（6127 列，253,484 B）；v4 完整稿 6148 列 `bbe4974f…1502`，Kris 女名 600/600。mock 的 Kris 道具文字改為「波刃短劍」。
- **m063c**：catalog v4（地區標籤＋NAME_ONLY）模型、C 核心、主機交叉測試、lab 數量摘要（`DESIGN-M063C-CATALOG-V4.zh-TW.md`）。在模型與 C 核心層面解掉 Kris、戟斧 2 組、跨地區假切分 5 組；男名 40,000 組全對。
- **m063c native v4**（DESIGN §7 1–4）：ListInsert v4 兩入口（item／name）、NameTextOut v4（NAME_ONLY）、NamePair v4（旗標 0）、`merge_plan_v4`／`enable_plan_v4`（7 item＋11 name 清單點分流）、兩入口 COFF 稽核、Linux 預演與 mock 全過；lab 鏡像上 v4 inert＋enabled 影像靜態建置通過（只在記憶體，沒寫 EXE）。三個 v4 物件 pin 仍為 `None`。

## 阻礙一覽
| # | 阻礙 | 現況 | 下一步 | 誰 |
|---|---|---|---|---|
| 1 | Kris 短劍 vs 女名 | v4 核心＋native helper＋合併／啟用計畫已解（Linux，mock／預演） | m063b MSVC 編譯後實機確認 | 使用者（Win11，需同意） |
| 1a | ~~Kris 短劍的譯名~~ | **已定稿「波刃短劍」**（draft5，user_decided）；公開 JSON 與 v4 lab 已收；v3 lab_preview 仍排除（v3 人名點會把女名顯示成短劍） | 無（等 #1 的 v4 實機） | — |
| 2 | 男名 7 組（5 假切分＋2 戟斧） | v4 核心＋helper 已解，lab 40,000/40,000 | 同 #1 | 使用者（Win11，需同意） |
| 3 | ~~24 筆 label/desc mismatch（primary 272–295）~~ | **已決定名字＋說明都收**（draft5，`user_decided_include_name_and_description`）；已進 lab_preview（v3 +264 列） | 實機只剩「顯示是否合理」的觀察，不再擋收錄 | — |
| 4 | 非 CP950 7 字（8 筆） | v3／v4 都輸出 UTF-16，理論可顯示 | 只能實機確認（同一次觀察即可） | 使用者（Win11，需同意） |
| 5 | 沒有任何列是 `human_reviewed` | reviewed catalog 只有 m051 24 項 | 使用者或遊戲內確認後才升級 | 使用者／Mina |
| 6 | m063b MSVC 編譯 | 未打包（Linux 前置已全部完成） | 使用者同意後才打包：一次編 NameTextOut v4＋ListInsert v4＋NamePair v4，回傳物件以 `rehearse_v4_objs.py` 完整稽核再填 pin | 使用者（需同意） |

## 目前不需要使用者操作
Linux 端 DESIGN §7 的 1–4 已完成。接下來全部是等待項：
- **使用者（需同意）**：是否進行 m063b（Win11 MSVC 一次編譯三個 v4 物件）。未同意前不打包任何 Win11 交接。
- **Win11 實機觀察（m063b 之後）**：Kris／戟斧／跨地區男名在清單與 TextOut 的實際顯示；commission 3 點清單內容（決定 `unclassified_list` 要不要改 name）；非 CP950 7 字；24 筆 label/desc mismatch（已收）實際出現在哪個畫面、譯名是否合理；Kris「波刃短劍」在商店／道具畫面、「克莉絲」在人名點。
- **Mina**：見下。

## 需要 Mina 的項目（由 Mona 轉達）
- 目前沒有。2026-10-29 的兩項（Kris 譯名、24 筆處理方式）已由 draft5-kris-24 收進 #26。
- 附註（不擋）：Kris 說明的「く」字形，公開檔改成注音「ㄑ」（字形相同、CP950 可編碼，比照 extended 63「ト→卜」）；若 Mina 想改寫成「彎折狀」等說法，下一版草稿再換。
