# 訓練所 Static id=1024 亂碼調查（m063d）

> 旗標維持：`production_can_apply=false`、`release_approved=false`。

## 已知
- m063d 啟用（lab_preview Mode 2）後，訓練所（筋力／知性／敏捷／魅力頁）Static id=1024 狀態列顯示 cp932 亂碼（`observations.md`、`autotest-load-inn-tavern-quest-004-report.md` 步驟 61–63）。
- 對話框模板：resource 147（知性）、148（筋力）、149（敏捷）、158（魅力），控制項 id 1024，模板文字「もっと、修行が必要です」。
- **模板已譯**：m041 `patches/m041/review.json` 譯為「仍需繼續修練」，狀態 `static_pass_runtime_unseen`，註明「dynamic overwrites unverified」。
- 因此 runtime 看到的亂碼不是模板，而是程式碼以 **ANSI(cp932) 字串動態覆寫**該 Static，在繁中（cp950）環境下解碼成亂碼。

## 候選日文來源（Ld95.exe `.rdata`，cp932，m001 catalog 有收錄）
| id | 原文 | 保守容量(bytes) | 試譯（待 Mina 定稿） |
|---|---|---|---|
| ansi:0x165b74 | 既に、限界に達しています | 24 | 已達能力上限 |
| ansi:0x165b90 | もっと、経験が必要です | 22 | 仍需更多經驗 |
| ansi:0x165ba8 | 訓練して能力を伸ばせます | 24 | 可透過訓練提升能力 |
| ansi:0x165bc4 | 訓練しますか？ | — | 要訓練嗎？ |
| ansi:0x165bd4 | 訓練には２週間ほどかかります。 | — | 訓練約需兩週。 |

前三者位於同一區塊、緊鄰 `CShopBuyPage` 類別名稱前，幾乎確定是 1024 的三種狀態（上限／經驗不足／可訓練）。截圖中具體是哪一句需以 PNG 或 dump 原始 bytes 對照（本機文字證據未含 1024 原始 bytes）。

## 是否已在 catalog
- 模板：是（m041「仍需繼續修練」）。
- 動態 `.rdata` 字串：只在 m001 抽取 catalog 與 Mina `_local/exe-strings.txt` 清單中出現；**任何翻譯 catalog／v4 lab_preview 均未收錄**。

## 建議下一步
1. 將上列 5 筆納入「動態 CP932 字串清單」批次（與 #24 inventory 同一軌），由 **Mina 起草**譯文，cp950 位元組數不得超過原容量。
2. 由 Mona 加入 resource/ANSI profile（`.rdata` 原位替換，邊界僅限原 payload），在 lab 副本驗證。
3. Rona 自動測：訓練所三種狀態（可訓練／經驗不足／上限）各截一張確認。
4. 不改旗標，不 merge。
