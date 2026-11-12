# Changelog

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
