# Build an offline-portable Windows EXE on Windows x64 using PyInstaller.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function RunChecked([string]$program, [string[]]$arguments) {
    & $program @arguments
    if ($LASTEXITCODE -ne 0) { throw "$program failed with exit code $LASTEXITCODE" }
}

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
    throw 'A real Windows EXE must be built on Windows. See the GitHub Actions workflow.'
}
RunChecked python @('-m', 'pip', 'install', '-r', 'requirements.txt', 'pyinstaller>=6.16,<7')
RunChecked python @('-m', 'unittest', 'tests.test_providers', 'tests.test_dynamic_providers', 'tests.test_engine', 'tests.test_model_visibility', 'tests.test_release_migration', '-v')
RunChecked python @('-m', 'PyInstaller', '--noconfirm', '--clean', 'Multi-AI.spec')
$dist = Join-Path $PSScriptRoot 'dist/MULTI-AI'
if (-not (Test-Path -LiteralPath (Join-Path $dist 'Multi-AI.exe'))) {
    throw 'PyInstaller did not produce Multi-AI.exe.'
}
Copy-Item 'scripts/Create-Desktop-Shortcut.ps1' $dist -Force
Copy-Item 'scripts/Install-MULTI-AI.cmd' $dist -Force
Copy-Item 'README-WINDOWS.md' $dist -Force
New-Item -Force -ItemType Directory 'release' | Out-Null
$zip = Join-Path $PSScriptRoot 'release/MULTI-AI-v1.0.0-Windows.zip'
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $dist -DestinationPath $zip -CompressionLevel Optimal
Write-Host "Release created: $zip"
