$ErrorActionPreference = "Stop"

$Py = "F:\Jay_ic_tw\fara\.venv2\Scripts\python.exe"
$TaskScript = "F:\Jay_ic_tw\scripts\st0306_st_task.py"
$Db = "F:\Jay_ic_tw\sol.db"
$Xlsx = "F:\Jay_ic_tw\data\scope_1306_models.xlsx"
$OutDir = "F:\Jay_ic_tw\data"
$FailedOut = "F:\Jay_ic_tw\data\scope_1306_failed_models_latest.txt"
$IgnoreModels = "F:\Jay_ic_tw\data\scope_1306_ignore_status_not_found.txt"
$Cdp = "http://127.0.0.1:9222"
$Resume = "F:\Jay_ic_tw\data\scope_1306_resume_state.json"
$Lock = "F:\Jay_ic_tw\data\scope_1306_task.lock"

# Build scope xlsx from sol_3233 (1306 target list)
@'
import sqlite3
from pathlib import Path
import openpyxl

db = Path(r"F:/Jay_ic_tw/sol.db")
xlsx = Path(r"F:/Jay_ic_tw/data/scope_1306_models.xlsx")
ignore_file = Path(r"F:/Jay_ic_tw/data/scope_1306_ignore_status_not_found.txt")

conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT * FROM sol_3233")
rows = cur.fetchall()
models = {str(r[0]).strip().upper() for r in rows if r and r[0] and str(r[0]).strip()}
ignore = set()
if ignore_file.exists():
    ignore = {x.strip().upper() for x in ignore_file.read_text(encoding="utf-8").splitlines() if x.strip()}
models = sorted(m for m in models if m not in ignore)
conn.close()

wb = openpyxl.Workbook()
ws = wb.active
ws["A1"] = "型号"
for i, m in enumerate(models, start=2):
    ws.cell(row=i, column=1, value=m)
wb.save(xlsx)
print(f"scope_models={len(models)}")
print(f"ignored_models={len(ignore)}")
print(f"xlsx={xlsx}")
'@ | & $Py -

# Run crawl task on 1306 scope, skip already-priced models from parts_pricing
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
  --skip-existing-st-price `
  --db-path $Db `
  --max-consecutive-errors 25 `
  --failed-models-out $FailedOut `
  --resume-state-file $Resume `
  --lock-file $Lock
