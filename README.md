# MovieBox Desktop App

Independent Windows client · Preview 0.10.0 · Installed app name: **MovieBox**

A local Windows reconstruction with a native Qt interface and native video player.
Runs without Android, an emulator, or an embedded MovieBox website.

Launch `MovieBox.exe` from its folder. Keep the `_internal` directory beside it.

## Download and install

[**Download Windows setup EXE**](https://github.com/emransm877/moviebox-desktop/releases/latest/download/MovieBox-Setup-0.10.0-windows-x64.exe)

Run the setup EXE to install the complete application, Start menu shortcut and
optional Desktop shortcut. Python and administrator access are not required.
Uninstall through Windows Settings; your library/history remain in your user data
directory. The installed application and shortcuts are named **MovieBox**.

A [portable ZIP](https://github.com/emransm877/moviebox-desktop/releases/tag/v0.10.0)
is also available. Extract it completely and launch `MovieBox/MovieBox.exe`;
keep `_internal` beside that executable.

The installer requires Windows 10 version 1809 or later on an x64-compatible
system. Native playback was exercised on Windows 11 x64; Windows 10 and ARM
emulation are not separately certified. This is not a macOS, Linux or 32-bit
Windows package. The preview is not Authenticode-signed; SHA-256 files accompany
the downloads. Media availability still depends on the upstream service.

## Included

- Live catalog, categories, database search suggestions, movie details and season/episode buttons for series.
- Separate full Movies and TV Shows catalogues with live server pagination;
  combine genre, year, country, language/edition, sorting and minimum-rating filters.
- Prepared playback on title pages, click-to-seek and keyboard navigation.
- Native video playback, borderless fullscreen (F11 or double-click), mouse-revealed controls, volume and available audio tracks.
- Auto quality and manual selection among streams the service makes available.
- A visible audio-language selector for embedded tracks and dubbed editions,
  preserving position and paused state when switching between matching cuts.
- Automatic online subtitles, a persistent per-episode subtitle cache, local SRT/WebVTT files, and subtitle timing adjustment.
- My list, per-episode playback resume, next episode and optional autoplay.
- Atomic library saves, a recovery copy and merging across app instances protect
  My list and progress from being overwritten by an idle second window.
- Optional GitHub update notices with Download, Later, Skip this version and an
  opt-out in Settings; no automatic installation or compulsory updates.
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
.\.venv\Scripts\python.exe -m unittest test_service test_transport test_native_regressions test_native_captions test_subtitle_store test_audio_options test_library_store test_release_updates test_artwork test_browse_filters
```

Run `verify_upgrade.py`, `verify_subtitle_fix.py` or `verify_audio.py` with the
virtual-environment Python for opt-in live playback/input checks. These contact
the upstream service and use isolated verification data. Run `./build.ps1` in
PowerShell to rebuild the Windows executable and dependency notices.
To build the setup EXE, install Inno Setup 7 and run `build-installer.ps1`, passing
`-Compiler` with the path to `ISCC.exe` if it is not detected automatically.

The published source excludes local research, account data and captured runtime
responses. Sixty-two offline tests cover service transport, subtitle handling and
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

## Themes and latest titles

Settings offers five persistent themes with matching MovieBox logos. Home rotates up to 100 latest movies and TV shows, with Previous/Next/Pause and active-title Watch/More info actions. Existing features remain available. See [theme and spotlight behavior](docs/THEMES_AND_SPOTLIGHT.md).

## Catalogue cache and Continue watching

Movies/TV Shows restore their cached pages and position immediately. After five minutes, the app checks for new results in the background; Apply filters can refresh manually. In Continue watching choose **Select titles**, select one/several or **Select all**, then **Remove selected**. **Undo removal** restores the last batch during the current session. My list is preserved. See [details](docs/CACHE_AND_HISTORY.md).
