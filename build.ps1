Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot

try {
    foreach ($path in @(".\build", ".\dist")) {
        if (Test-Path $path) {
            Remove-Item -LiteralPath $path -Recurse -Force
        }
    }

    Write-Host "Building single executable: dist\pyscout.exe"

    py -m PyInstaller `
        --clean `
        --noconfirm `
        .\pyscout.spec

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE."
    }

    Write-Host "Build complete:"
    Write-Host "  dist\pyscout.exe"
}
finally {
    Pop-Location
}
