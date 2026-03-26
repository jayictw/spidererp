# Release Note（v0.2 RC）

## 基本資訊
- 版本：`v0.2.0-rc1`
- 日期：`2026-03-25`
- 發布負責人：`<name>`
- Commit / Tag：`v0.2.0-rc1`

## 本次範圍
- Alembic baseline + v0.2 delta migration
- 四列表 API 統一 `data.items + data.meta`
- 四頁模板契約對齊（filter/sort/pagination）
- dedupe v1 落地（含 mark_duplicate guard / 冪等 / reason 前綴）
- sample trace API + samples trace 視圖最小接線

## Migration 驗證
### 預設 DB 驗證
- 結果：`fail`
- 現象：`table jobs already exists`
- 原因：目前 `DATABASE_URL` 指向非空庫，與 baseline migration 的空庫前提不符
- 判定：符合預期風險，非 migration 腳本本身缺陷

### 空庫 Dry Run 驗證
- `DATABASE_URL`：`sqlite:///./rc_dryrun_empty.db`
- `upgrade head`：`pass`
- `current`：`0002_v02_delta_lists_dedupe_trace (head)`
- 預期 head revision：`0002_v02_delta_lists_dedupe_trace`

## Smoke Matrix 結果
- migration smoke：`pass`
- API smoke：`pass`
- page smoke：`pass`
- dedupe smoke：`pass`
- trace smoke：`pass`
- 全綠定義：無 fail / error

### 執行摘要
- 命令：migration/API/page/dedupe/trace 相關測試一次跑完
- 結果：`22 passed in 16.06s`

## 資料相容性
- 本版本以 Alembic migration 為唯一 schema 來源
- 不支援舊版 `create_all` 直接升級
- 既有資料庫建議：
  - 先 backup
  - 視情況使用 `stamp 0001_baseline` 後再 `upgrade head`

## 回滾提示
> 注意：部分 schema 變更（例如新增欄位、索引）可能無法完全還原資料狀態，回滾前請確認已有備份。

## 已知限制（非阻塞）
- dedupe 仍為 v1 保守策略，尚未引入 content hash / 多策略回放
- trace 目前僅提供單筆 sample 的最小追溯聚合，不含跨 sample 圖狀分析
- 既有非空庫若未先 backup / stamp baseline，直接執行 baseline migration 會失敗

## 最終判定
- RC 可發布：Yes
- 判定依據：空庫 migration 驗證成功，`alembic current` 對齊 head revision，RC smoke 全綠（`22 passed in 16.06s`），無阻塞問題
