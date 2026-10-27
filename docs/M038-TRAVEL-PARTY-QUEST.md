# m038：移動、隊伍與委託詳情

基底：PR #12 c96d16a706c98855876c6ad6c028839cd22771ed。
本批只有本機離線成果，公開範圍尚待整批確認；未建立遠端分支或 PR。

## 內容

新增 24 個未翻譯位置、22 組不同譯文：3 個標題、21 個控制項。
累計 295 個位置、216 組不同目標字串，不是全遊戲覆蓋率。
4 個對話框字型改為 MingLiU，累計 24 個字型位置。

| 對話框 | 用途 | 代表性譯文 |
|---|---|---|
| 154 | 前往其他城鎮 | 進入、目的地、目前位置、持有金錢、天數、資訊 |
| 170 | 隊友離隊 | 離隊、隊友、確定、取消 |
| 172 | 道具分配 | 分配道具、不參與 |
| 292 | 委託詳情 | 詢問意見、接受委託、委託人、承接人、狀態 |

5 個原本相同的文字位置保留，不計入新增。角色與城鎮名稱、金額、
貨幣記號、未確認的通行文件術語、動態委託內容與欄位均未改動。
對話框 168、173 本輪尚未確認使用鏈，保留原樣；不代表它們沒有使用。

## 靜態證據與動態文字界線

四條關聯已用固定來源雜湊和 Capstone 核對：命令分派、資源描述表、
類別工廠，或委託一覽詳細按鈕經虛擬函式到詳情資源。有限位置常數、
類別名稱記於 review.json，沒有完整反組譯或原始程式區塊。

委託期限另有動態文字鏈：32 位元整數傳給 wsprintfA，來源格式帶
CP932 日文字尾，再經 MFC wrapper 呼叫 SetDlgItemTextA，寫入 dialog
292 的 control 1050。詳見 dynamic-boundary.json。此段沒有看到明確
CP932 → Unicode 轉換；資源譯文不會修正動態期限。兩個格式化緩衝位置
相隔 64 bytes，但完整容量和所有寫入邊界未證實。wrapper 的控制站
虛擬分支亦未完成分析。

下一個最小切口是離線 UTF-16 期限組句，保留 signed int32 參數契約；
完成 HWND／Unicode 狀態、ABI、生命週期、錯誤回退與覆寫路徑證據後，
才評估單一控制項的 Unicode 設定邊界。本輪不修改或執行該鏈，
不使用全域 CP950 替換，也不更動 HF。

## 驗證與重現

一般套件 274 tests：200 通過、74 跳過、0 失敗。
帶合法原檔套件 274 tests：208 通過、66 跳過、0 失敗。兩套計數不可相加。
新增 8 個測試涵蓋 profile 保留、格式拒絕、編碼差異、原檔重建、
資源邊界、命令／工廠關聯、動態 ANSI 邊界。

24 個新位置通過 Windows 原生 CP950 往返。新位置沒有 printf 參數；
負面測試確認新增參數、控制碼、換行、快捷鍵及 NUL 被拒絕。
動態期限候選的 signed int32 極值僅做離線檢查。
21 個新控制項於 96／144／192 模擬 DPI 共 63 次 memory DC 量測通過，
沒有缺字或估算超寬；未建立視窗、未變更系統 DPI。

兩次獨立 CLI 重建 EXE 和 metadata 完全一致，7,106,560 bytes，
SHA-256：8730f5731730afcf8a20e245958744d2b227dde4fa260d861eae296001ef65b2。
相較 m037 僅四個 dialog payload 改變。程式／資料區和原檔內容不變。
m020、m037 的 catalog、recipe、版本及預期輸出均保留並回歸確認。

需新建輸出資料夾，輸出不可存在或位於來源目錄：

~~~text
python -B tools/check.py
python -B tools/check.py --game-exe <absolute-original-Ld95.exe>
python -B tools/build_patch.py --profile m038 --input <absolute-original-Ld95.exe> --out <fresh-output-directory>/Ld95.exe --metadata-out <fresh-output-directory>/metadata.json
~~~

預設仍為 m020；m036 單 EXE 候選與安裝器未重打包。
Production can_apply=false。原生 opt-in 交易測試的 skip 不是通過。
未執行遊戲／GUI，也未驗證實際焦點、裁切、DPI、存讀檔或動態覆寫；
既有畫面觀察不能當成本版本驗收。

## 候選公開範圍

完整候選 manifest、hash 與逐檔分類保存在本機 m038 紀錄目錄。
新 catalog 有 24 個新譯文位置和來源 hash、定位 ID、格式／字型設定，
並保留 271 個既有位置。review.json 含 24 列有限原文／譯文對照、
5 個未變文字錨點，以及四條關聯的必要位置常數。
dynamic-boundary.json 另含一個短格式錨點、hash 與動態呼叫位置／限制。
測試含定位常數與自有驗證程式；文件含分析摘要與譯文例子。

不含遊戲 EXE、原始 bytes、完整反組譯、全量原文抽取、圖片音樂、
私人存檔、venv、dump 或秘密。本批不遠端寫入，須先取得整批公開確認。
