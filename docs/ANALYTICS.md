# Download analytics and project website

**Moved:** the active website, live refresh, SEO pages and collection pipeline are
now maintained in [MovieBox Projects](https://github.com/emransm877/moviebox-projects).
Use **https://emransm877.github.io/moviebox-projects/** for the shared Android,
Windows and Samsung TV hub. The former Desktop site is a compatibility redirect.
The implementation notes below describe the original two-project snapshot site
and are retained as historical context, not the current live-refresh contract.
See the hub README for current setup and data definitions. Search Console
verification must use the new URL-prefix property.

The static website lives in `site/` and is served through GitHub Pages. It combines
the public release counters of `emransm877/moviebox-android` and
`emransm877/moviebox-desktop`. No application telemetry, visitor analytics,
account sessions, device identifiers or third-party tracking scripts are used.

## Definitions

- **Application packages:** recognized Android APKs, Windows setup EXEs and
  Windows portable ZIPs. Downloading both an installer and a ZIP counts twice.
- **All release files:** every attached asset, including checksum files and other
  attachments. This is the comparable total for trackers that sum all assets.
- **Versions:** all currently published releases, including labelled prereleases;
  draft releases are excluded. Download buttons use GitHub's latest stable release.
- **People, installs and active users:** unavailable from these counters. Repeated
  downloads are not deduplicated and must never be described as unique users.

## Collection and history

`tools/collect_downloads.py` paginates releases and their assets and writes the
last successful snapshot to `site/data/latest.json`. GitHub Actions runs it daily
at 04:23 UTC and on site changes. Scheduled jobs may be delayed; the site displays
the actual snapshot timestamp and flags snapshots older than 48 hours.

`site/data/history.json` retains observed per-asset peaks and daily observations.
The initial measurement is a baseline, not downloads that occurred that day.
Later deltas are observed increases between measurements, not precise event-time
counts. Removed assets retain their last observed count; counts for assets deleted
before collection began cannot be recovered. Replacement assets have distinct IDs.
Counters that fall are retained at their prior observed peak for the historical
series; the current snapshot still reflects GitHub's currently available assets.

If collection fails, existing committed data is left intact. The browser loads
only these public snapshots, not a GitHub token. The collector accepts an optional
`GITHUB_TOKEN` environment variable; Actions supplies its scoped token server-side.
Git history provides an additional audit trail of observations.

## Local use

```powershell
python tools/collect_downloads.py
python -m http.server 8090 --directory site
```

Open `http://localhost:8090/`. There is no framework build step or production
database. Run `python -m unittest test_download_analytics` for the collector rules.

The website workflow also runs browser checks for responsive layouts, loaded
images, package/all-file totals, project/version filtering, keyboard FAQ access,
measured growth, and unavailable snapshot data. To run them locally, install the
pinned Playwright version from `.github/workflows/site.yml`, install its Chromium
browser and run `python tools/check_site.py`. `BROWSER_CHANNEL=msedge` can select
an already installed Edge browser. Screenshots are written to an isolated temp folder.

## Discoverability and growth

Keep project descriptions and topics accurate. Use real, reviewed screenshots;
label the captured version and distinguish source from released builds. The page
includes a description, canonical URL, social metadata, sitemap and robots file.
These help search engines understand it; they do not guarantee indexing or rank.

Share useful release notes and troubleshooting answers in relevant communities
only where their rules allow it. Ask users for reproducible bug reports and tested
device configurations. Do not buy engagement, spam, imply official affiliation,
promise universal compatibility, or market unverified ad removal.
