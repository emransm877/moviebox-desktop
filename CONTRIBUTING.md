# Contributing

Use Python 3.12 on Windows for the maintained build. Create a virtual environment
and install `requirements.txt`. Run the offline regression suite before a PR:

```powershell
python -m unittest test_service test_transport test_native_regressions
```

Describe the concrete behavior being fixed, the relevant validation, and any
remaining limitations. Keep UI/network work off the main event loop. Preserve
service access restrictions and do not import phone identities or sessions.

Never commit account tokens, captures, signed media URLs, user libraries, local
signing material, vendor APKs, or generated application folders. Use fixtures
and sanitized summaries for bug reports. Service-dependent GUI tests are manual;
do not add live requests to the default CI test suite.

MovieBox branding and catalog artwork are third-party assets, not MIT-licensed
project artwork. Changes to third-party dependencies must preserve their notices.
