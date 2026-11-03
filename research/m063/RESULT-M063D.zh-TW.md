# RESULT M063D — v4 啟用驗收（Win11，Mode 2 lab_preview）

> production_can_apply = false；release_approved = false。本結果僅為實驗室驗收紀錄。

## 摘要
- 模式：Mode 2 `lab_preview`；inert sha `c796bc12…6e37`；enabled sha `240ab04d…4121`
- 步驟 P / L1 / E / L2 / G 皆完成；`finalized: true`；原安裝未變動
- L1、L2 皆 soft-warn exit1；無 crash dump
- 證據 zip sha256 `53399e09d4e05c2f9e6515a9127e40a42dd44febe053bdccdbe762eb0db1e151`（zip／PNG 不入庫，見 `enable-v4-run1/EVIDENCE-ZIP.sha256.txt`）

## 觀察
- 武器店購買清單顯示「波刃短劍」（635G）
- 酒館冒險者名稱繁中完整
- 委託資訊清單為空，無法判定人名 vs 道具
- 訓練所 Static 1024 仍為 cp932 亂碼（未譯字串，待後續處理）
- 未進行購買／販賣／招募／住宿／存檔

## 自動測試 runs
- load-shop-item-001、load-shop-weapon-002、load-inn-tavern-quest-004（report 見 `enable-v4-run1/`）

## 其他
- #25 冒險者譯名升級 delta 已另行審核通過，屬 PR #25，不併入本 PR。
