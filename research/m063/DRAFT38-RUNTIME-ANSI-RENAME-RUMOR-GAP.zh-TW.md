# m063 draft38：runtime ANSI 改名／傳聞缺口（Rona 缺口小包，候選 catalog）

- 檔案：`research/translations/m063-draft38-runtime-ansi-rename-rumor-gap.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `35a58d39b10b7fb17cff4a872d292a7f46d992b9faf0a6febf11d94cb974e85b`
- 本檔 sha256：`f1125d4bf01e8e7fb7c6964245aa62e44bbd18697410defc8bfc3c85a06b6d6e`
- 12 列：名稱／稱號／世界名輸入、家名顯示、「鎮上傳聞-」、惡魔傳聞3、隊列提示、彩券／武鬥規則殘件
- 針對 Rona wm2 缺口（32880 隊伍名、聽傳聞 1013）；**本包只含 ANSI（CP932→CP950）**。
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 延後：UTF-16 對話框
選單 32880 標題／欄位與「噂を聞く」按鈕屬 UTF-16 對話框資源（線索約 `0x6b6d8a`／`0x6b3968`），未含於本包；待溯源後再決定是否另開 UTF-16 包。

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）；頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。**

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
