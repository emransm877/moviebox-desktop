# Prepared Windows signing application brief

Draft for the maintainer to review and submit. **Not submitted or approved.**

- Project: MovieBox Desktop App; installed application name: MovieBox.
- Repository: https://github.com/emransm877/moviebox-desktop
- Maintainer: Emran Hossain / GitHub emransm877.
- Source license: MIT; dependency notices and license files accompany packages.
- Purpose: independent Windows media client with catalogue browsing, native
  playback, subtitles, audio selection, saved lists, progress and local downloads.
- Signing scope: the project's own Windows application executable and setup EXE.
- Build provenance: GitHub-hosted Windows CI, pinned dependencies, validated
  installer compiler, reviewed source commit and recorded artifact hashes.
- Release controls: maintainer review, no automatic public release, exact signed
  artifacts verified before publication, new versions rather than silent replacement.
- Policy: [Code signing policy](CODE_SIGNING.md).
- Privacy/network disclosure: [Privacy and network behavior](PRIVACY.md).
- Third-party rights: project source licensing does not grant rights to upstream
  MovieBox trademarks, artwork, content or proprietary applications. No upstream
  Android APK or modified proprietary binary is included in this signing request.
- Network behavior: catalogue/playback requests reach the upstream service;
  optional update checks reach GitHub. Source/license and network disclosures
  require review against the provider's current conditions before submission.

The maintainer must confirm project-role details, account security, dependency
license compliance and any provider-specific fields. This document cannot promise
eligibility or replace the provider's approval.
