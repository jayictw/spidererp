$ErrorActionPreference = "Stop"

$Py = "F:\Jay_ic_tw\fara\.venv2\Scripts\python.exe"
$Script = "F:\Jay_ic_tw\scripts\st0306_st_task.py"
$Xlsx = "C:\Users\PC\Desktop\ST0306.xlsx"
$OutDir = "F:\Jay_ic_tw\data"
$ChromeProfile = "C:\Users\PC\AppData\Local\Google\Chrome\User Data\Profile 2"

if (-not (Test-Path $Py)) {
  throw "Python not found: $Py"
}
if (-not (Test-Path $Script)) {
  throw "Script not found: $Script"
}
if (-not (Test-Path $Xlsx)) {
  throw "XLSX not found: $Xlsx"
}

& $Py $Script `
  --xlsx $Xlsx `
  --output-dir $OutDir `
  --max-per-hour 45 `
  --start-jitter-max-seconds 1800 `
  --use-cookie-profile `
  --chrome-profile-dir $ChromeProfile
