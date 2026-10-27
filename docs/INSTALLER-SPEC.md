# 單一 Patch 安裝 EXE 規格（尚未實作）

## 偵測與確認

僅唯讀 Steam 官方登錄位置取得 Steam root，再讀該 root 的 `steamapps/libraryfolders.vdf`，
列出所有 library（含 root），讀對應 `appmanifest_<已核實AppID>.acf`；核對 AppState.appid、檔名和 installdir。
這輪 SteamPath 登錄讀取被拒，AppID 未由本地 manifest 核實，因此目前 null，禁止猜測或使用網搜值代替。
拒絕空/相對/穿越/UNC 或不受支援 reparse 路徑；正規化 library 與 common 子路徑後驗證 containment。
不掃全磁碟、不下載遊戲；多候選顯示路徑/版本供選擇，也可手動指定資料夾並做同樣驗證。
畫面列明完整目標、版本、來源/預期輸出 hash、將修改的 Ld95.exe、備份位置、ACP 限制與未簽章資訊。
只有按「安裝」才寫入；選擇與預覽不寫入遊戲目錄。禁止無提示自動選第一個候選。

## 預檢與寫入

- EXE 完整 SHA/大小/版本白名單，不匹配拒絕；版本號相同不能取代 hash。
- 偵測所有候選 Ld95 程序，核對 canonical path/file identity；資訊不可讀或狀態不明時拒絕寫入，不關閉程序。
- 安裝器只使用最小權限；讀取/目錄可寫性不足時說明精確操作，再走正常 UAC。原遊戲 requireAdministrator manifest 保留。
- 再次核對開啟檔案的 identity/hash 防止 TOCTOU，排除 reparse race；同時安裝需互斥。
- 在同磁碟私有暫存目錄產生目標並核對預期 hash，先建立不可覆蓋的原檔備份，flush 後重新讀回驗證可還原。
- journal 記錄 transaction id、來源/目標 hash、備份與操作狀態；驗證備份及產物後才做 Windows 支援的 replace。
- 故障時依 journal 回滾；拒絕或重啟中斷時下次先恢復/報告，不繼續半套安裝。Windows ACL/檔案鎖/防毒可能使 replace 或回滾失敗，必須保留備份並明確回報。
- 當前目標僅一個 EXE。未來多檔更新不能假稱 OS 提供整批原子性，需可恢復逐檔交易。

## 重複安裝、升級及解除

已知相同 patched hash：顯示已安裝，不重複改寫或覆蓋原始備份。
升級：只接受已知舊 patch hash 且可驗證原始備份，從原始版本生成新版本；不能層疊未知差異。
解除：只在現檔等於該安裝器已知 patched hash 且備份匹配時還原；現檔不同視為更新/其他 mod，停下不覆蓋。
USR、LUNAS 存檔、ini、其他 mod 一律不納入寫入或刪除。備份採版本與 hash 識別，不能覆寫先前備份。
Steam 更新或驗證完整性可能還原遊戲；要提示重新偵測與版本核對，不默默重套。

## 安全與交付限制

不關閉 Defender/SAC、防火牆，不加排除、不改信任/ACL/locale，不注入，不下載或執行外部程式，無遙測。
單 exe 自含自製碼、翻譯和資源編輯指令；不得夾帶完整遊戲/原 .rsrc/圖音/存檔。
未簽章可能有警告或被政策封鎖；簽章亦不保證免警告。封鎖時停止，不能提供繞過步驟。
目前未批准買 code-signing、不新增憑證、無發行 installer。可回復設計不保證能撤銷任何遊戲自身外部寫入。
