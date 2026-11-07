# m063 draft58：執行期 ANSI 戰鬥感謝／格式 stub 候選目錄

- 目錄 JSON：`research/translations/m063-draft58-runtime-ansi-fmt-combat-thanks.zh-TW.json`
- 來源 public_copy sha256：`462bb39ac7c812cb02e2f39ea64f5f66a80a470f0e735270d364482e6c07b5fd`
- 提交檔 sha256：`39a8a535cda9a4223697392f29938f979344d60226f3b85832ddb07ade25618e`

## 內容（19 列）
剩餘 printf stub（卸下重量 `%s`、通緝 `%s`、帳本表 `%-12s/%-14s/%3d/%2d`）、戰鬥感謝與盟友家人感謝（配偶／父母／子女）。純 ANSI，不含 UTF-16。

## 檢查
- 已驗證無假名；保留 printf 符記；CP950 可編碼且不超出容量。
- review_status = `mona_approved_candidate_pending_site`
- stripped_fields：source_name_ja、source_name_cp932_hex

## 註記
- 無宿泊補包；UTF-16 未開啟；無道具／訓練所 Static。

## 為何是候選
site_binding 未確認：mona_approved_candidate true；site_binding_confirmed false。**未配線**（不進 apply／profile）。

## 旗標
production_can_apply／release_approved／rendering_verified 皆為 false。
