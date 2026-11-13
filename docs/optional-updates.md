# Optional update checks

`release_updates.py` reads only public GitHub release metadata. It does not fetch
installer bytes, run a program, change playback, force an update or require a
GitHub token. The only accepted repository is `emransm877/moviebox-desktop`.

## Integration contract

Keep the installed application version in the application's version constant and
pass it as `current_version`; for the next build this is `0.5.0`. Do not derive
the installed version from the latest online release.

Store these values in `state['update_notifications']`:

```python
{'enabled': True, 'last_checked': 0, 'skipped_version': ''}
```

1. After startup, use `check_due(settings)` before queuing a worker. Keep a
   separate in-flight flag so timers cannot queue duplicate requests.
2. On the worker, call `check_for_update(APP_VERSION, dict(settings))`. It returns
   an immutable `CheckResult` and never mutates the captured settings dictionary.
3. On the UI thread, merge `record_result(current_settings, result)` into the
   current state and persist. Record failed checks too; offline, refused or
   rate-limited requests stay silent and wait a day before another attempt.
4. Hold `result.notice` in memory while playback is active. Display a nonmodal
   notification on a browsing/details page only when
   `notice_is_allowed(current_settings, notice)` still returns true. Recheck
   before opening a queued notice because opt-out or skip may have changed.
5. **Download** opens `notice.download_url` in the user's browser after an
   explicit click. **Later** dismisses; the daily interval prevents immediate
   redisplay. **Skip this version** stores `notice.version` as `skipped_version`.
   A Settings checkbox can disable automatic checks and re-enable them later.

`check_due(..., force=True)` bypasses the daily timer but still respects opt-out.
Use this only for an explicit user-initiated check. The updater's errors should
not replace a playback error/status or produce a modal error dialog.

The checker accepts strictly newer stable three-part versions, published releases
and exact same-repository asset URLs. It prefers the version-matched Windows x64
setup EXE, then a matching portable ZIP. Drafts, prereleases, untrusted links and
missing installers produce no notice. API reads are bounded to 512 KiB with an
eight-second timeout; HTTP redirects are not followed. A browser may follow the
normal GitHub download redirect after the user chooses Download.

## Verification and limitations

Run `python -m unittest test_release_updates`. Tests use synthetic release data
and mocked transport, including bad URLs, skipped/equal/older versions, failed
requests and throttling. They do not contact GitHub or establish that a downloaded
future installer is authentic. The updater deliberately makes no code-signature
or universal compatibility claim. UI timing, dismiss actions and playback
deferral were exercised in the native Qt integration check in `verify_history.py`.
The first upgrade from older installed versions must be installed manually;
those old binaries do not already contain this checker.
