param([string]$Compiler = '')
$ErrorActionPreference = 'Stop'
if (-not $Compiler) {
    $compilerCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($compilerCommand) { $Compiler = $compilerCommand.Source }
    else {
        foreach ($compilerCandidate in @("$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe", "$env:ProgramFiles\Inno Setup 7\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe")) {
            if (Test-Path -LiteralPath $compilerCandidate) { $Compiler = $compilerCandidate; break }
        }
    }
}
if (-not $Compiler -or -not (Test-Path -LiteralPath $Compiler)) { throw 'Install Inno Setup 7, then supply -Compiler with the ISCC.exe path.' }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'dist\MovieBox\MovieBox.exe'))) { throw 'Run build.ps1 first.' }
& $Compiler (Join-Path $PSScriptRoot 'installer.iss')
if ($LASTEXITCODE -ne 0) { throw 'MovieBox installer build failed.' }
