# m063 draft49：執行期 ANSI 商店／道具 UI 候選目錄

- 目錄 JSON：`research/translations/m063-draft49-runtime-ansi-shop-item-ui.zh-TW.json`
- 來源 public_copy sha256：`5c6bfcf176c9a5fae28020458a59b67f47b3a5d9e3f316a111e40b878276c2da`
- 提交檔 sha256：`c5bfa18efa42af1b0bcaa6802d904ea85f623aa42bd795550b8d0628412708a5`

## 內容（19 列）
彩券購買提示、休養費用不足（`0x13c3cc`）、道具丟棄／使用／條件與 HP／MP 不足、魔法使用條件、店主、房屋建造／未持有、掉落（`%s`）。純 ANSI，不含 UTF-16。

## 檢查
- 已驗證無假名；text_zh_tw 保留 `%s`。
- review_status = `mona_approved_candidate_pending_site`
- stripped_fields：source_name_ja、source_name_cp932_hex（項目內無 ja／cp932 資料）

## 註記
- 無宿泊補包：宿泊天數句已在 draft10 `0x168dd4`（未配線）。
- `0x13c3cc` 為休養費用確認句，與 draft47 `0x13c3f0`（休養天數範圍）不同。

## 為何是候選
site_binding 未確認：mona_approved_candidate true；site_binding_confirmed false。**未配線**（不進 apply／profile）。

## 旗標
production_can_apply／release_approved／rendering_verified 皆為 false。
