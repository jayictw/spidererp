$ErrorActionPreference = "Stop"

$Py = "F:\Jay_ic_tw\fara\.venv2\Scripts\python.exe"
$TaskScript = "F:\Jay_ic_tw\scripts\st0306_st_task.py"
$Db = "F:\Jay_ic_tw\sol.db"
$Xlsx = "F:\Jay_ic_tw\data\parts_pricing_missing_only.xlsx"
$OutDir = "F:\Jay_ic_tw\data"
$FailedOut = "F:\Jay_ic_tw\data\parts_pricing_failed_models_latest.txt"
$Cdp = "http://127.0.0.1:9222"

# Build input xlsx from parts_pricing where st_official_price_usd is NULL
@'
import sqlite3
from pathlib import Path
import openpyxl

db = Path(r"F:/Jay_ic_tw/sol.db")
xlsx = Path(r"F:/Jay_ic_tw/data/parts_pricing_missing_only.xlsx")

conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute(
    """
    SELECT DISTINCT UPPER(TRIM(model))
    FROM parts_pricing
    WHERE model IS NOT NULL
      AND TRIM(model) <> ''
      AND st_official_price_usd IS NULL
    ORDER BY UPPER(TRIM(model))
    """
)
models = [r[0] for r in cur.fetchall() if r and r[0]]
conn.close()

wb = openpyxl.Workbook()
ws = wb.active
ws["A1"] = "鍨嬪彿"
for i, m in enumerate(models, start=2):
    ws.cell(row=i, column=1, value=m)
wb.save(xlsx)
print(f"missing_models={len(models)}")
print(f"xlsx={xlsx}")
'@ | & $Py -

# Run crawl task (3 min per model)
& $Py -u $TaskScript `
  --xlsx $Xlsx `
  --output-dir $OutDir `
  --max-per-hour 30 `
  --start-jitter-max-seconds 0 `
  --retries 1 `
  --goto-timeout-seconds 180 `
  --connect-existing-chrome `
  --cdp-endpoint $Cdp `
  --close-tab-after-each `
  --max-consecutive-errors 10 `
  --failed-models-out $FailedOut `
  --resume-state-file "F:/Jay_ic_tw/data/parts_pricing_resume_state.json" `
  --lock-file "F:/Jay_ic_tw/data/parts_pricing_task.lock"

