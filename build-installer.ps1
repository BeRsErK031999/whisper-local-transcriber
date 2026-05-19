$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$candidatePaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Users\$env:USERNAME\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
)
$isccPath = $candidatePaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $isccPath) {
    throw "ISCC.exe not found. Checked: $($candidatePaths -join ', ')"
}

& $isccPath "/DMySourceDir=$projectRoot" (Join-Path $projectRoot "installer.iss")
