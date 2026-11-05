# m063 draft50：執行期 ANSI 隊伍／格式 UI 候選目錄

- 目錄 JSON：`research/translations/m063-draft50-runtime-ansi-party-fmt-ui.zh-TW.json`
- 來源 public_copy sha256：`60d4c5adbda93e1db2bda4c8f797809ed0422060311bc46b65f9a343611db866`
- 提交檔 sha256：`1ac47e999f549e058019ffd9b5fb30c2c2b50abc88655576d7f237cd94a6aa66`

## 內容（19 列）
年齡／日數格式（`%2d`／`%d`／`%2s`）、入隊／結婚／退隊對話（含 `%s`）、生日、道場挑戰、存檔失敗／完成。純 ANSI，不含 UTF-16。

## 檢查
- 已驗證無假名；text_zh_tw 保留 `%2d`、`%d`、`%2s`、`%s`。
- review_status = `mona_approved_candidate_pending_site`
- stripped_fields：source_name_ja、source_name_cp932_hex（項目內無 ja／cp932 資料）

## 註記
- 無宿泊補包：宿泊天數句已在 draft10 `0x168dd4`（未配線）。

## 為何是候選
site_binding 未確認：mona_approved_candidate true；site_binding_confirmed false。**未配線**（不進 apply／profile）。

## 旗標
production_can_apply／release_approved／rendering_verified 皆為 false。
