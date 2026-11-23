# Local development

Clone this repository and work from its root. Development checks run locally by default; GitHub remains the source host and retains necessary production automation.

## Environment

Run `python tools/local_doctor.py` (`python3` on systems where that is the Python 3 command). This read-only preflight detects the host and basic tools; it does not install dependencies or certify a build. Use the project's supported runtime versions below and existing lockfiles. Do not upgrade dependencies just to run checks.

For Python, create an isolated environment with `python -m venv .venv`. Use `.venv/Scripts/python.exe` on Windows and `.venv/bin/python` on Linux/macOS for installation and checks (activation is optional). Replace `python` below with that interpreter. Existing pinned requirements remain authoritative. Where requirements contain ranges, exact historical dependency resolution is not guaranteed; record a tested lock separately before upgrading.

For Node projects with package-lock.json use `npm ci`; without a lockfile use `npm install` and review the generated lock before committing. Use the declared packageManager if present. Native SDKs and first dependency downloads need internet access. Local-first does not make external APIs or production services offline.

## Repository commands

Use Python 3.12 on Windows for the supported native desktop/package validation. Run `python -m pip install -r requirements.txt`, `python -m unittest discover -p "test_*.py"`, `python tools/check_release.py`, and `python tools/check_docs.py`. Run the GUI regression commands recorded below in an interactive Windows desktop, then `./build.ps1`; use `./build-installer.ps1` with the existing verified Inno Setup compiler for the installer. Windows APIs and packaging require Windows; Linux/macOS can edit source and run only platform-independent checks, or use the manual Windows workflow. Never treat a Linux compile as validation of Windows GUI behavior.

## Existing hosted command reference

These are the pre-migration commands for reproducing checks locally. Use the correct host shell (PowerShell paths on Windows, Bash on Unix); install requirements from the workflow. Publishing commands are intentionally excluded.

### ci.yml / verify

```text
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -p "test_*.py"
.\.venv\Scripts\python.exe verify_settings_design.py --output verification/settings-ci
.\.venv\Scripts\python.exe verify_offline_audit.py --output verification/offline-ci
.\.venv\Scripts\python.exe verify_spatial_home.py --output verification/spatial-ci --generated-fixtures --media verification/offline-ci/owned-fixture.avi
.\.venv\Scripts\python.exe tools/check_release.py
.\.venv\Scripts\python.exe tools/check_docs.py
.\.venv\Scripts\python.exe -m compileall -q main.py fluent_ui.py interactions.py subtitle_store.py audio_options.py settings_ui.py spatial_hero.py home_panels.py themes.py json_transport.py
./build.ps1
$toolInstaller = Join-Path $env:RUNNER_TEMP 'innosetup-7.1.1-x64.exe'
$toolDirectory = Join-Path $env:RUNNER_TEMP 'MovieBoxInnoSetup'
Invoke-WebRequest 'https://github.com/jrsoftware/issrc/releases/download/is-7_1_1/innosetup-7.1.1-x64.exe' -OutFile $toolInstaller
if ((Get-FileHash -LiteralPath $toolInstaller).Hash -ne '8A5A6711C3766A6E5FB74F280BA0E3551E719CE94538D901FDBD1F8F9920B3F0') { throw 'Compiler download hash mismatch' }
if ((Get-AuthenticodeSignature -LiteralPath $toolInstaller).Status -ne 'Valid') { throw 'Compiler signature verification failed' }
$toolProcess = Start-Process -FilePath $toolInstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER',"/DIR=$toolDirectory") -WindowStyle Hidden -Wait -PassThru
if ($toolProcess.ExitCode -ne 0) { throw 'Compiler installation failed' }
./build-installer.ps1 -Compiler (Join-Path $toolDirectory 'ISCC.exe')

```


## Automation and releases

Development workflows are manual fallbacks; select Run workflow in GitHub only when local execution is impractical. Retained production workflows keep their existing triggers and approval gates. Existing release downloads are unaffected by changing development triggers. Manual workflow artifacts expire after the retention shown in each workflow and are not durable release downloads.

Before pushing a workflow change, inspect current branch protection/rulesets and preserve required check names or coordinate their replacement. A manual workflow does not automatically satisfy required PR checks. Never weaken protection merely to make a push pass.

Rollback: inspect the migration commit with `git show <migration-commit>`, then `git revert <migration-commit>` and push under normal repository policy. Reverting automatic triggers may start cloud jobs; review the resulting diff first. Avoid reverting later production state or historical statistics. Account billing and Actions permissions were not changed.

For a new project, choose its existing/native tooling, record supported runtime versions, commit an appropriate dependency lock and environment example without secrets, define local validation commands and platform limits, and classify any proposed cloud automation before adding it. Do not copy an unrelated stack's build script.
