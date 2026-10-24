$ErrorActionPreference = "Stop"

# All paths are derived from this script's location (no hard-coded drives).
#   $PSScriptRoot = <project>/aigc_web/perf
$perfDir = $PSScriptRoot

# JMeter binary: $env:JMETER_BIN first, then jmeter on PATH, then a local default.
$jmeter = $null
if ($env:JMETER_BIN) {
  $jmeter = $env:JMETER_BIN
} elseif (Get-Command jmeter -ErrorAction SilentlyContinue) {
  $jmeter = (Get-Command jmeter).Source
} else {
  $jmeter = "C:\apache-jmeter-5.6.3\bin\jmeter.bat"
}
if (!(Test-Path $jmeter)) {
  Write-Error "JMeter not found. Set `$env:JMETER_BIN to jmeter.bat or install JMeter. Tried: $jmeter"
}

$plan = "homepage"
if ($args.Count -gt 0) { $plan = $args[0] }

if ($plan -eq "detect-page") {
  Write-Host "Running detect page only load test (GET /detect)..."
  & $jmeter -n `
    -t (Join-Path $perfDir "detect_page_only_load_test.jmx") `
    -l (Join-Path $perfDir "results_detect_page.jtl") `
    -e -o (Join-Path $perfDir "report_detect_page")
  Write-Host "Done. Open: $(Join-Path $perfDir 'report_detect_page/index.html')"
} else {
  Write-Host "Running homepage load test (GET /login)..."
  & $jmeter -n `
    -t (Join-Path $perfDir "homepage_load_test.jmx") `
    -l (Join-Path $perfDir "results.jtl") `
    -e -o (Join-Path $perfDir "report")
  Write-Host "Done. Open: $(Join-Path $perfDir 'report/index.html')"
}
