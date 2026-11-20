param(
    [Parameter(Mandatory=$true)][string[]]$Artifact,
    [string]$CertificateThumbprint = $env:MOVIEBOX_WINDOWS_CERT_THUMBPRINT,
    [string]$SignTool = '',
    [switch]$VerifyOnly
)
$ErrorActionPreference = 'Stop'
$paths = @($Artifact | ForEach-Object {
    $resolved = (Resolve-Path -LiteralPath $_).Path
    if ([IO.Path]::GetExtension($resolved) -notin @('.exe','.dll','.msi','.msix')) { throw 'Pass individual Windows binaries, not ZIP files.' }
    $resolved
})
if (-not $VerifyOnly) {
    if ($CertificateThumbprint -notmatch '^[A-Fa-f0-9]{40}$') { throw 'A validated Windows signing certificate thumbprint is required. No signing was attempted.' }
    $certificate = Get-Item -LiteralPath "Cert:\CurrentUser\My\$CertificateThumbprint" -ErrorAction Stop
    if (-not $certificate.HasPrivateKey -or $certificate.NotAfter -le (Get-Date) -or $certificate.NotBefore -gt (Get-Date)) { throw 'The certificate must be current and have an accessible private key.' }
    if ($certificate.Subject -eq $certificate.Issuer) { throw 'Self-signed certificates are not accepted for public MovieBox releases.' }
    $ekuExtension = $certificate.Extensions | Where-Object {$_.Oid.Value -eq '2.5.29.37'} | Select-Object -First 1
    $ekuOids = @()
    if ($ekuExtension) {
        $decoded = [Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]::new($ekuExtension, $ekuExtension.Critical)
        $ekuOids = @($decoded.EnhancedKeyUsages | ForEach-Object {$_.Value})
    }
    if ('1.3.6.1.5.5.7.3.3' -notin $ekuOids) { throw 'Certificate is not enabled for code signing.' }
    $chain = [Security.Cryptography.X509Certificates.X509Chain]::new()
    $chain.ChainPolicy.RevocationMode = 'Online'
    try { if (-not $chain.Build($certificate)) { throw 'Certificate chain or revocation validation failed.' } } finally { $chain.Dispose() }
    if (-not $SignTool) {
        $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
        if ($command) { $SignTool = $command.Source }
        else {
            $kits = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
            $candidate = Get-ChildItem -Path (Join-Path $kits '*\x64\signtool.exe') -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
            if ($candidate) { $SignTool = $candidate.FullName }
        }
    }
    if (-not $SignTool -or -not (Test-Path -LiteralPath $SignTool)) { throw 'Install the Microsoft Windows SDK Signing Tools, or pass -SignTool.' }
    if ((Get-AuthenticodeSignature -LiteralPath $SignTool).Status -ne 'Valid') { throw 'Microsoft signing-tool signature could not be verified.' }
    foreach ($path in $paths) {
        & $SignTool sign /sha1 $CertificateThumbprint /s My /fd SHA256 /tr https://timestamp.digicert.com /td SHA256 $path
        if ($LASTEXITCODE -ne 0) { throw "Signing failed: $path" }
    }
}
foreach ($path in $paths) {
    $signature = Get-AuthenticodeSignature -LiteralPath $path
    if ($signature.Status -ne 'Valid') { throw "Authenticode validation failed: $path ($($signature.Status))" }
    if (-not $signature.TimeStamperCertificate) { throw "A trusted timestamp is required: $path" }
    if ($CertificateThumbprint -and $signature.SignerCertificate.Thumbprint -ne $CertificateThumbprint) { throw "Unexpected publisher certificate: $path" }
    [PSCustomObject]@{File=[IO.Path]::GetFileName($path);Status=$signature.Status;Publisher=$signature.SignerCertificate.Subject;Thumbprint=$signature.SignerCertificate.Thumbprint;Timestamped=$true}
}
