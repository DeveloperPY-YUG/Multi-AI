# Creates a shortcut pointing at this installed/unchanged portable app folder.
$ErrorActionPreference = 'Stop'
$exe = Join-Path $PSScriptRoot 'Multi-AI.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw 'Multi-AI.exe was not found. Extract the Windows release ZIP first.'
}
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
$shortcutFile = Join-Path $desktop 'MULTI-AI.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutFile)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.IconLocation = "$exe,0"
$shortcut.Description = 'MULTI-AI v1.0.0 | MADE BY YUG'
$shortcut.Save()
Write-Host "Desktop shortcut created: $shortcutFile"
