# 架構與模組切分

已實作的最小可移植核心：
- `patches/versions.json`：版本/大小/SHA-256 白名單；Steam AppID 尚未核實，null 必須阻止發行。
- `patches/ui-m020.zh-TW.json`：標準 menu/dialog/string 的目標譯文、locator、來源 UTF-16 雜湊、格式契約與歷史狀態。
- `ld2patch.pe_resources`、`menu`：自製 PE x86 與標準資源 parse/encode、資源尾端重建；禁止 ANSI relocation 分支。
- `ld2patch.contracts`：格式順序、數字寬度/精度、MFC indexed 參數、控制碼、快捷鍵、空字串/NUL、CP950 往返；Windows API 額外嚴格轉碼。
- `ld2patch.catalog`：唯讀原檔、記憶體改寫、完整輸出雜湊核對；目前鎖定 m020，不可更動譯文後仍沿用舊 output hash。
- `ld2patch.steam_vdf`：僅合成資料驗證的有界 VDF parser，尚未實作 registry/discovery/安裝。
- `research/native`：不編譯、不執行的 Unicode 邊界研究，與資源發行路徑分離。

下一步最小模組/測試拆分：
1. `discovery`：注入式 registry/filesystem 介面；以自製多 library fixture 測現代/舊式 VDF、無 Steam、離線庫、多候選、惡意路徑。真實 AppID 必須另由本地 manifest 核實。
2. `planner`：純函式產出版本與檔案差異、阻擋遊戲執行中/未知版本/不明 mod；不寫檔。
3. `transaction`：同磁碟 staging、備份雜湊、journal、鎖定、ReplaceFile/回滾；合成小檔測每一步故障、磁碟滿、拒絕、斷電恢復。尚未實作，不宣稱原子多檔交易。
4. `installer-ui`：自含 Windows x86 Win32 安裝器候選，標準 SDK、asInvoker、必要時才 UAC；顯示目標、變更、風險，按安裝才交給 transaction。
5. `packager`：預定單一 exe 嵌入譯文/patch 指令和自製程式，於使用者端解析已驗證原檔；不嵌入整個 EXE、完整 .rsrc、遊戲圖示或原版 DLL。不要把整段資源 replacement blob 當作已去資產化。
6. `release-gate`：包內資產掃描、來源/輸出雜湊、流程測試與一次集中 Win11 GUI/save/load 驗收後才允許發行。

雲端只執行無資產單元測試、合成 fixture、lint/編譯/原生轉碼。不要把整個既有 laboratory 複製到雲端。
Python 與未來原生實作必須共享 catalog/schema 和合成測試向量；跨實作輸出需在本機 licensed input 上比對。
Linux CI 尚未實跑。Windows 本機 Python 測試不等於 Windows CI 或遊戲通過。
