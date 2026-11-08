# m063 draft48：執行期 ANSI 年齡／隊伍 UI 候選目錄

- 目錄 JSON：`research/translations/m063-draft48-runtime-ansi-age-party-ui.zh-TW.json`
- 來源 public_copy sha256：`14c898720bab93614da7036b71e65b104f000c1b6ce86cf53403e2221917bcbf`
- 提交檔 sha256：`14d1208dfa78723daf3b7c4c34411a02a18c5cdbff0cbca06ef2a560f351b6fe`

## 內容（19 列）
年齡／生日／壽命（%s/%d）、GOLD／掉落／偷竊（%d/%s）、能力上升／傷害／吸魔（%d）、祭壇放置（%s）、未滿 16 歲入隊鎖、結婚入隊詢問（%s）、魅了戰鬥片段、親情歡迎回家。純 ANSI，不含 UTF-16。

## 檢查
- 已驗證無假名；text_zh_tw 保留 `%s`／`%d`。
- review_status = `mona_approved_candidate_pending_site`
- stripped_fields：source_name_ja、source_name_cp932_hex（項目內無 ja／cp932 資料）

## 為何是候選
site_binding 未確認：mona_approved_candidate true；site_binding_confirmed false。**未配線**（不進 apply／profile）。

## 旗標
production_can_apply／release_approved／rendering_verified 皆為 false。
