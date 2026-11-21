# Code signing policy

The currently published Windows 0.10.3 installer and portable application are
unsigned. The SignPath Foundation application was submitted on 21 November 2026;
the official form confirmed receipt. Approval and signing access are pending.
A checksum verifies file identity, not a
Windows publisher signature. Existing release assets will not be silently replaced.

The maintainer is [Emran Hossain](https://github.com/emransm877). Public signing
will cover this repository's independently built MovieBox.exe and installer.
Third-party binaries retain their own licenses and signatures. Android APKs and
Samsung TV certificates are separate and cannot establish Windows trust.

## Signing application status

Application submitted: **21 November 2026**. The official SignPath form displayed
“Form submitted” and “Thank you, we'll be in touch soon.” This confirms submission,
not acceptance, certificate issuance or a signed Windows release. No duplicate
application should be sent while that review is pending.

## Obtain a validated signing identity

For this open-source project, review the
[SignPath Foundation application](https://signpath.org/) and
[eligibility conditions](https://signpath.org/terms). Acceptance is subject to
their review, including source/dependency licensing, build provenance, project
roles and account security. Do not claim a partnership, approval or Foundation
signature before approval and actual signing. The prepared
[application brief](SIGNING_APPLICATION.md) describes the requested scope.

Alternatively, obtain a publicly trusted code-signing certificate/service that
supports your country and identity. Microsoft documents
[Windows code-signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options).
Azure Artifact Signing's individual public-trust onboarding is currently limited
to the US and Canada; do not enter an incorrect location or identity to qualify.
Use the provider's approved secure-key workflow, not a self-signed certificate.

## Maintainer setup

1. Sign in to the selected provider yourself and complete any required identity,
   repository-ownership and account-security checks. Keep credentials out of Git,
   issue reports and chat.
2. For a certificate exposed through the Windows certificate store or hardware
   provider, install Microsoft's Windows SDK Signing Tools. Configure the
   certificate provider locally. Never export a hardware-managed key for CI.
3. Set `MOVIEBOX_WINDOWS_CERT_THUMBPRINT` to the approved public certificate's
   thumbprint. This is an identifier, not the private key.
4. Build the reviewed source, then sign the app **before** packaging it:

   ```powershell
   ./build.ps1
   ./tools/sign-windows.ps1 -Artifact ./dist/MovieBox/MovieBox.exe
   ./build-installer.ps1
   ./tools/sign-windows.ps1 -Artifact ./dist/installer/MovieBox-Setup-VERSION-windows-x64.exe
   ```

   Replace `VERSION` with the actual source version. For a cloud signing service,
   use its reviewed integration instead of exporting keys to run this local path.
5. Verify both signatures with `-VerifyOnly`, create the portable ZIP from the
   signed application, and compute checksums **after** all signing/packaging.
6. Test the exact signed EXE, installer and ZIP. Publish them under a new version
   after review. Update release.json, README, installer metadata, release notes
   and the website together, once the actual assets are public.

The helper requires a non-self-signed code-signing certificate, a trusted chain,
an accessible private key, SHA-256 and a timestamp; verification fails closed.
It does not create certificates, install trusted roots, disable security tools or
publish releases. Signing does not guarantee an immediate absence of SmartScreen
warnings: reputation and Windows policy are separate checks.

## Current boundary

No validated Windows signing identity is available on the maintainer's PC yet.
The current published downloads remain labelled unsigned until a new, verified
signed release is available. The first onboarding/signing step requires the
maintainer's provider account; source changes alone cannot supply that trust.
