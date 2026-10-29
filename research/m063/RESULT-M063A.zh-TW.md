# m063a 結果：NameTextOut 第三物件槽＋改寫計畫（Linux 靜態）

`production_can_apply=false`、`release_approved=false`。只在 Linux 上做靜態工作：沒有寫出 EXE，沒有跑遊戲，沒有在 Win11 編譯。`name_textout_v3.obj` 還沒有 MSVC 版本，所以 `TEXTOUT_OBJECT_SHA256=None`（等 m063b）。

## 總結：**通過**（以 Linux clang 預演物件驗證；不能交接）

## 新檔（`research/m063/`）
- `merge_plan_m063.py`：在 m062 `merge_plan_v3` 之上加第三個物件槽。
  - `.ld2t` 版面：`[name_pair_v3][16 對齊][list_insert_v3][16 對齊][name_textout_v3]`。`.ld2c`（16 B 標頭＋v3 blob）和 `.ld2i` 不變，NameTextOut 不加新 import。
  - NameTextOut 的綁定和 NamePair **共用**同一組（`_LD2_Catalog`、`_LD2_CatalogBytes`、`_LD2_ExpectedTextOutA`、`_LD2_TextOutW`、cookie）；建構時會檢查兩者完全相同。
  - 拒絕條件：
    - 槽數不是 3、長度為 0 或超過 0x4000、沒對齊、重疊、span 不符；
    - NameTextOut 未鎖定（沒有 pin 就拒絕；預演必須明確給 pin，報告標 `textout_rehearsal=true`、`handoff_eligible=false`）；
    - pin 和 NamePair／List 的 pin 重複、undefined 或 public 集合不符（例如把 NamePair 物件放進第三槽）；
    - image base 不是固定 0x400000、或有 relocation／DYNAMIC_BASE（helper VA 用 imm32 絕對位址，所以要擋）。
- `enable_plan_m063.py`：在 m061 hook stub 之上加：
  - 25 個 pair5：`mov R1,[cdc]; mov R2,[R1+0x5c]` → `mov R2, imm32 NameTextOut`。每一點都檢查 sha8、4 個 push 之後是 `mov ecx,cdc; call R2`。
  - 1 個 tail8（0x48f47e，sha8 `7bcdd7c8`）：`push ecx; mov ecx,esi; call rel32`，返回位址仍是 0x48f486。
  - 清單 18 點：m061 優先 8 點＋m063 新增 10 點（8 個 LB_INSERTSTRING、2 個 CB_INSERTSTRING），都用 ListInsertV3。
  - 拒絕條件：摘要旗標或 source sha 漂移、點數多或少、bytes 不符、helper VA 不在 `.ld2t`、改寫窗重疊、清單訊息／優先旗標／readback 漂移，以及 allowlist 外的任何 byte 變動。
- `audit_name_textout.py`：移植 m062 NamePair 稽核。`@LD2_NameTextOut@24` ret 16、`_LD2N_FindCopy@12` ret 12、`_LD2N_Wipe@8` ret 8；正常路徑 ESP 和非揮發暫存器都保留。`@__security_check_cookie@4` 之後若是 nop／int3／下一個函式開頭，視為 noreturn。
- `build_m063_lab.py`（只限實驗室）：在記憶體裡從 m045 建 inert＋enabled，只輸出 JSON。
- `static_verify_m063a.summary.json`：reviewed catalog、mode 2 與 0 的 hash 和計數。
- `test_m063.py`：20 項。

## 實驗室結果（m045 為底，reviewed catalog，hash 可重現）
| | mode 2 | mode 0 |
|---|---|---|
| inert sha256 | `757c8121e7c8…` | `b47d611b59c6…` |
| enabled sha256 | `9cc6a04ae9f0…` | `b738d405df61…` |
| inert→enabled 改動 bytes | 228 | 228 |

- 槽：NamePair `0xae3a10`、ListInsert `0xae47e0`、NameTextOut `0xae50d0`；`.ld2t` 程式範圍 `0xae3000..0xae53f5`。槽位移 0／3008／6720，長度 3008／3700／2485。
- 計數：pair5 25、tail8 1、清單 18。
- 靜態驗證（兩個 mode 都通過）：
  - m062 `build_v3_lab.verify` 全套：hook stub、18 個清單點、物件稽核、fixup、綁定目標、間接呼叫、checksum、import；
  - NameTextOut fixup 32 個，全部落在共用綁定；
  - 26 個改寫窗用 capstone 反組譯：新指令正確，後續指令和原本相同，R2 在改寫點和 call 之間沒有被寫，正好 4 個 push；
  - `.text` 的 rel32 掃描、5 個函式的線性反組譯、絕對 DWORD 掃描，都沒有東西跳進或指向改寫窗內部；
  - pefile checksum 正確；新增 import 和 m062 相同，沒有新增。
- `lab_preview`（2343 列）mode 2 也通過（enabled `d11f7ab53818…`，只在實驗室跑，不入庫）。

## 測試
- `test_m063.py` 20 項：
  - 合成測試 13 項：用一般 x86 編碼重建，編碼的 sha8 和摘要一致，不含遊戲 bytes。
  - clang 預演 1 項：沒有 ziglang 就 skip。
  - 實驗室 3 項：需要授權輸入，否則 skip。
  - 實驗室 20 項全過；公開倉庫裡是 17 過、3 skip（沒有 ziglang 時 16 過、4 skip）。

## m063b 之前的阻礙
1. `name_textout_v3.cpp` 要在 Win11 用 MSVC 編譯一次，鎖定 sha256（`TEXTOUT_OBJECT_SHA256`），再用 `audit_name_textout.py` 稽核 MSVC 輸出。這一輪的 clang 預演物件**不能**鎖定或打包。
2. 隊伍面板中文名的寬度和重疊要在實機觀察（TextOutW 的寬度和原本的 CP932 不同）。
3. CB_INSERTSTRING 兩點（0x46e73a、0x47db6a）：ListInsertV3 mode 2 不會把 combobox 切成 Unicode，W→ANSI 可能顯示 `?`，觀察時要特別看。
4. 名字譯稿要有 `human_reviewed` 才會進 `reviewed` catalog。目前 reviewed 的 264 列只有 m051 道具，冒險者名在實機上還不會變。
5. 延後項目（PLAN §6）：複合清單 4 點、複合標題 4 點、SetDlgItemText／SetWindowText 5 點、句子內的名字。

## 重跑
```bash
python3 research/m063/test_m063.py                                    # 合成測試
~/venv-ld2/bin/python -I -B research/m063/build_m063_lab.py > x.json  # 只限實驗室；需要 m045、MSVC v3 物件、ziglang
```
