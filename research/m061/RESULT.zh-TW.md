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

## 下一步

使用者在 Win11 跑一次 `HANDOFF-LOADER-ENABLED`，交回 `m061-loader-enabled-evidence.zip`，再依證據寫結果。`production_can_apply` 仍 false。
