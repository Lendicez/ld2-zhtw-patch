# m063 draft59：執行期 ANSI 家人訣別候選目錄

- 目錄 JSON：`research/translations/m063-draft59-runtime-ansi-family-farewell.zh-TW.json`
- 來源 public_copy sha256：`a17349237a4197bd04dfbee67ea7fd9e13ff24140f08a9432bbb2291d78b94cb`
- 提交檔 sha256：`72fb028e57a87b5459bb2f37750a0e99c065798643522212ad72bebb5772d4e0`

## 內容（19 列）
家人捨身相護而亡時的訣別（farewell_parent 9／farewell_child 10）。無 printf。純 ANSI，不含 UTF-16。

## 檢查
- 已驗證無假名；無 printf；CP950 可編碼且不超出容量。
- review_status = `mona_approved_candidate_pending_site`
- stripped_fields：source_name_ja、source_name_cp932_hex
- 省略號使用「……」，未使用半形「･･･」。

## 註記
- 無宿泊補包；UTF-16 未開啟；無道具／訓練所 Static。

## 為何是候選
site_binding 未確認：mona_approved_candidate true；site_binding_confirmed false。**未配線**（不進 apply／profile）。

## 旗標
production_can_apply／release_approved／rendering_verified 皆為 false。
