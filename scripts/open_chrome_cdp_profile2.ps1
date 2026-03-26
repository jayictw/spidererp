$ErrorActionPreference = "Stop"

$ChromeExe = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$UserDataDir = "C:\Users\PC\AppData\Local\Google\Chrome\User Data"
$ProfileDir = "Profile 2"
$Port = 9222

if (-not (Test-Path $ChromeExe)) {
  throw "Chrome not found: $ChromeExe"
}

Start-Process -FilePath $ChromeExe -ArgumentList @(
  "--remote-debugging-port=$Port",
  "--user-data-dir=$UserDataDir",
  "--profile-directory=$ProfileDir"
)
