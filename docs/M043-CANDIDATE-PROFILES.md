# m043：m042 單 EXE 副本驗收候選

基底為 PR #16，commit 4ba99ec099b76ed88cb470c5fbad137587338783。本機候選預設 m042：552 個文字位置、71 個字型位置。m020、m037、m038、m041 仍可選；m039 動態 formatter 與 m040 版面候選未啟用。原有非 trial generator 命令仍預設 m020。

## 版本、確認與還原

profiles.py 固定五種 profile 的 recipe、來源／輸出 hash、大小及版本。計畫與確認畫面顯示 profile、recipe ID、文字位置數與預期輸出 hash。混用、竄改或未知 profile 在建立副本前拒絕。

還原憑據的 version 欄位由目前使用者 DPAPI 保護，並與 workspace、vault、case 身分及 receipt 雜湊綁定。還原依憑據選出固定 CopyRecipe；重新啟動時選擇的 profile 不會覆蓋它。m020 舊版本值仍被接受。沒有編輯 JSON、抄 hash、由未驗證日誌重建憑據或切換信任來源的 fallback。

每次確認僅建立新的有界測試工作區；不採用正式遊戲目錄作為目標。16 MiB 上限、原檔保留、備份驗證、metadata 比對及可診斷日誌沿用既有 backend。兩次 rename 仍有短暫缺少目標檔名的空窗，不宣稱全原子或真斷電安全。

## 本輪實證

- 通用回歸：326 項，241 通過、85 跳過、0 失敗。
- 唯讀合法原版回歸：326 項，258 通過、68 跳過、0 失敗。兩組不能相加；跳過不是通過。
- 原生憑據套件：20 項全部通過，其中 14 項 headless、6 項實際 Windows DPAPI／檔案測試。與通用套件有重疊。
- onefile 實際執行 13 次：help、version、未知來源拒絕、範圍外工作區拒絕、m042 預檢、取消、缺少確認拒絕、m020 預檢、1.0.3.17 錯誤版本拒絕、m042 安裝、另程序檢查、另程序還原、再次還原。全部符合預期退出碼。
- 取消與所有拒絕案例未變更限定候選根目錄；沒有移除安全封鎖或模擬 process guard。
- 實際安裝輸出為 7,118,848 bytes，SHA-256 9fea1172e92167d435a8ec26baf085ab45a2a56468690bf7bfec1f8ba29dc367。
- 跨程序還原刻意在 CLI 選 m020，仍依受保護憑據辨識 m042。還原後的 hash、檔案身分、attributes、建立／修改時間及 owner/group/DACL 雜湊與保留原檔一致；再次還原檔案內容與修改時間不變。憑據沒有被重建或改寫。
- 原版 Ld95.exe 始終是唯讀來源，SHA-256 6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2；未執行任何遊戲 EXE。
- 包內 17 個資料檔逐位元核對，其中 16 個為公開 profile／Steam 資料，1 個為本機限定 policy。Tk runtime 存在，但不代表 GUI 已目視驗收。

## 候選與命令

版本 0.4.0-m043，AMD64 單 EXE，13,046,007 bytes。
SHA-256：8809f16af4de559658980de07bc53f60cb006adb0f30783a4d4ccc8dc84fc018。
PE manifest 為 asInvoker、uiAccess=false；未簽章，不要求 UAC。僅在本機保存，不是 release。

一般權限背景命令範例：

    ld2-patch-generator.exe --help
    ld2-patch-generator.exe --version
    ld2-patch-generator.exe --trial preview --source <original>/Ld95.exe
    ld2-patch-generator.exe --trial preview --source <original>/Ld95.exe --cancel
    ld2-patch-generator.exe --trial install --source <original>/Ld95.exe --profile m042 --confirm
    ld2-patch-generator.exe --trial inspect --workspace <tool-created-workspace>
    ld2-patch-generator.exe --trial restore --workspace <tool-created-workspace> --confirm

無參數或 --gui 會開啟圖形介面，本輪未走此路徑。GUI 的 Steam 探測按鈕仍停用，手動選擇來源可用。工具內建 policy 綁定本機專用根目錄與身分；不能當一般可攜式正式安裝器使用。DPAPI 還原須保留整個工作區並使用同一 Windows 帳戶。不要以管理員身分啟動 onefile。

## 限制與狀態紀錄

production can_apply=false；正式安裝、全引擎 Unicode、遊戲畫面、遊戲存讀檔及跨地區執行均未驗證。m042 靜態資源仍限定 ACP950。完整遊戲準備及集中 GUI／遊戲驗收見 M043-ACCEPTANCE.md。

早期前置曾被工具核准審查拒絕，之後取得明確批准才成功執行，紀錄均保留。Git 本次 add 成功；兩項工作檔差異證實僅為 CRLF 與索引 LF 的差異，依原有 .gitattributes 正規化後一致。這沒有改 Git／系統安全設定，也無法倒推先前未保留 stderr 那次 exit 1 的確切原因。

沒有新依賴、GUI、遊戲、提權、防護設定變更、遠端寫入、commit、PR、merge、release 或 Actions。累計容量及待發布清單以 packaging/m043-verification.json 與本機完成紀錄為準。
