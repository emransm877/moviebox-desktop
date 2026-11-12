# MovieBox Desktop App

Independent Windows client · Preview 0.4.0 · Installed app name: **MovieBox**

A local Windows reconstruction with a native Qt interface and native video player.
Runs without Android, an emulator, or an embedded MovieBox website.

Launch `MovieBox.exe` from its folder. Keep the `_internal` directory beside it.

## Download and install

Download `MovieBox-Desktop-0.4.0-windows-x64.zip` from the
[releases page](https://github.com/emransm877/moviebox-desktop/releases).
Extract the complete ZIP, open the `MovieBox` folder and launch `MovieBox.exe`.
For a per-user installation and Desktop/Start menu shortcuts, run `install.ps1`
from that extracted folder in PowerShell. Administrator access is not required.
The installed application and shortcuts are named **MovieBox**.

This preview targets Windows 11 x64. It is not Authenticode-signed. Release
SHA-256 checksums are supplied alongside the ZIP.

## Included

- Live catalog, categories, database search suggestions, movie details and season/episode buttons for series.
- Prepared playback on title pages, click-to-seek and keyboard navigation.
- Native video playback, borderless fullscreen (F11 or double-click), mouse-revealed controls, volume and available audio tracks.
- Auto quality and manual selection among streams the service makes available.
- A visible audio-language selector for embedded tracks and dubbed editions,
  preserving position and paused state when switching between matching cuts.
- Automatic online subtitles, a persistent per-episode subtitle cache, local SRT/WebVTT files, and subtitle timing adjustment.
- My list, per-episode playback resume, next episode and optional autoplay.
- Background downloads, pause, and partial-file resume when downloading the same selection again.
- Local file playback and disk artwork caching.
- Optional native QR login, confirmed in the MovieBox app on your phone. Desktop sessions are protected with Windows DPAPI.
- Original MovieBox branding, a Fluent-inspired Windows shell, native rounded window chrome and Snap support, dark/light/system appearance, and a compact layout.

## Current scope

MovieBox streaming is verified on a full-length episode using its 1080 quality tier,
including native decoding, seeking, online subtitle discovery and local resume.
Widescreen source files may have cropped black bars; the provider's 1080 tier does
not necessarily encode 1080 vertical picture pixels. Available quality varies by title.

This is a preview, not a claim of complete Android feature parity. QR ticket creation
is verified; a user-confirmed account login and Android history sync are not yet verified. Access restrictions and available
resolutions come from MovieBox. A visible resolution label alone is not proof of
working playback; the player checks the decoded video and rejects short placeholders.

Your phone's app and data are separate. Local lists and artwork are stored in
`%LOCALAPPDATA%\MovieBoxDesktop`. Downloads are saved to the location you select.
No forced app update mechanism is included in this Windows build.

## Source and verification

With Python 3.12 installed, run from the repository directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Run the focused offline checks with:

```powershell
.\.venv\Scripts\python.exe -m unittest test_service test_transport test_native_regressions test_native_captions test_subtitle_store test_audio_options
```

Run `verify_upgrade.py`, `verify_subtitle_fix.py` or `verify_audio.py` with the
virtual-environment Python for opt-in live playback/input checks. These contact
the upstream service and use isolated verification data. Run `./build.ps1` in
PowerShell to rebuild the Windows executable and dependency notices.

The published source excludes local research, account data and captured runtime
responses. Thirty offline tests cover service transport, subtitle handling and
audio selection. Local native-player checks exercised 1080-tier playback,
subtitles, seeking, audio switching and resume; these are bounded checks rather
than certification of every title or network condition.

## Related projects and licensing

- [Android patch source](https://github.com/emransm877/moviebox-android)
- [Samsung Tizen TV client](https://github.com/emransm877/moviebox-tizen)

Maintained by [Emran Hossain](https://github.com/emransm877). Independent project;
not affiliated with MovieBox, Samsung or Microsoft. Original project code is MIT.
Names, artwork and dependencies retain their respective owners' rights. See
`LICENSE`, `THIRD_PARTY_NOTICES.txt`, `CONTRIBUTING.md` and `SECURITY.md`.
