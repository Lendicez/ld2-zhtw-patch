# m062／m063 狀態與等待項目（Linux 端）

最後更新：2026-10-29（台北）。分支 `research/m062-catalog-capacity`（PR #26，Draft，不合併）。`production_can_apply=false`、`release_approved=false`。

## 已完成（Linux）
- m063a：NameTextOut 第三物件槽、25 pair5＋1 tail8＋18 清單點改寫計畫、靜態驗證（`RESULT-M063A.zh-TW.md`）。
- 男女同 bytes 名定稿「薩拉」（3 列 user_decided）與 lab_preview 靜態重建。
- **m063c**：catalog v4（地區標籤＋NAME_ONLY）模型、C 核心、主機交叉測試、lab 數量摘要（`DESIGN-M063C-CATALOG-V4.zh-TW.md`）。在模型與 C 核心層面解掉 Kris、戟斧 2 組、跨地區假切分 5 組；男名 40,000 組全對。

## 阻礙一覽
| # | 阻礙 | 現況 | 下一步 | 誰 |
|---|---|---|---|---|
| 1 | Kris 短劍 vs 女名 | v4 核心已解（模型＋C） | Linux：native helper 改用 v4（DESIGN §7 1–4）；之後 Win11 編譯 | Mona（Linux）→ 使用者（Win11，需同意） |
| 1a | Kris 短劍的譯名 | REVIEW 只有建議「克力士劍」，lab 測試只當暫代文字 | 需要 Mina 確認譯名並放進下一版草稿（目前草稿沒有 extended 28） | **Mina** |
| 2 | 男名 7 組（5 假切分＋2 戟斧） | v4 核心已解，lab 40,000/40,000 | 同 #1 | Mona → 使用者 |
| 3 | 24 筆 label/desc mismatch（primary 272–295） | lab_preview 仍排除 | 二選一：(a) 實機確認這些名字是否出現在道具畫面；(b) Mina 決定只收名字、不收說明（需要 Mina 標記新狀態） | **Mina**（政策）或使用者（Win11 觀察） |
| 4 | 非 CP950 7 字（8 筆） | v3／v4 都輸出 UTF-16，理論可顯示 | 只能實機確認（同一次觀察即可） | 使用者（Win11，需同意） |
| 5 | 沒有任何列是 `human_reviewed` | reviewed catalog 只有 m051 24 項 | 使用者或遊戲內確認後才升級 | 使用者／Mina |
| 6 | m063b MSVC 編譯 | 未打包 | 等 #1 的 Linux 步驟做完，再一次編 NameTextOut＋ListInsert v4＋NamePair v4 | 使用者（需同意） |

## 目前不需要使用者操作
Linux 端下一步（不需任何人）：DESIGN §7 的 1–4（v4 native helper、合併／啟用計畫、稽核、mock 測試）。完成前不打包任何 Win11 交接。

## 需要 Mina 的項目（由 Mona 轉達）
1. Kris 短劍（extended 28）譯名確認（目前建議「克力士劍」）。
2. 24 筆 label/desc mismatch 的處理方式（只收名字，或等實機）。
