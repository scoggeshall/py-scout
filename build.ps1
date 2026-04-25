Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot

try {
    Write-Host "Building py-scout.exe with PyInstaller..."

    py -m PyInstaller `
        --onefile `
        --name py-scout `
        --windowed `
        --clean `
        py-scout.py

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE."
    }

    Write-Host "Build complete: dist\py-scout.exe"
}
finally {
    Pop-Location
}
