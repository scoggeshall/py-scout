Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot

try {
    $pyInstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
    if (-not $pyInstaller) {
        Write-Host "PyInstaller is not installed. Run: py -m pip install -r requirements.txt"
        exit 1
    }

    pyinstaller --onefile --name py-scout py-scout.py
}
finally {
    Pop-Location
}
