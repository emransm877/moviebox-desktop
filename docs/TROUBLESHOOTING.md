# Troubleshooting MovieBox for Windows

Start by checking which file you downloaded and its release tag. The version on
the source branch can be newer than the published installer. Include the release
tag and **installer or portable ZIP** when reporting a problem.

| Problem | First checks |
| --- | --- |
| README download fails | Use the published [Releases page](https://github.com/emransm877/moviebox-desktop/releases). Source version 0.10.4 is not currently a published download. |
| Portable app will not start | Extract the complete ZIP. Keep `_internal` beside `MovieBox.exe`. Do not run the EXE from inside the ZIP. |
| My list or progress appears missing | Close extra MovieBox windows. Copy `%LOCALAPPDATA%\MovieBoxDesktop` somewhere safe before changing anything. Keep `library.json` and its `.bak` recovery copy; do not delete them to reset the app. |
| Navigation freezes during playback | Record the exact release, Windows version, installer/ZIP, and whether the source was buffering or seeking. Report the steps through the bug form. A source-branch fix is not proof that an older downloaded EXE contains it. |
| Subtitles or audio are missing | Check another episode/title and the available language choices. Subtitle and audio availability comes from the service; not every edition exposes the same tracks. |
| Quality label differs from the picture | A provider's 1080 tier can contain widescreen video with fewer than 1080 picture rows. Availability varies by title; selecting a label cannot create a missing stream. |
| Windows shows a security prompt | The preview is not Authenticode signed. Confirm the official repository URL and compare SHA-256 with the release checksum. Do not disable antivirus or other security protections. |

## Safe bug reports

Use [the bug form](https://github.com/emransm877/moviebox-desktop/issues/new/choose).
Include what happened, what you expected, steps to reproduce, app release, Windows
version, and whether it happens with multiple titles. Crop screenshots to the app.

Never attach account tokens, signed stream URLs, `session.bin`, your complete
library, private logs, phone identifiers or passwords. Report security issues
privately as described in [SECURITY.md](../SECURITY.md).

## Updates and backups

The application offers optional update notices; it does not install updates for
you. Back up the user-data directory before troubleshooting. Updating the EXE
does not require deleting your library. Downloads stay in the locations you chose.
