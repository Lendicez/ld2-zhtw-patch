# m061 結果：清單 Unicode helper 編譯里程碑＋惰性 loader 驗收

日期：2026-10-29（Asia/Taipei）。`production_can_apply=false`、`release_approved=false`。編譯里程碑階段未開遊戲；惰性 loader 驗收由使用者在可丟棄副本執行一次（見下）。

## Windows（使用者 Win11，HANDOFF-COMPILE）

| Stage | 結果 | 依據 |
|---|---|---|
| A compile-only | 成功：`list_insert_w.obj` 3073 B | `compile-command.json`：`/c /W4 /WX /O2 /Oi /Oy- /GS /Gy /Zl /EHs`，linked=false，game_touched=false |
| B mock link+run | 成功：exit 0，stderr 0 B | `once-result.json`：SDK 10.0.26100.0，`list_object_sha256` 同上，game_touched=false |

**鎖定物件 sha256：`d5349e58bd5087bb06aedda6c8b8dbfa1d2c0d1f87de42e1f86993869bfc61e0`**（`merge_plan.LIST_OBJECT_SHA256`）。
物件本體只留在實驗室 `runs/m061/compile-only/`，不進倉庫。

Stage B 第一次失敗（C1083 `cstdio`）：可攜式 MSVC 無 vcvars，腳本未設 `INCLUDE`。已修正並加 `-SkipStageA`（見 HANDOFF-COMPILE/README）。

## Linux 靜態稽核（`audit_list_obj.py`，capstone，未執行原生碼）：通過

- 未定義符號恰好 7 個：5 個 helper 綁定＋`___security_cookie`、`@__security_check_cookie@4`；無 memcpy／memset／chkstk／EH／heap／`__imp_`；`.drectve` 無 DEFAULTLIB。
- 唯一公開符號 **`@LD2_ListInsert@24`**（MSVC 對 `__fastcall` 的修飾；先前 stand-in 誤寫為 `_LD2_ListInsert@24`，已更正稽核／merge／synthetic）。
- 入口 3 個正常返回皆 `ret 0x10`、ESP 歸零、ebx/ebp/esi/edi 保全。
- 內部函式 `LD2_ListPrepare`（static，`__cdecl`，未內聯）：稽核器新增遞迴走訪，2 個返回皆 `ret`、ESP／非揮發暫存器保全；呼叫端 `add esp, 0x18` 清棧。
- 呼叫：MultiByteToWideChar（清 24）、SendDlgItemMessageW（清 20）、OriginalDlgItem ×2（清 16；其中一次為 `mov eax,[slot]; call eax`，稽核器追蹤暫存器來源）、security_check_cookie ×3。
- 重定位：DIR32 ×11、REL32 ×4。另有 3 個未被引用的 COMDAT（`ld2_decode932`、`ld2_list_find`、`ld2_list_valid_units`；/Gy 未經連結器剔除），會一併放入 `.ld2t`，不可達。

### 已知事項（不阻擋）

守衛 `!LD2_OriginalDlgItem` 失敗時仍呼叫 OriginalDlgItem（原始碼邏輯），若該槽為 0 會呼叫空指標。合併計畫固定把槽寫為 `0x4ea671`，`test_merge_lab` 也驗證合併影像中該字非零，故不可達。下次需要重編物件時再改為安全返回。

## 惰性雙 helper 合併（實驗室，未寫檔、未改 hook）

| 來源 | 輸出 sha256 | list 入口 | OriginalDlgItem 槽 |
|---|---|---|---|
| original | `7468ddbedaa4699b63286db7178458f3e213e9cab210d31b5ce59c747c97dc07` | 0xadc790 | 0xb03288 |
| m045 | `6a43dc4e3d881a207f4b0dae2fcc5f1fca5d079d6fe90139115da84ac3ef1cfe` | 0xae3790 | 0xb0a288 |

單 helper 輸出不變（原版 `08b9ec9e…41a1`、m045 `40fa133b…143c`）。匯入描述子 13→15；list 程式 1398 B、15 個 fixup、5 個程式段。摘要：`merge_inert_dual.summary.json`。

## 惰性 loader 驗收（Win11，HANDOFF-LOADER-INERT，一次）：**通過**

時間：2026-10-29 03:06:57–03:07:29（台北），Windows NT 10.0.26200。證據原件留在實驗室 `runs/m061-loader-inert/`（zip sha256 `a1b4e1b7…ad85c`）；倉庫只放去識別化摘要 `loader-inert-run1/`（無截圖、無 EXE、無存檔）。

| 判定項 | 結果 | 依據 |
|---|---|---|
| 寫出的惰性 EXE | `6a43dc4e…1cfe`，7,286,784 B；`game\Ld95.exe`＝`exe-store` 惰性版 | `hashes-before.summary.json`、`hashes-after.json` |
| m045 基底 | `4a0910…9da7`（m060 `exe-store\Ld95.m045.exe`）；delta `f26cdbb0…a64a` | 同上 |
| hook／清單點 | `hook_span_unchanged=true`、`list_sites_patched=false`、`textoutw_hook_enabled=false` | 同上 |
| 標題畫面 | **到達**：截圖顯示 Passage of The Book 標題圖、主視窗選單與工具列正常（m045 中文選單） | `screens/L-title..jpg`（只在實驗室） |
| 結束碼 | 1（`soft-warn-exit1`：此遊戲從選單結束的常見值，與 m060 一致），31.8 秒 | `launch-L.json` |
| 錯誤事件／WER／dump | 0／0／0 | `launch-L.json` |
| 原安裝 | 未變動：原版 `6c817a09…d5d2` 修改時間相同，1029 個檔案清單 0 變動 | `hashes-after.json` |
| 流程 | P → L → G 完整，`stopped=null` | `state.json` |

**載入意義**：匯入目錄已改指向新段 `.ld2i`；若新段未映射或 `GDI32!TextOutW`／`USER32!SendDlgItemMessageW` 無法解析，Windows loader 會在進入點前失敗（錯誤框＋非 0/1 結束碼＋事件）。實際正常到達標題畫面且無任何事件 ⇒ 15 個匯入描述子全部解析、三個新段已映射。

### 未完成／注意（不影響判定）

- `module_probe.ok=false`（「不可在值為 Null 的運算式上呼叫方法」）：32 位元 PowerShell 讀不到 `MainModule`（多半是權限／相容性設定造成 `MainModule` 為 null）。屬最佳努力項，不在通過條件內。下一個 handoff 改為 null 安全並改用其他方式讀模組大小。
- `observations.md` 未填（樣板原樣）；`launch-L-events.txt` 只有 BOM＋換行（0 事件）。截圖檔名為 `L-title..jpg`（多一個點，JPG）。

## 啟用版準備（Linux，2026-10-29）：已備妥，**尚未在 Win11 執行**

- 合成：輸出 sha256 `57103342f130da2ab51bf70e94d4dfb6c63245c3b375154bb4fbe27906b7ce5b`，是惰性版（`6a43dc4e…1cfe`）加上 TextOutW hook stub、8 個清單點和 checksum，共 66 B 不同。
- 靜態驗證通過（`enabled_static_verify.summary.json`），沒有任何失敗項。
- 交付：`HANDOFF-LOADER-ENABLED`（zip 在倉庫外）。腳本只寫可丟棄副本，存檔從 m060 副本複製，觀察紀錄為必填。
- 這一節**不是**執行結果：沒有開遊戲，也沒有在 Windows 寫出 EXE。

## 啟用版驗收（Win11，HANDOFF-LOADER-ENABLED，一次）：**穩定性通過；顯示功能部分達成**

證據摘要放在 `loader-enabled-run1/`（已去除路徑，不含 EXE、截圖或存檔）。執行時間：2026-10-29 03:34:46–03:37:00 台北，Windows NT 10.0.26200。

| 判定項目 | 結果 |
|---|---|
| EXE sha256 | `57103342…7ce5b` 與預期相符（P 記錄和 launch-L 一致） |
| 讀檔 | 讀第 1 格（從 m060 副本複製了 3 個存檔）OK |
| 結束 | 結束碼 1（soft-warn，從選單結束），共 134.5 秒 |
| 事件／WER／dump | 0／0／0 |
| 錯誤框／崩潰／卡住／存檔 | 無／無／無／沒有存檔（使用者填寫） |
| 原安裝未變動 | **G（-Finalize）沒有執行**，所以沒有 hashes-after，state 是 `finalized=false`。P 步驟時原版 EXE 複製前後 hash 相同，但完整的 1029 檔比對還沒做，需要補跑 `-Finalize` |
| module_probe | `ok=false`：OpenProcess/ReadProcessMemory 回傳 Win32 錯誤 5（存取被拒）。屬最佳努力項，不影響判定 |

### 截圖判讀（10 張，對照 m060 run2 的 D-2／D-3，也就是 m045 未啟用時的畫面）

- **helper 確實有在跑**：
  - m045 商店清單裡的道具名稱原本是零散的 `?` 和不可見字元（SJIS 被當成 CP950 解讀，落在 EUDC 區）。
  - m061 變成連續的 `?`，而且數量正好等於日文字數。例如第一列 11 個 `?`，對應 11 個字的「コンディションパウダー」（117G，說明視窗也確認是這個道具）。
  - 旅館委託清單（dialog 140）的漢字全部正確顯示：退治、救出、宅配、買物、逮捕、住民、商人、愛蓮、史 如松。只有假名變成 `?`，例如「?王」和「??????」。
- **假名變 `?` 的原因（推論，有證據支持）**：這些清單是 ANSI 視窗（MFC 用 A 版 API 建立對話框）。helper 用 `SendDlgItemMessageW` 送出 UTF-16 時，系統會先把字串轉成 CP950 再存進 ANSI 清單。CP950 沒有日文假名，所以假名變成 `?`；繁中和 CP950 內的漢字則能保留。
  - 也就是說，catalog 有命中的繁中名稱應該能正確顯示。
  - 沒命中的日文原文，只有漢字能保留，假名會變 `?`，**無法如預期顯示日文**。
- **各畫面對照 catalog 預期**（catalog 有 24 個基本名稱，含 +1～+10 共 264 列，都是武器、防具、藥水、油燈、鑰匙）：
  - 商店・購買（137）：道具店賣的是「〜パウダー」「トーチ」這類道具，都不在 catalog 裡，所以畫面上沒有繁中，這符合預期，不是 catalog 失效。最後一列可以看到「高…2花」這類漢字。要驗證 catalog 命中，需要去武器店或防具店，或找賣藥水、油燈的店。
  - 商店・出售（138）：只有一件 29G（推定是トーチ，58G 的一半），不在 catalog 裡，顯示 `???`。
  - 商店・強化（139）：沒有到達。
  - 酒館（143）：冒險者名都是片假名，全部顯示 `?`。這個 dialog 沒有 catalog，符合「143 尚無條目」。
  - 旅館・委託（140）：漢字可讀，假名變 `?`。沒有 catalog，符合預期。
  - 委託一覽（169）：沒有單獨截圖，使用者表示「部份委託人顯示???」。
  - 委託詳情（156／388）：使用者表示「大量缺字」。截圖裡出問題的是靜態欄位和說明文字框（例如「睛」「?」「ｼ」），那是另外的路徑（SetDlgItemText 或繪字），**不屬於這 8 個清單點**。site 0x4b1153（control 1021）在這張截圖裡看不到。
  - 道具說明視窗的名稱行：顯示正確的日文「コンディションパウダー」。它不在 catalog，所以 NamePair 會走原本兩次 ANSI 繪字。這和預期相符，但**無法用這個畫面證明 hook 有命中**，需要看 catalog 內的道具（例如ヒールポーション、ダガー）。
- 選單和對話框的固定 UI 仍然是 m045 的繁中，沒有退步。存檔清單的「?」是原版本來就有的現象。

### 結論

- 穩定性：**通過**。8 個清單點和 TextOutW hook 都已啟用，在商店、旅館、委託、酒館和說明視窗操作 134 秒，沒有崩潰、錯誤框或事件，最後從選單結束。
- 顯示：漢字已經改善，但假名仍然是 `?`。catalog 命中的效果還沒觀察到。
- 未完成的項目：G 收尾、module_probe（錯誤 5）、商店・強化，以及 catalog 命中的實機畫面。

## m061b 設計與靜態測試（Linux，2026-10-29 04:00 台北）：完成，尚未上 Win11

- 設計：helper v2（`native-u/list_insert_u.cpp`，入口 `@LD2_ListInsertU@24`）加上 `.ld2c` 政策字 `LD2_ListMode`。
  - 預設模式 2：catalog 未命中且目標是清單框時，若該控制項的程序等於類別程序（沒被子類化），就用 `SetWindowLongW` 重新設定同一個程序，把它切成 Unicode 視窗，再送 W。
  - 切不成功就和 run1 相同。
  - 模式 0：只在全命中時走 W，未命中整串回 m045 路徑（保底）。
  - 詳見 `M061B-DESIGN.zh-TW.md`。
- 新匯入：USER32 `IsWindowUnicode`、`GetWindowLongW`、`GetClassLongW`、`SetWindowLongW`。`GetDlgItem` 沿用 IAT 0x525498。
- 測試：`test_m061b.py` 12／12 通過（實驗室含授權 EXE 部分）；既有 `test_m061.py` 與 `test_merge_lab.py` 也照常通過。
  - i386 mock：22 個案例、1116 個斷言，0 失敗。
  - clang 預演物件：profile u 稽核通過（**預演物件不可鎖定或合併**）。
  - 記憶體內合併與啟用：8 個清單點都指向 v2 入口，未寫檔。
- 需要新的 Win11 編譯：`HANDOFF-COMPILE-M061B`（只編譯＋mock，不開遊戲）。

## 下一步

1. 使用者補跑 `-Finalize`，確認原安裝沒有變動。不需要重開遊戲；不擋 Linux 工作。
2. 使用者執行 `HANDOFF-COMPILE-M061B`，交回 `list_insert_u.obj`、`.asm`、`compile-command.json`、`once-result.json` 與 `stdout.txt`。
3. Linux：`audit_list_obj.py --profile u` 稽核並鎖定 hash，再合成模式 2（另備模式 0）的啟用版 delta 與 loader handoff。
4. 下一次 Win11 觀察：道具店或委託清單的假名是否正常，並去武器店或防具店確認 catalog 命中時是繁中。
5. 擴充 catalog（道具店的消耗品和冒險者名）屬於翻譯資料工作，另案進行。

`production_can_apply=false`、`release_approved=false` 不變。
