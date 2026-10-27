# CI 與費用控制（尚未啟用）

目前沒有 `.github/workflows`。遠端公開庫已由使用者建立，原始碼搬移不啟用 Actions；
CI 預算/額度與啟用執行仍須另行核准。
第一階段 Linux：Python 標準庫單元測試、合成 fixture、catalog/上傳白名單掃描；缺原檔 integration 明確 SKIPPED。
第二階段 Windows：標準 Python 測試與 WideCharToMultiByte CP950 無損測試；之後才新增已審核原生安裝器的 x86 編譯、合成檔 transaction 測試。
Windows runner 的 OS 依 runner image 而定，不能當作 Win11 GUI、DPI、音效、遊戲存讀檔驗收。
不得在 CI 儲存/下載遊戲、私人 saves、dump；不得把缺原檔標成整合通過。
待核准後初期只設 workflow_dispatch、contents:read、單一 concurrency、明確 timeout、短 artifact retention，
不設 schedule，不用 pull_request_target 執行外來碼，不用 self-hosted runner，不上傳含遊戲 bytes 的產物。
是否有免費額度、Windows 分鐘費率與超額預算須以當時帳號設定核實，這份文件不保證免費。
雲端打包只能用自製源碼與 target-only catalog；最終 release 需另外批准。
