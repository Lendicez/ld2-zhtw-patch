# m061 結果：清單 Unicode helper 編譯里程碑（compile-only＋mock）

日期：2026-10-29（Asia/Taipei）。`production_can_apply=false`、`release_approved=false`。未開遊戲、未寫出任何遊戲 EXE。

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

## 下一步（需另案授權，本輪未準備、未執行）

可丟棄副本的惰性 loader 驗收：在 Win11 以 m045 副本寫出一次雙 helper 惰性 EXE（hook 與 8 個清單點都不改），比對 sha256 `6a43dc4e…1cfe`，只確認 loader 能載入新段／新匯入後正常進入標題畫面。之後才是啟用清單點＋TextOutW 的功能版觀察。
