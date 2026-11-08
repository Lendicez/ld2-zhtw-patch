# m063 draft51：執行期 ANSI 確認框／系統 UI 候選目錄

- 目錄 JSON：`research/translations/m063-draft51-runtime-ansi-confirm-sys-ui.zh-TW.json`
- 來源 public_copy sha256：`6689c9ee3c8e4639d0aaab2a40f6c16e84437ade98c1b5c9e8ce576c42ebb223`
- 提交檔 sha256：`73b54ccf9171677a1929e3581f66f2095c7268e294a1f09ae1542ba13ccba5c2`

## 內容（19 列）
讀檔失敗（`%s`）、世代交替詢問（`%s`）、祭壇消失（`%s`）、是／否確認框（勝負／幫忙／聽從／愛／斷親／襲擊／進入／回鎮／攀談／按鈕／國王）、休養一年、屍體拿道具、達人信物限制、退隊道謝、國王試煉一次限制。純 ANSI，不含 UTF-16。

## 檢查
- 已驗證無假名；text_zh_tw 保留 `%s`。
- review_status = `mona_approved_candidate_pending_site`
- stripped_fields：source_name_ja、source_name_cp932_hex（項目內無 ja／cp932 資料）

## 註記
- 無宿泊補包：宿泊天數句已在 draft10 `0x168dd4`（未配線）。

## 為何是候選
site_binding 未確認：mona_approved_candidate true；site_binding_confirmed false。**未配線**（不進 apply／profile）。

## 旗標
production_can_apply／release_approved／rendering_verified 皆為 false。
