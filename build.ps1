$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
Push-Location -LiteralPath $projectRoot
try {
    $buildArgs = @('-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed', '--name', 'MovieBox', '--icon', 'assets\app.ico', '--version-file', 'version_info.txt', '--exclude-module', 'PySide6.QtWebEngineCore', '--exclude-module', 'PySide6.QtWebEngineWidgets', '--exclude-module', 'PySide6.QtPdf', '--exclude-module', 'PySide6.QtPdfWidgets', '--add-data', 'assets;assets', 'main.py')
    $buildProcess = Start-Process -FilePath $pythonExe -ArgumentList $buildArgs -WorkingDirectory $projectRoot -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'build-native.stdout.log') -RedirectStandardError (Join-Path $projectRoot 'build-native.stderr.log')
    if ($buildProcess.ExitCode -ne 0) { throw 'Windows build failed. See build-native.stderr.log.' }
    Copy-Item -LiteralPath (Join-Path $projectRoot 'README.md') -Destination (Join-Path $projectRoot 'dist\MovieBox\README.md')
    Copy-Item -LiteralPath (Join-Path $projectRoot 'THIRD_PARTY_NOTICES.txt') -Destination (Join-Path $projectRoot 'dist\MovieBox\THIRD_PARTY_NOTICES.txt')
    foreach ($releaseFile in @('LICENSE','CHANGELOG.md','CONTRIBUTING.md','SECURITY.md','install.ps1')) {
        Copy-Item -LiteralPath (Join-Path $projectRoot $releaseFile) -Destination (Join-Path $projectRoot "dist\MovieBox\$releaseFile")
    }
    Copy-Item -LiteralPath (Join-Path $projectRoot 'docs') -Destination (Join-Path $projectRoot 'dist\MovieBox') -Recurse -Force
    & $pythonExe (Join-Path $projectRoot 'tools\collect_licenses.py')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency license collection failed.' }
    Write-Output 'Built dist\MovieBox\MovieBox.exe'
} finally {
    Pop-Location
}
