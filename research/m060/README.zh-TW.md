# m060：記憶體產生器改採 m058 `/EHs` helper（m059 mock 原生通過）

**結果：靜態／記憶體層接受新 helper；仍不建置功能性遊戲 patch，`production_can_apply=false`。**

## 變更內容

- 由 `research/m057/` 複製 `memory_plan.py`、`test_memory_plan.py`、`probe_memory.py`、`verify_readback.py` 到本目錄；**m057 原檔未改**（保留歷史）。
- `memory_plan.OBJECT` 改為唯一接受 m058 `/EHs` helper COFF：
  `5819838a30cddaea51b4914d87ab3971d603de06cd4f6b1e1c94684fa5ac8c92`
  （路徑 `zhTW_lab/runs/m058/compile-only/name_pair.EHs.obj`）。
- 舊 m056 `/EHsc` 物件 `0faa3fe5…71b9c7` 列入 `RETIRED_OBJECTS`，並由測試確認**被拒絕**。
- 仍只接受單一精確 hash；**沒有**繞過／allow-unknown 開關（有測試掃描原始碼確認）。
- 路徑改為相對於本檔推得 LD2 根目錄（`parents[3]`），Windows `<LD2_ROOT>` 與 Linux `/workspace/LD2` 皆可直接跑。
- 測試新增 `M060AcceptanceTests`：新 hash 接受、舊 hash 拒絕、無 bypass、以精確原版＋catalog 跑完整記憶體 plan（缺檔時明確 skip，不臆造 hash）。

## 驗證（Linux，2026-10-28）

| 項目 | 結果 |
|---|---|
| `python -I -B test_memory_plan.py` | 28 tests OK（原 24＋m060 新 4；本機有原版 Ld95.exe，無 skip） |
| `probe_memory.py` | object=`5819838a…ac8c92`、fixups=25、264 rows、`can_apply=false` |
| `verify_readback.py` | 25 fixup 讀回、678 非 fixup bytes 不變、264 catalog rows、原 headers/sections/delay 相同 |
| 原版 `Ld95.exe` | `6c817a…40d5d2`，未變 |

**重點發現：** 重定位後 code 片段 SHA-256 `c08f8b08…0ed9cb5` 與 m057（舊 helper）**完全相同**。`/EHs` 與 `/EHsc` 的差異只在例外 metadata／link-only sections；helper 機器碼、25 個 relocation 與 6 個外部符號一致（與 m058 `helper-EHs-comparison.json` 結論吻合）。

證據：`zhTW_lab/runs/m060/`（`test_memory_plan.txt`、`probe_memory.json`、`verify_readback.json`、`m060-files.sha256`、`completion.json`）。

## 驗收界線（重要）

m059 通過的是**自有 mock harness** 下的原生連結／執行（28 cases、0 failed、1000 次 ABI 迴圈）。它**不等於**：

- 真實遊戲程序內的 MFC 例外路徑／SEH／GS cookie 行為已驗證；
- 字型（TextOutW、CJK 字型 fallback、字寬／截斷）已驗證；
- 存讀檔與「保留原格式、顯示時轉語言」已驗證；
- Windows loader 對新 import／section 的接受度已驗證（本輪仍未生成 PE headers 或 section）。

因此功能性 EXE patch 仍 **NO-GO**；`production_can_apply` 維持 **false**。下一步見 `OBSERVATION-PLAN.zh-TW.md`（僅計畫，需另外授權在可丟棄副本上單次執行）。

本輪無 native、GUI、遊戲、私人存檔、遠端或安裝動作。
