# m042 翻譯現況

最新本機 profile m042 承接 m041；m020／m037／m038／m041 及雜湊均保留。
m040 期限版面與動態研究獨立。預設 CLI／既有打包候選仍為 m020，can_apply=false。

本輪 210 個剩餘靜態 UI 候選完整分類：134 新翻、33 原樣保留、8 設定識別保留、35 暫緩。
新增 108 個不同譯文，累計 552 個位置、377 個不同輸出字串、71 個字型指定。
整個 381 候選清單：257 翻譯、72 原樣保留、8 設定識別、44 暫緩。
337 個已有內容處置；44 的逐項理由在 research/ui/m042-disposition.json。
這些數字不是全遊戲覆蓋率，也不表示動態內容只剩 44 項。

- dialog_control：289 個位置
- dialog_title：51 個位置
- menu：111 個位置
- string：101 個位置


所有本版本 current_version_game_seen=false，歷史觀察不能移作本版通過。
314 項一般測試 232 通過／82 跳過；原檔測試 248 通過／66 跳過，均零失敗。
340 個固定控制項離屏樣本與 336 個固有文字尺寸樣本不能替代實際遊戲畫面。

仍未完成：44 個已盤點語境／動態候選、EXE CP932 記錄與訊息、外部資料的
文字用途／格式／載入關聯、存檔標頭日期、全引擎 Unicode、Win11 穩定性與畫質。
RES DAT／BMH／TIL 不能直接等同外部劇本；圖片字仍暫不處理。
最有價值的下一步是追一筆可見委託內容或道具說明到原始來源和安全邊界。
集中遊戲驗收的五組最小場景見 [本輪結果](M042-STATIC-UI.md)。

本輪成果只在本機，沒有新增遠端 blob、commit、分支或 PR。


## m045 local update

Adds 2 distinct standard status/help translations to m042: 554 translated resource positions in total. Both target RT_STRING block 3585; LD95 and 13 empty slots remain exact. This is a bounded correction found through m044 observation, not a claim of complete static UI or whole-game coverage. Story/data/HF parsing and dynamic text remain separate. The two candidates have not been seen in the game; the existing packaged tool still defaults to m042.


## m047 candidate integration (no new translations)

554 text locations / 379 distinct translations remain pinned to m045. The candidate now defaults to that profile; old profiles are still selectable. Runtime evidence covers the initial F1 prompt by direct observation and the File menu by user report. These are not whole-game coverage or save/load acceptance. No new text source or original-language anchor was added.
