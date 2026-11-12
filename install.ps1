param([string]$SourceDirectory = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
$sourceExe = Join-Path $SourceDirectory 'MovieBox.exe'
if (-not (Test-Path -LiteralPath $sourceExe)) { throw 'Extract the complete release ZIP first, then run install.ps1 beside MovieBox.exe.' }
$destination = Join-Path $env:LOCALAPPDATA 'Programs\MovieBox Desktop'
$targetExe = Join-Path $destination 'MovieBox.exe'
foreach ($runningApp in @(Get-Process MovieBox -ErrorAction SilentlyContinue)) {
    if ($runningApp.Path -eq $targetExe) {
        $null = $runningApp.CloseMainWindow()
        if (-not $runningApp.WaitForExit(8000)) { throw 'MovieBox is still closing. Try again after it exits.' }
    }
}
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Get-ChildItem -LiteralPath $SourceDirectory | Copy-Item -Destination $destination -Recurse -Force
$shell = New-Object -ComObject WScript.Shell
$shortcutPaths = @((Join-Path ([Environment]::GetFolderPath('Desktop')) 'MovieBox.lnk'), (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs\MovieBox.lnk'))
foreach ($shortcutPath in $shortcutPaths) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $targetExe
    $shortcut.WorkingDirectory = $destination
    $shortcut.IconLocation = "$targetExe,0"
    $shortcut.Description = 'MovieBox'
    $shortcut.Save()
}
Write-Output 'MovieBox installed. Your saved library and account data are preserved.'
