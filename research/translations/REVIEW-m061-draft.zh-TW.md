# m061 翻譯草稿審查（Mina 翻譯，Mona 審查與發布）

狀態：**研究草稿**。`production_can_apply=false`、`release_approved=false`、`rendering_verified=false`、`preview_only=true`。
未併入 helper catalog，也沒有任何 EXE、delta 或遊戲資源。

## 來源與分工
- 翻譯：Mina（lab 本地產生器，以 pristine Ld95.exe 為來源，sha256 `6c817a09…40d5d2`）。
- 審查、清理、commit 與 PR：Mona。
- lab 完整草稿（含日文欄位）的 sha256 為 `477edfbaa16fb8ca74672fcec8006986fbd90f49dae7bd89fc95702454e14ec1`，各 JSON 的 `lab_full_draft_sha256` 都記錄這個值。完整草稿與產生器只留在 lab，不上傳。

## 公開檔案
| 檔案 | 筆數 |
|---|---|
| `m061-draft-consumables-tools.zh-TW.json` | 72（consumable 55、tool 17） |
| `m061-draft-adventurers-western.zh-TW.json` | 350 |
| `m061-draft-adventurers-arabic.zh-TW.json` | 350 |
| `m061-draft-adventurers-chinese.zh-TW.json` | 350 |
| `m061-draft-adventurers-japanese.zh-TW.json` | 350 |

- 每個地區各 350 筆：男名前段 100、男名後段 100、女名 150。合計 1472 筆。
- 冒險者名依地區拆成 4 檔，是因為 `audit_upload` 規定每個檔案不得超過 400000 bytes。
- 每列一筆 JSON 物件；頂層 metadata 沿用 m051。

## 清理（相對 lab 完整草稿）
- 刪除 `source_name_ja`、`source_name_cp932_hex`（依 m051 政策，公開檔不收日文原文）。
- 保留：所有 sha256、contracts、numeric literals、slot、stored_id、file_offset、slot_determination、`name_zh_tw`、`description_zh_tw`、`translation_method`、`exact_match_usable`、`name_cp950_encodable`、`review_status`。
- `review.tsv` 與 `tools/` 不公開。它們含日文原文或 lab 路徑，日文對照表也寫在程式碼裡。

## Mona 獨立驗證（對 pristine EXE 重算）
- 道具 72 筆：
  - `source_record_sha256`（216 bytes）、`source_name_sha256`、`stored_id`、`source_description_sha256` 全部吻合。
  - 與 m051 的 24 個 (table, slot) 不重疊。
- 冒險者 1400 筆：依 `file_offset` 與欄寬（男名 8、女名 13）重算 `source_name_sha256`，全部吻合。
- 所有 hash 都是 64 位 hex；沒有 TBD 或空值，也沒有重複的 slot/index。
- 一致性：
  - 1342 個不同的來源 bytes，每個只對應一個譯名。
  - `ambiguity_blocked` 全為 false。
  - `name_cp950_encodable` 與實際 CP950 編碼結果一致。
- 所有可用 CP950 編碼的譯名都不超過原欄位寬度減 1。
- 道具說明全部可以用 CP950 編碼。
- 中文名中沒有殘留假名。`々` 僅 1 筆（日本女名「奈々」，CP950 可編碼）。
- 抽查：道具譯名與說明忠於原文，數字保留不變。
  - 例：slot 30/31 原文本來就寫「玉」，所以說明譯為「寶珠」。

## 工程阻礙（之後併入 helper catalog 前必須處理）
1. **男名 `exact_match_usable=false`（800 筆）**：男名全名是在執行時於 0x44e7xx 把前段和後段串接而成，用完整 bytes 比對一定找不到。需要以下其中一種做法：
   - helper 改成前綴＋後綴兩段查表；
   - 或在串接點改用 ID 查表。

   女名 600 筆可直接比對。
2. **`encode_entries` 上限 264 列**：24×11 已經用滿。新增道具要 ×11 強化後綴，加上 1270 種名字，都會超過上限。
3. **`reviewed_catalog`** 寫死了 catalog hash 與 `len==24`，需要改成可擴充的版本化 catalog。
4. **`item_sidecar`** 只接受 weapon、armor、tool、consumable，而且每批 1–30 筆：
   - 這 72 筆道具要拆成至少 3 批；
   - 冒險者名需要新增 category，或另開 sidecar。
5. **`machine_translit_draft` 515 筆**是依音節機器音譯，需要人工校對。男名片段串接後的整體讀感也還沒確認。
6. **CP950 無法編碼的字有 7 個**（咲、宍、惣、杢、梶、榊、笹），出現在 8 個名字、8 筆資料中。它們只能走 W（Unicode）路徑，所以要等 m061b 的 Unicode list 路徑確認之後才能用。ANSI fallback 會顯示成 `?`。
7. **201 筆名字含尾端空白**（原文就以空白補齊欄寬）。比對時必須保留空白；同時要釐清 `%-12s`/`%-16s` 補齊後的字串為什麼一律算 miss（見 m061b 設計）。
8. 72 筆道具與全部冒險者名都還沒有在遊戲內確認渲染。

## 不在範圍內
- 其餘約 350 筆道具（寶物、飾品、其他武器和防具）。
- 委託畫面中其他字串表造成的 ??? 或缺字。
