# Distribution and upgrades

Folio is distributed as source. Since the v1 cuts (WP-6) there are no standalone
archives, installer scripts, Homebrew formula, wheel verifier or bundled runtime:
`scripts/build-*.py`, `scripts/install-folio*.py`, `scripts/homebrew-formula.py`,
`scripts/verify-*.py` and `scripts/python-runtime-lock.json` are gone. Releases
published earlier (v1.0.0 to v1.1.2) stay unchanged; their notes are kept under
`docs/releases/` as history and describe tools this tree no longer contains.

Folio needs Python 3.9+ and nothing else: 0 runtime dependencies, no frontend build,
no package registry.

## Run from a checkout

```sh
python3 server.py                  # http://127.0.0.1:8765
bin/folio ui                       # open an authenticated browser session
bin/folio --version
```

Symlink `bin/folio` onto your `PATH` to type `folio`. Optionally install the checkout
into a virtual environment you manage yourself (`python3 -m pip install .`), which
provides the `folio` and `folio-server` commands and the `folio.plugins` entry point
for the Ollama plugin. The package data is `folio/static/*` only. `MANIFEST.in` and
`scripts/export-source.py` describe the source distribution.

`folio --version`, `folio-server --version`, the server banner and `folio status`
report the same package version.

## Existing workspace and safe upgrades

Workspace selection is `--data-dir`, then `FOLIO_WORKSPACE`, then a user data
directory: `~/Library/Application Support/Folio/workspace` on macOS and
`${XDG_DATA_HOME:-~/.local/share}/folio/workspace` on Linux. A checkout never writes
project state inside its own tree.

For an old checkout workspace, continue using its exact absolute path with
`--data-dir`/`FOLIO_WORKSPACE`, or stop Folio and explicitly migrate its registry:

```sh
folio --data-dir /absolute/old/workspace server-stop
folio migrate-workspace --from /absolute/old/workspace --to /absolute/new/workspace
folio-server --data-dir /absolute/new/workspace
```

The destination must not exist. The command acquires the source workspace lock,
validates registered projects, copies `registry.json` (and any 1.1.x `.sync`
bookkeeping, which is no longer read) into a private sibling staging directory,
verifies and flushes the copy, durably marks the source as migrated, then publishes
the destination atomically without replacing a concurrently created directory. The
`.migrated.json` marker prevents reopening the old workspace even if migration is
interrupted after publication. After an interruption, inspect the destination and use
it if complete; delete the marker only to abandon migration after stopping all use of
the destination. **Registered project folders stay where they are**, including
automatically created folders under the old checkout workspace. Migration reports
every retained folder, and lists those inside the old workspace as
`projects_inside_source`; do not delete that workspace, or a checkout containing it,
while any remain.

Before updating a checkout, stop the server with `folio server-stop` for the selected
workspace and keep a copy of your planning data: `folio backup` and the in-app backup
download were cut together with `/api/backup`, so copy the workspace directory and
each project's `.task-manager/` folder with ordinary file tools. `folio restore --from
FILE --to DIR` still reads a 1.1.x backup file into a new workspace. Restart with the
same workspace setting and run `folio doctor` and `folio status`. This release makes
no Folio project schema change.

## Cuts that affect an upgrade

- No native folder picker: type the absolute project folder in **New project** or
  **Change project folder**.
- No `--demo` seed and no appearance setting; the UI follows the operating system.
- No native Windows dialogs or notifications; `win32` reads as "no confirmation dialog
  can open". WSL2 counts as Linux and keeps Zenity and `notify-send`.
- `folio tasks …` and `folio agent-guide` are gone; edit tasks through the Backlog CLI
  or the UI. An agent-guide skill or `AGENTS.md` block you installed earlier is not
  removed for you.

## Switchboard

Switchboard integration is frozen; see the [Switchboard freeze](../README.md#switchboard-freeze)
and tag `archive/switchboard-1.1.2`. Folio reads and writes no Switchboard state.

## Linux desktop check

On a Linux test desktop, `dbus-run-session -- xvfb-run -a python3 scripts/smoke-linux-desktop.py`
checks the real Zenity default Cancel button and the confirmation timeout. It needs
Zenity, Xvfb, xauth, xdotool and a session bus, and sends nothing to any other service.

See [local API ownership and project-file trust](local-security.md) for browser
sign-in, private CLI discovery and the local OS-account boundary.
