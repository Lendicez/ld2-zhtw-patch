# m039：委託期限 UTF-16 離線研究

本機基底是尚未發布時封存的 m038；遠端祖先為 PR #12。
成果為純 Python formatter 與 headless 單一控制項邊界模型。
沒有新遊戲 profile，沒有原生 hook／DLL，沒有 HWND 存取或訊息發送。
m020、m037、m038 的 catalog／recipe／版本／輸出與安裝限制均保持不變。

## 可重用程式

src/ld2patch/deadline_text.py 提供：
- format_deadline：只收真正的 signed int32，產生繁中天數文字。
- signed_days_from_word：明確將 unsigned x86 word 解讀為 signed int32。
- utf16z_single_line：回傳獨立 UTF-16LE bytes 與 NUL；容量以 UTF-16
  code unit 計，拒絕 NUL、控制碼、孤立 surrogate、超限，不截斷或替換。
- preview_deadline：僅產生不可變文字／bytes 和阻擋原因。即使所有合成
  控制項觀察值為真，can_apply 仍永遠為 false，不可當執行許可。

最長數值輸出含 NUL 為 14 units／28 bytes，使用新配置資料，
不與原版 stack／heap buffer 共用。可處理「錄、檔」及非 BMP 合成字元，
不以 CP932 可表示的字元替代 Unicode 驗證。這不是字型繪字成功證明。

## 靜態證據與語意

固定來源版本的期限 getter 位於 0x9d0e0，從索引選到的記錄 +0x2c
讀取完整 32-bit 值。0x643d1 呼叫 getter，值存入 local，後續傳給
wsprintfA 的單一 signed decimal 參數。未找到可證明的業務上限或
負值 sentinel 語意，因此不截斷、不歸零、不擅自顯示「無期限」。

數值路徑只適用於 signed quest selector <10000；另一分支從記錄 +0x46
直接取既有期限文字。本輪不改該分支，也不把任意文字送入數值 formatter。

目標資源是 dialog 292、control 1050，唯一相符控制項為 STATIC，
初始文字空白，位置／尺寸為 (30,117,20,8) DLU。
這些是資源身份，不能當成執行中的 HWND 或 Unicode 狀態。

對 0x64270 的有界直接 CFG 共解碼 371 條指令，沒有未解直接跳轉；
不表示被呼叫函式或例外路徑全部分析。格式化、設定控制項與正常返回
發生於同一 stack frame。wsprintfA 呼叫後 caller 清理 12 bytes；
MFC setter wrapper 正常路徑 ret 8，populate 正常返回亦 ret 8。
尚未證明原緩衝區個別容量、alias、例外／重入路徑或未來 adapter ABI。

## 官方 API 限制

Microsoft 文件指出 wsprintfA 使用 cdecl，%d 為 signed decimal：
[wsprintfA](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-wsprintfa)。
新 formatter 不呼叫這個不帶容量參數的 API。

[SetDlgItemTextW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setdlgitemtextw)
以 WM_SETTEXT 設定控制項文字；Windows 會依目標視窗字元集轉換訊息。
[IsWindowUnicode](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-iswindowunicode)
文件說明其字元集來自類別註冊。故單改 A 為 W 不保證保留繁中字元，
更不能拿原窄字串指標當寬字串。文件查核日期：2026-10-27。

## 測試與版面風險

新增 16 個測試：
- int32 上下界、零、負值，以及 133 個 x86 word 的 signed 解讀對照。
- 拒絕 bool／float／字串 coercion、超界及格式字串輸入。
- 保留單一 %d 契約，排除型別、參數數量、百分號及換行變化。
- UTF-16 NUL／surrogate／容量邊界、獨立不可變資料。
- 錯誤對話框／ID／class／文字分支，以及未知或未證實的 Unicode、
  存活、同 UI thread、普通 Win32 控制項、生命週期、版面均阻擋。
- 即使合成條件全部符合，也永不允許真正套用。
- 帶合法原檔時核對 getter、傳遞位置及唯一資源控制項；不執行遊戲。

一般套件：290 tests，215 通過、75 跳過、0 失敗。
含原檔套件：290 tests，224 通過、66 跳過、0 失敗。
兩次計數不可相加；缺原檔與 opt-in 原生交易測試的 skip 不是通過。

96 DPI 的獨立 memory DC 估算：期限欄位約 50×19 px；「365 天」約
60×19 px，int32 極值約 130–140×19 px，會超寬。7 個樣本中 3 個
估算不符版面；沒有缺字。這是實際發現的離屏風險，沒有隱藏或改尺寸
讓檢查通過；不代表已觀察遊戲裁切。未建立視窗或變更系統 DPI。

~~~text
python -B tools/check.py
python -B tools/check.py --game-exe <absolute-original-Ld95.exe>
~~~

## 下一個最小接入方案

目前不可安全接入。先確認數值分支的真正可見範圍／負值語意，並設計
不裁切版面；不得以改小字或截斷數字掩蓋未知範圍。
接著在另外授權的集中動態驗收中確認 dialog 292 的 control 1050
實際 HWND、父子關係、UI thread、Unicode 狀態、普通控制項分支及存活。
再評估一個專用邊界：新配置 UTF-16 資料至少存活至同步 setter 返回，
保持原數值與其他欄位、回傳／錯誤行為，失敗時回退原路徑。
在 ABI、重入、例外清理和 ANSI 目標轉換風險未證實前，不建立 hook 或
原生接入，不把此研究合併進可安裝 profile。m038 的靜態資源成果可獨立使用。

本輪未上傳 m039；本機原始碼／合成測試／本文件可依專案公開範圍另行審核。
私有靜態與版面紀錄仍在工作區，不包含於 repository 白名單。
