# m063d：catalog v4 啟用驗收交接包（Win11）

> **狀態：已在 Linux 準備並驗證完成，尚未在 Win11 執行。** `production_can_apply=false`、`release_approved=false`。

## 這包是什麼

m063b 已由使用者在 Win11 編出三個 MSVC 物件（NamePair／ListInsert v4／NameTextOut），Linux 已稽核並 pin。m063d 用它們在 Linux 合出兩個 EXE（**都不放進 git，也不放進 zip**；zip 只帶 delta，Win11 上由腳本從 m045 現場重建，每段 hash 釘死）：

| 版本 | 用途 | sha256 |
|---|---|---|
| 惰性版（模式 2） | L1：只加新段與新匯入，45 個位置全是 m045 原樣 → 行為應和 m045 相同 | `c796bc12378440b1ea027c5e268b0f564aff47bd4675b3a61bc1465068726e37` |
| 啟用版（模式 2，主要） | L2：hook＋18 清單點＋26 個名字 TextOut 點全部啟用 | `240ab04d7f81f185820865549c72b12a0c73475bb1f8dd073146731dab3f4121` |
| 惰性版（模式 0，保底） | 同上 | `811c0788c15836055516e3f77ce4129641bec05a0a31c80be23d7ff28713675c` |
| 啟用版（模式 0，保底） | 清單只在全部命中時走 W | `bdba6fb06bc328cb561fe0ca100a8af2e48e407acdf1a619826c0e957f4716d3` |

catalog：**lab_preview v4**（m051 264 列＋draft5 1817 列，含 Kris「波刃短劍」；共 6148 列，blob `bbe4974f…1502`）。這是實驗室預覽，**不可發行**。

## 檔案

| 檔案 | 進 git | 進 zip | 說明 |
|---|---|---|---|
| `WINDOWS-ENABLE-M063D.ps1` | ✓ | ✓ | 唯一要執行的腳本（UTF-8 BOM，Windows PowerShell 5.1 可用） |
| `USER-STEPS.zh-TW.md` | ✓ | ✓ | 使用者逐步指令（每段可整段貼上，附一行說明） |
| `PLAN-ACCEPTANCE.zh-TW.md` | ✓ | ✓ | 階段、預期 hash、軟警告／硬停止規則、證據內容 |
| `observations.template.md` | ✓ | ✓ | 觀察表（P 時複製到 evidence\observations.md） |
| `m063d-v4-lab_preview-mode{2,0}.delta.json` | ✓ | ✓ | delta 說明（runs、各段 hash、惰性還原資訊） |
| `m063d-v4-lab_preview-mode{2,0}.delta.bin` | ✗ | ✓ | delta 本體（含遊戲衍生 bytes，只放 zip） |
| `SHA256SUMS.txt` | ✗ | ✓ | zip 內所有檔案的 hash |

## 安全設計（沿用 m061b）

- 只寫 `-DisposableRoot` 指定的**新**資料夾；路徑已存在就停。來源安裝只讀，P 與 G 各做一次完整 manifest 比對。
- **惰性版先、啟用版後**：L1 判定為 `hard-stop` 時，`-Enable` 會拒絕執行。
- 每一步只能跑一次；任何一步 `hard-stop` 之後，只允許 `-Finalize` 與 `-Pack`。
- 腳本沒有任何寫回正式安裝的功能；正式套用需另外明確的 Finalize 指示與另一個交接包。
- `-Pack` 只收 `.json/.md/.txt/.png/.jpg`，單檔 ≤ 15 MB；EXE、`.LDP` 存檔、dump 一律拒收。

## Linux 端驗證（2026-10-31）

- `build_v4_lab.py`：lab_preview 與 reviewed 各跑模式 2／0，全部 bl.verify、fixup／binding、TextOut 點、物件稽核、pefile、禁止匯入、惰性＝m045（本體 0 byte 差異）、啟用−惰性 ⊆ 45 個窗＋CheckSum、catalog 讀回、Kris 語意 → 通過。摘要：`../static_verify_v4.lab_preview.summary.json`、`../static_verify_v4.reviewed.summary.json`。
- `make_v4_delta.py`：delta 套回 m045 → 啟用版 bit-for-bit；啟用版 → 惰性版還原 bit-for-bit。
- 本腳本的 `Assert-Delta`／`Build-Enabled`／`Build-Inert` 以 pwsh 7 在 Linux 實跑：模式 2、0 的兩個 hash 都重現；3 個反例（m045 被改 1 byte、run 位移被改、惰性 CheckSum 被改）都正確停止。
- **未驗證**：Windows 上的完整流程（robocopy、啟動、事件記錄、ReadProcessMemory、Compress-Archive）只能在 Win11 實跑。
