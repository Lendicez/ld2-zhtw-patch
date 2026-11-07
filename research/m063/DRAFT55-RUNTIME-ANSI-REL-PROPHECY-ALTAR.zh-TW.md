# m063 draft55：執行期 ANSI 親屬／預言／祭壇候選目錄

- 目錄 JSON：`research/translations/m063-draft55-runtime-ansi-rel-prophecy-altar.zh-TW.json`
- 來源 public_copy sha256：`a2913325b7d9f1c0235aa9a91d84234b69c0e4fdfc32e005f5f93c650dc6a1b7`
- 提交檔 sha256：`4a2e92831a8aad9da865f47c6a7143284ee8cbe8e1bccf966501624d17a3400c`

## 內容（19 列）
月／年格式（`%2d`／`%4d`）、親屬標籤（同伴／子女／妻／夫－`%s`）、樓層（`%d`）、預言續（`%s`；アツユ暫譯「阿津優」）、國王資格後綴、祭壇檢視／放劍發光。純 ANSI，不含 UTF-16。

## 檢查
- 已驗證無假名；保留 `%2d`／`%4d`／`%d`／`%s`。
- review_status = `mona_approved_candidate_pending_site`
- stripped_fields：source_name_ja、source_name_cp932_hex（項目內無 ja／cp932 資料）

## 註記
- 無宿泊補包：宿泊天數句已在 draft10 `0x168dd4`（未配線）。
- 「阿津優」為暫譯，候選可接受，之後可再潤飾。

## 為何是候選
site_binding 未確認：mona_approved_candidate true；site_binding_confirmed false。**未配線**（不進 apply／profile）。

## 旗標
production_can_apply／release_approved／rendering_verified 皆為 false。
