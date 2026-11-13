# Changelog

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
