# m063 draft64：執行期 ANSI 庇護／感謝／狀態異常／誤傷候選目錄

- 目錄 JSON：`research/translations/m063-draft64-runtime-ansi-protect-thanks-status-ff.zh-TW.json`
- 來源 public_copy sha256：`fc52c1aa81548618995ba0009f50a08c89bd223ad54e6009d86b4e6bbdd6c947`
- 提交檔 sha256：`478f9881caa5ab3e707ff68cc7d9c6026271dba9c688fd19e92edf552d7ca2cc`

## 內容（19 列）
protect 4／thanks 5／death_cry 3／status_shout 3／friendly_fire 2／enemy_dying 2。無人名。純 ANSI，不含 UTF-16。

## 檢查
- 已驗證無假名；CP950 可編碼且不超出容量。
- review_status = `mona_approved_candidate_pending_site`
- stripped_fields：source_name_ja、source_name_cp932_hex
- 省略號使用「……」，未使用半形「･･･」。
- 與既有 draft 目錄無 file_offset 重疊。

## 註記
- 無宿泊補包；UTF-16 未開啟；無道具／訓練所 Static。

## 為何是候選
site_binding 未確認：mona_approved_candidate true；site_binding_confirmed false。**未配線**（不進 apply／profile）。

## 旗標
production_can_apply／release_approved／rendering_verified 皆為 false。
