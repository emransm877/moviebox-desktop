# Changelog

## 0.10.1 — 2026-11-14

- Restrict the episode Up shortcut to hidden player controls; visible controls and open menus keep normal navigation.
- Compact the season selectors and TV option popup. Align the desktop More menu labels and pad the subtitle timing value.

## 0.10.0 — 2026-11-14

- Put the timeline above one inline control row using the upstream Stremio SVG icons with bundled MIT attribution.
- Keep quality, subtitle and audio choices in accessible icon selectors; keep timing and downloads in More on Windows.
- One Up-arrow press opens the episode panel from the right, including when player controls are hidden.
- Retain series autoplay, resume, fullscreen, subtitle/audio preferences, library and themes.
- See [inline player behavior](docs/INLINE_PLAYER.md).

## 0.9.2 — 2026-11-14

- Use compact icons for player Play/Pause and Seasons & episodes, with accessible names and tooltips. Retain time and seek labels.

## 0.9.1 — 2026-11-14

- Add a desktop in-player season/episode panel, including fullscreen and keyboard selection, without pausing while browsing.

- Remove the permanent Next transport button. Series continue automatically; the near-end Up next card remains. Movies return to details when finished.

## 0.9.0 — 2026-11-14

- Automatic next series episode, including season boundaries; final/unavailable playback returns to details.
- Near-end next-up card without guessing or skipping unknown credits.
- Immediate video/OK playback toggles, refined dropdowns, and TV season/episode drawer.
- TV-only lifted focus and saved theme before first paint.
- Existing library, catalogue cache, themes, audio, subtitles and quality controls retained.
- See [exact behavior and validation limits](docs/PLAYER_BEHAVIOR.md).

## 0.8.1 — 2026-11-14

- Retain the last fully cached page boundary when a long catalogue exceeds the metadata budget. Returning to that view resumes Load more at the first uncached page, without skipping results.

## 0.8.0 — 2026-11-14

- Cache Movies/TV Shows metadata and loaded pages by filters across visits and restarts. Show cached results immediately, check stale data in the background, and preserve position when unchanged.
- Add Continue watching selection mode, single/multiple/all removal and Undo. Remove all episode records belonging to a chosen title, preserve My list, and prevent removed progress from being recreated on close.

- Tighten title details: place actions immediately after the synopsis for movies and after the season selector for TV shows. Remove the desktop's flexible gap and hide the entire unused movie season row.
- Keep existing posters, seasons, episode cards, playback, library and themes intact; use consistent compact spacing on TV too.


## 0.7.0 — 2026-11-14

- Add five live Settings themes: Obsidian Cinema, Orbital, Prism, Aurora and Eclipse. Save the choice across launches; refresh surfaces, focus accents, hero styling and navigation without changing playback or library data.
- Add a shuffled latest movies + TV slideshow, up to 50 of each (100 unique titles), with previous/next/pause, an accurate count, and exact active-title Watch/More info actions.
- Load bounded metadata in the background and only active-slide artwork. Pause automatic rotation while interacting, in other views, during playback or when hidden.
- Preserve the existing catalogue, filters, library, audio, captions, quality, fullscreen, remote/keyboard input and optional update features.


## 0.6.0

- Replace home-feed-only movie/series filtering with separate live Movies and TV
  Shows catalogue channels and real server pagination.
- Add combined genre, year, country, audio/edition, sort and minimum-rating
  selectors, explicit Apply/Reset, keyboard support and per-section preferences.
- Ignore stale catalogue/home callbacks after navigation; preserve saved titles
  and all existing playback, subtitle, audio and update behavior.
- Animate a subtle 160 ms poster focus/hover enlargement and bounded highlight
  without moving the layout or allocating resized pixmaps on every frame.
- Document the remaining prior-request gaps in `docs/REQUEST_AUDIT.md`.

## 0.5.0

- Preserve My list and history across concurrent app instances with locked,
  atomic saves, current recovery copies and visible save errors.
- Keep a valid progress checkpoint when the media engine resets before closing;
  verify fresh-user playback, two saved titles and relaunch in separate processes.
- Allow small audio runtime differences, including the three-second Street Fighter
  metadata difference; offer an explicit restart for genuinely different cuts.
- Prevent mismatched-quality switches and defer auto quality changes after seeks.
- Resize service artwork at the verified CDN endpoint before downloading/decoding.
- Add optional daily GitHub update notices, Later, Skip this version and opt-out;
  never overlay the player, download automatically or require an update.
- Include the native Windows setup builder and focused regression checks.

## 0.4.0

- Add a visible audio-language selector with embedded tracks and actual dubbed
  catalog editions, excluding subtitle-only editions.
- Switch audio editions while preserving position and paused/playing state;
  remember the preferred language and keep one canonical history entry.
- Require matching runtimes during audio changes and reject truncated files.
- Load the selected audio edition's own subtitle tracks.

## 0.3.1

- Discover MP4 subtitles through the external-caption endpoint used by Android.
- Recover matching captions from another quality of the same episode only when
  the subject, season, episode and runtime agree.
- Retain available languages after a failed download and retry empty lookups.
- Read UTF-8/UTF-16, gzip and ZIP subtitle downloads; reuse cached timed cues.
- Give season/language popups larger rows and prevent video preparation while
  a selector is open. Ignore accidental season changes from page scrolling.

## 0.3.0

- Prepare streams and the saved playback position on title pages for faster starts.
- Recover every unlocked resolution in mixed-quality movie responses.
- Resolve later series episodes with exact season/episode requests.
- Show episode cards for series and hide season controls for movies.
- Add borderless fullscreen, double-click toggle and automatically hidden controls.
- Render controls and subtitles above the native Windows video surface.
- Seek by clicking the timeline; support keyboard navigation and activation.
- Fetch search suggestions from the service.
- Download and cache subtitles by title, episode and language.
- Preserve playback positions, including near the end of a video.

## 0.2.0

- Introduce the native Windows interface, original branding and appearance settings.
- Add native playback, downloads, local history, saved titles and optional QR login.

The application remains an independent preview. Available media and account
features depend on the upstream service.
