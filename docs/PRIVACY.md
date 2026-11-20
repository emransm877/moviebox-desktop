# Privacy and network behavior

This page describes the independently maintained MovieBox Windows client. It does
not describe the separate proprietary Android phone app or make promises about
third-party services' retention and policies.

## Data on your PC

The client stores settings, My list, playback progress, catalogue/artwork caches,
subtitle caches and download information in its local application data directory,
normally `%LOCALAPPDATA%\MovieBoxDesktop`. Media downloads use the destination you
choose. Library/cache files are not all encrypted. Other software with access to
your Windows account may be able to read local files.

Optional account sign-in uses the upstream service's QR confirmation flow.
After you approve that login, its session token is stored locally in `session.bin`
using Windows DPAPI protection. Signing out removes that local session file; it
does not necessarily revoke every session at the upstream service.

## Network requests

- Catalogue browsing, searches, title details, playback, subtitles, artwork and
  account confirmation contact the upstream service and its media/CDN hosts.
  Requests include the information necessary for those actions, guest/account
  session identifiers and client compatibility metadata. The recipient can also
  observe ordinary connection information such as your IP address.
- The service adapter's configured website is [movieboxhd.net](https://movieboxhd.net)
  and its API infrastructure includes `aoneroom.com`. Returned media/artwork hosts
  can vary. The project does not operate those services or determine their policies.
- Optional update notices request public release metadata from GitHub, including
  the application version in the User-Agent. You can turn these notices off.
  Downloads open after user action and follow GitHub's normal download routing.
  See [GitHub's privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).

The project has no separate client-usage analytics backend. It does not upload
your local My list or viewing-history database to the maintainer. Public download
statistics are GitHub release-file counters, not a measurement of app usage,
people, installations or viewing activity.

## Removing data and contacting the project

Sign out to remove the locally stored account session. Removing the application
may leave its separate data directory; delete that directory yourself if you want
to remove local settings, library and caches. Keep any files you need before
deleting them. Downloads in a folder you chose are separate files.

If you choose to submit an issue or diagnostic information to GitHub, review it
first: do not include credentials, session files, signed media URLs, private
viewing details or personal identifiers. Use the [security policy](../SECURITY.md)
for sensitive reports. The maintainer's public contact channel is the
[project repository](https://github.com/emransm877/moviebox-desktop).

Third-party services handle their own data requests and terms. This client
behavior disclosure does not replace those services' policies.
