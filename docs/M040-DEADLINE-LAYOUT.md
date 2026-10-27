# m040：期限欄版面與單一接入點

基底為 PR #14 commit f606b290dd93bffb8b1cdaf3beb7ead413e5faa9。
本輪已完成有版本鎖定的「單一對話框版面候選」，沒有新增翻譯、native adapter、
遊戲呼叫修改或 GUI 執行。m020／m037／m038 的 catalog、recipe、版本白名單、
輸出雜湊及打包設定保持不變；正式 can_apply 仍為 false。
本地結果與待發布 manifest 已備妥，本輪沒有任何遠端寫入。

## 已收斂的版面方案

固定來源版 dialog 292 是標準 DLGTEMPLATE，大小 149×148 DLU，17 個控制項。
control 1050 是 item 8、STATIC（class ordinal 130）、style 0x50020000，
初始文字空白。其低位型別為 SS_LEFT，沒有 ellipsis 樣式。原版字型為 FixedSys
14pt；m038 已改為 MingLiU 14pt。本輪保留 m038 字型和字級。

期限原位置 (30,117,20,8) 只給 20 DLU 寬；同列委託標籤從 x=63 開始，
不能任意往右放大。已選擇期限獨立一列、委託移到下一列，保留完整數字。

| 對象 | 原 rect (x,y,w,h) | 候選 rect |
|---|---|---|
| 期限 control 1050 | 30,117,20,8 | 30,117,115,8 |
| 委託標籤 item 10 | 63,117,25,8 | 5,127,25,8 |
| 委託值 control 1054 | 87,117,56,8 | 30,127,113,8 |
| 三個按鈕 | y=131 | y=141，其他尺寸不變 |
| 對話框 | 149×148 | 149×158 |

保留全部控制項 ID、class、style、順序、原有標題與控制項文字、字型資料。
只有 6 個控制項的矩形及對話框高度不同；新改動控制項沒有幾何重疊，
所有控制項在邊界內。未改的報酬標籤與值原先相交 3 DLU，委託人／承接人
標籤與值也原先相交 3 DLU；不把這些既有幾何情況宣稱為已修復。
動態值長度及實際文字是否碰撞仍須觀察。

Windows 的 DS_SETFONT 會依模板字型資料選擇字型並送出 WM_SETFONT，
但後續遊戲程式仍可能另行改字型或位置。參考
[Dialog Box Styles](https://learn.microsoft.com/en-us/windows/win32/dlgbox/dialog-box-styles)。
[SS_LEFT 文件](https://learn.microsoft.com/en-us/windows/win32/controls/static-control-styles)
說明其文字可換行，而過長單字仍可能被截斷；因此本方案以整行容納驗證，
不靠換行、縮字或省略號隱藏數字。

## 離屏量測與輸出

使用既有 Windows GDI memory DC、實際 MingLiU 字型識別及 DrawTextW CALCRECT；
不建立 HWND、不截取螢幕、不變更系統 DPI。11 種數值在 96／120／144／192 DPI
共 44 組全部容得下，另檢查 40 組既有靜態標籤／按鈕，沒有估算超寬或缺字。
數值包括 0、1、30、365、999、1000、負值及 signed int32 兩端。

| DPI | 最長數值文字 px | 新欄位估算 px | 水平餘量 px |
|---|---|---|---|
| 96 | 140×19 | 287×19 | 147 |
| 120 | 168×23 | 345×23 | 177 |
| 144 | 196×28 | 402×28 | 206 |
| 192 | 266×37 | 546×37 | 280 |

最長文字為「-2147483648 天」，含 NUL 仍為 14 個 UTF-16 units。
另外逐一量測十種數字重複十位的負值字形，寬度也在保留餘量內。
不推定遊戲真的允許極端數值；負值或 sentinel 的業務語意依舊未知。
模板高度 8 DLU 在這些字型量測中剛好容納一行；沒有證明其他字型、
輔助功能設定、實際 monitor DPI、視窗邊框或後續 WM_SETFONT 的效果。
替代分支直接讀既有期限字串，其最大長度未知，不在數值容量保證內。

候選 EXE 為 7,110,656 bytes，SHA256：
2afdc14391cf6e700f31c593e738d59cf66a6cc13f3b56b1fdbf9448e72313e1。
兩次獨立輸出 EXE 與 build.json 都逐 byte 相同。
它從白名單原版重建已鎖定 m038，再只附加新版 dialog 292 資源，
逐階段驗證 .text／.rdata／.data 等非資源區及其餘原始內容不變。
不是新的可安裝 profile；CLI／GUI 預設 m020 和正式安裝限制未變。

新增 6 個測試：幾何差異／不改原輸入、未知字型／控制項／樣式拒絕、
越界與重疊拒絕、相鄰邊界、錯誤 payload／版本拒絕、真原檔重建與差異。
一般套件 296 項：220 通過、76 跳過、0 失敗。
含合法原檔 296 項：230 通過、66 跳過、0 失敗。
兩者不可相加；本輪未重跑需 opt-in 的 Windows 交易／程序中斷套件。
另驗證 CLI 拒絕已存在輸出與修改版來源，既有輸出／原版均未改變。

~~~text
python -B tools/check.py
python -B tools/check.py --game-exe <absolute-original-Ld95.exe>
python -B tools/measure_deadline_layout.py
python -B tools/build_deadline_layout.py --source <absolute-original-Ld95.exe> --out-dir <absolute-fresh-build-dir>
~~~

輸出目錄必須全新且在來源安裝目錄之外。不安裝、不執行輸出；失敗留下的
產物不會被當作成功候選，既有目錄也不會被覆寫。完整遊戲檔留在本機。

## 最小動態接入點與停止線

數值路徑的最小專用邊界是原版 file offset 0x64553、VA 0x464553 的
五位元組 direct call，目標 wrapper file offset 0xea69f、VA 0x4ea69f。
它位於 shared populate 函式 0x64270，只屬於 selector signed <10000 分支，
控制項 ID 為 1050。另一分支的 0x646f1 同樣設定 1050，但輸入是既有字串，
不應被數值 formatter 攔截。不能改共用 wrapper 或全域 A/W 匯入。

原 setter 呼叫邊界為 ECX=this、兩個 32-bit stack 參數（ID、窄字串指標）；
普通路徑 ret 8。原 signed 數值先從記錄 +0x2c 讀入 local，再以 signed
decimal 格式化。格式化至 setter 均在同一正常 stack frame 內，但
原個別 buffer 容量、alias、例外／重入、caller frame 耦合仍不是完整證明。
單一 callsite 接入也不能只接收原窄字串指標就把它當 UTF-16；必須另行
保存／取得正確原數值，使用獨立 28-byte 以上的 UTF-16 儲存並維持同步呼叫
到返回。未實作此 native ABI，也未跳過原有 wsprintfA 或寫入其 buffer。

wrapper 會檢查 this+0x4c：零時用 this+0x20 的 HWND 呼叫 SetDlgItemTextA，
非零時跳至 control-site vtable+0x88。資源中的 STATIC 身份不能證明
執行時這個分支值，也不能證明 live HWND 的 Unicode 狀態與同執行緒生命週期。
[IsWindowUnicode 文件](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-iswindowunicode)
指出視窗字元集與註冊方式有關，訊息會自動雙向轉碼。因此僅將 setter
名稱換成 W 不足以證明所有 Unicode 可保留。

本輪的結論是：版面可離線完成，數值 formatter 可重用；真正接入仍停止。
目前沒有安全可啟用的動態 patch。若實測為 ANSI，應先明確選擇限 ACP950
的產品範圍或另行證明真正 Unicode 控制項方案，不能把呼叫 W 當成完成。

## 一次集中觀察的最小清單（本輪不執行）

預約一個短時段，單一獨立完整副本，以新測試角色／世界或已確認為可丟棄的
測試存檔到達「委託一覽 → 委託詳情」。先確認能正常到達此狀態；不能到達
就記錄前置缺口，不編輯存檔或虛構期限值，也不反覆啟動遊戲尋找。
執行前仍需明確核准本版主機遊戲與正常 UAC，並確認沒有另一個測試實例。

同一次開啟集中收集：
1. 正確 PID／EXE hash、父對話框、control 1050 的 HWND／STATIC class／ID、
   實際 rect、字型、DPI、IsWindowUnicode 與視窗所屬 UI thread；只讀查詢。
2. 實際期限文字及相鄰委託／報酬欄，開啟、返回後再開一次，查看是否被
   後續重繪／設定覆蓋；不注入、不發送修改文字訊息、不造極端遊戲狀態。
3. 保持按鈕／Tab／Esc／返回流程；正常退出，檢查新的 USR／INI 差異以及
   原版保護清單。這只能驗收版面與可觀測 HWND 行為，不能單靠畫面證明 ABI。

this+0x4c 的實際分支、數值傳遞與例外／重入清理不是普通螢幕觀察可得。
若要在同一輪取得它們，需要另行核准只針對該遊戲 PID 的唯讀 debugger／
程序記憶體觀察；目前沒有安裝、啟動或假定已有這個途徑。若工具權限不足，
停止該觀察，保留為未證明條件，不能藉改 manifest、換載入方式或放寬安全設定
繞過。尚未觀察前不開發或執行 hook／DLL。

## 完整副本容量與存檔分離

本機既有乾淨清單的 1,029 檔共 193,798,416 bytes，全部雜湊再次符合。
保留 RES、music、avi、說明文件與其他根檔，不以猜測刪減所需資產。
替換成本候選後，一份完整副本為 193,818,896 bytes（約 184.84 MiB）；
原版對照加候選兩份共 387,617,312 bytes（約 369.66 MiB）。
另保留 7,090,176-byte 原 EXE 回復份與新存檔／觀察紀錄空間。
建議單份預留 256 MiB，兩份對照預留 512 MiB；這是規劃餘量，
不是對任意遊玩時間或所有外部快取寫入量的上限。沒有建立完整副本。

後續只在新短 ASCII 路徑下建立專用副本，例如 LD2 工作區內的
zhTW_lab/playtest/m040-a，明確以該目錄為 cwd；建立全新 USR，不複製
正式存檔或唯一基準存檔，也不執行安裝腳本。乾淨清單本身沒有 USR 檔。
若需要可到達委託狀態的測試存檔，從已明確識別的可丟棄測試資料另複製一份，
保留來源不變；未確認路徑與用途前不讀取其內容。

既有 m022 靜態證據指出初始存檔路徑由 cwd 加 USR 建立，INI 使用 cwd 下
ld95.ini；目錄選擇可能改 cwd，MFC profile 也可能寫 HKCU。HKLM 安裝腳本
有 LD95DL／BootDirectory／Directory，但先前未證明這些是遊戲的直接
執行依賴，不應把 HTMLHelp 的 HKLM CLSID 查詢混為一談。
本輪沒有重查 registry 或擴大系統權限。

遊戲 manifest 仍 requireAdministrator。不同資料夾只分開預期資料，並非
安全隔離，也不能保證所有寫入只留在副本；不保證還原未監測的外部寫入。
測試過程不選原版／私人目錄、不開既有遊戲的存檔；若發現路徑指向外部、
Windows 封鎖、需額外安裝／權限或無法確認目標，就停止。先核對 cwd、
存檔目錄與前後檔案清單，再把可丟棄副本作為一次集中驗收的對象。

## 剩餘文字：一次盤點，非覆蓋率

以原始資源逐一核對 1,784 個非空位置，按實際 resource／item 身份去重；
m037／m038 source_key 有命名差異，不能只用 source_key 字面比對。
已翻 295 個位置、216 種譯文；另有 15 個確認原文已適用繁中的位置，不計新增。

剩餘一般 UI 候選為 381 個位置：18 選單、49 標題、259 控制項、55 RT_STRING。
這些是可辨識 UI 類型但仍待用途／呼叫語境確認的候選，不是 381 項可以盲翻。
優先依功能一次處理：設施對話框 171；角色／世界建立 42；對話／人物互動 26；
其他遊戲對話框 44；主選單 18；遊戲 RT_STRING 55；其他待確認對話框 25。
各組完整 resource ID 及數量在 research/layout/remaining-ui-summary.json。

另外分開保留 849 路徑／內部識別、109 數值／ASCII placeholder、106 framework
訊息、12 替代選單、9 debug UI、4 動態替換 placeholder、4 品牌版本項。
動態 CP932 訊息、HF／記錄資料、存檔標頭既有文字尚不在此盤點分母；
圖片內文字依需求暫不處理。沒有宣稱全遊戲抽取率或完成率。

最有價值的下一步是上述一次委託詳情集中觀察，以決定實際單一控制項接入
策略；內容工作可另按設施功能群補呼叫證據後整批處理，不再硬湊每批 20 項。
