$ErrorActionPreference = "Stop"

$Py = "F:\Jay_ic_tw\fara\.venv2\Scripts\python.exe"
$Script = "F:\Jay_ic_tw\scripts\st0306_st_task.py"
$Xlsx = "C:\Users\PC\Desktop\ST0306.xlsx"
$OutDir = "F:\Jay_ic_tw\data"
$FailedOut = "F:\Jay_ic_tw\data\st0306_failed_models_latest.txt"
$Db = "F:\Jay_ic_tw\sol.db"
$Cdp = "http://127.0.0.1:9222"

& $Py -u $Script `
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
  --max-consecutive-errors 10 `
  --failed-models-out $FailedOut

