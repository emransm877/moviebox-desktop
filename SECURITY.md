# Security

This project is a preview. Security fixes target the current source version.

For a vulnerability involving credentials or a working exploit, use GitHub's
private vulnerability reporting on the repository when enabled. Do not put
tokens, personal information, signing keys, or complete captures in a public issue.

Desktop account sessions are protected with Windows DPAPI. The local media bridge
binds to loopback, requires an unpredictable capability URL, and serves only
sources explicitly registered by the application.

The shared API protocol constant in `native_mobile.py` is public client metadata
from the supplied APK. It is not an account credential or application signing key.
