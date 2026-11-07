# m063 draft57：執行期 ANSI 預言／祭壇／地點候選目錄

- 目錄 JSON：`research/translations/m063-draft57-runtime-ansi-prophecy-altar-place.zh-TW.json`
- 來源 public_copy sha256：`84c36d68615536b279eca5486cffbc10315554230885c5ffd0a426b5c7e2ba58`
- 提交檔 sha256：`63a3c4e92e25fed8d2a673b96eeb305950eb8f5c7331b806799b66359ab94b27`

## 內容（19 列）
預言短 stub（`%s`／`%A`）、按鈕祭壇／銘板、亡靈老人／聲、神挑戰警告、地點標籤（前導空白：廣場／自宅／寺院／旅館）。純 ANSI，不含 UTF-16。

## 檢查
- 已驗證無假名；保留 `%s`／`%A`；地點標籤前導空白保留。
- review_status = `mona_approved_candidate_pending_site`
- stripped_fields：source_name_ja、source_name_cp932_hex（項目內無 ja／cp932 資料）

## 註記
- 無宿泊補包：宿泊天數句已在 draft10 `0x168dd4`（未配線）。
- UTF-16 未開啟。

## 為何是候選
site_binding 未確認：mona_approved_candidate true；site_binding_confirmed false。**未配線**（不進 apply／profile）。

## 旗標
production_can_apply／release_approved／rendering_verified 皆為 false。
