# Release process

There are two separate versions in `release.json`: the source version under
development and the version currently available to download. They may differ.
README download links must describe the published version until a new release
has actually been reviewed and published.

## Before proposing a release

1. Run `python -m unittest discover -p "test_*.py"` and `python tools/check_release.py`.
2. Build the application and installer using the pinned dependencies and compiler
   validation in CI. Keep signing material outside Git. Do not change signing or
   installation identity without an explicit migration plan.
3. Test the built package in isolated user data, not just imported Python source:
   fresh start; existing-library upgrade; actual restart; My list and progress;
   playback; pause/resume; repeated seeking; subtitles; audio; quality changes;
   navigation during a healthy stream and a stalled stream; exit and recovery.
4. Record the artifact SHA-256, source commit, Windows version, installer/ZIP and
   each scenario's result. A check not performed must be labelled unverified.
   Synthetic media tests do not certify every live source or device.
5. Prepare release notes with changes, compatibility, known issues and migration
   guidance. Generate SHA-256 files for each application artifact.
6. Discuss the concrete release candidate with the maintainer before publication.
   CI upload artifacts are test outputs, not automatically published releases.

## Publication is a separate manual step

No workflow in this repository creates a GitHub Release. After the maintainer
approves the candidate, publish the exact reviewed files, verify their public
download names and checksums, then update `published_version`, `assets` and the
README together. Run `python tools/check_release.py --online` or the manual
**Review published download metadata** workflow.

Never replace an existing release asset silently: asset IDs and download counters
can change, and users must be able to identify the build they installed.

## What CI currently establishes

CI runs offline regressions, validates source/documented version metadata, builds
the native application and produces a setup EXE. It does not replace the package
acceptance checklist above or real-device checks. Test coverage must be described
by its actual scope, not as universal reliability.
