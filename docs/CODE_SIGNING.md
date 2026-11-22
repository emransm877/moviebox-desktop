# Code signing policy

Windows 0.10.4 uses the existing local code-signing identity
`CN=Emran Hossain (MovieBox Local Test)` for the application and installer.
The certificate is self-signed, not publicly trusted. Windows can therefore still
show a publisher or SmartScreen warning. Signing does not grant Windows trust or
confirm ownership of third-party branding or content.

The public certificate fingerprint is
`E61361C8EA5808607C019A75C5C58B815AAA6A51` (SHA-1 certificate thumbprint).
Both application and installer carry SHA-256 Authenticode signatures and RFC3161
timestamps. CMS signature and PE-content digest checks passed for the staged files.
Release SHA-256 files identify the exact downloadable bytes. Do not import the
certificate into trusted roots or disable device security to suppress warnings.
No private signing key is distributed.

SignPath Foundation received the application on 21 November 2026; provider
approval and validated signing access remain pending. Existing older release
assets are retained unchanged.

The maintainer is [Emran Hossain](https://github.com/emransm877). Public signing
will cover this repository's independently built MovieBox.exe and installer.
Third-party binaries retain their own licenses and signatures. Android APKs and
Samsung TV certificates are separate and cannot establish Windows trust.

## Self-signed preview

A separate [0.10.3 self-signed preview](https://github.com/emransm877/moviebox-desktop/releases/tag/v0.10.3-selfsigned.1) is published at the maintainer's request. It signs the original 0.10.3 MovieBox.exe before building and signing a separate installer; a portable ZIP includes the signed launcher. This historical packaging preview contains the older 0.10.3 application; the current 0.10.4 release contains the subsequent application changes.

Both EXE signatures use SHA-256 and DigiCert RFC3161 timestamps. Independent CMS signature and Authenticode PE-digest checks passed. Windows signature verification reports an untrusted root, as expected for a self-signed publisher certificate. No publicly trusted publisher identity has been issued.

- Included: installer, portable ZIP, public `.cer`, SHA-256 checksum files, usage notes and cryptographic-integrity evidence.
- Excluded: private key, account credentials and any instruction to bypass security. The private key is non-exportable in the maintainer's Windows Personal certificate store.
- Do not add this certificate to Trusted Root Certification Authorities or Trusted Publishers to suppress warnings. Self-signing does not provide public Windows trust or guarantee SmartScreen reputation.
- Existing stable assets remain byte-for-byte unchanged. This prerelease does not replace `releases/latest` or trigger stable-only update reminders.
- The trusted-release signing helper below continues to reject self-signed certificates. SignPath approval is still pending.

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
The current local signature does not provide public Windows trust. A future
validated signature requires provider approval and the maintainer's signing
account; source changes alone cannot supply that trust.
