Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot

try {
    Write-Host "Building GUI executable: dist\py-scout.exe"

    py -m PyInstaller `
        --onefile `
        --name py-scout `
        --windowed `
        --clean `
        py-scout.py

    if ($LASTEXITCODE -ne 0) {
        throw "GUI PyInstaller build failed with exit code $LASTEXITCODE."
    }

    Write-Host "Building CLI executable: dist\py-scout-cli.exe"

    py -m PyInstaller `
        --onefile `
        --name py-scout-cli `
        --clean `
        py-scout.py

    if ($LASTEXITCODE -ne 0) {
        throw "CLI PyInstaller build failed with exit code $LASTEXITCODE."
    }

    Write-Host "Build complete:"
    Write-Host "  dist\py-scout.exe"
    Write-Host "  dist\py-scout-cli.exe"
}
finally {
    Pop-Location
}
