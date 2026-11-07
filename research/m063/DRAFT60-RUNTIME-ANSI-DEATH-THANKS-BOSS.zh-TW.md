# m063 draft60：執行期 ANSI 死亡呼喊／感謝／頭目候選目錄

- 目錄 JSON：`research/translations/m063-draft60-runtime-ansi-death-thanks-boss.zh-TW.json`
- 來源 public_copy sha256：`1456bd1e1f2bcc2b7e452951f3fa09aeae640e9a555a267cfef15cbeff776759`
- 提交檔 sha256：`225e887adf41a129c65aba78655f5ed89d3d9863a775267ca2209ee89ca86d09`

## 內容（19 列）
death_cry 8／family_thanks 7／combat_thanks 1／boss_defeat 2／boss_intro 1（塞姆伊；前導空白保留）。純 ANSI，不含 UTF-16。

## 檢查
- 已驗證無假名；CP950 可編碼且不超出容量。
- review_status = `mona_approved_candidate_pending_site`
- stripped_fields：source_name_ja、source_name_cp932_hex
- 省略號使用「……」，未使用半形「･･･」。
- boss_intro（0x125e48）前導空白保留；「塞姆伊」在列。

## 註記
- 無宿泊補包；UTF-16 未開啟；無道具／訓練所 Static。
- 「塞姆伊」暫譯可接受。

## 為何是候選
site_binding 未確認：mona_approved_candidate true；site_binding_confirmed false。**未配線**（不進 apply／profile）。

## 旗標
production_can_apply／release_approved／rendering_verified 皆為 false。
