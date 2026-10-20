# Use Folio and Switchboard locally

> **Historical.** Switchboard integration in Folio is frozen (see the README's
> [Switchboard freeze](../README.md#switchboard-freeze)), and since WP-6 Folio is
> distributed as source only. The pairing sections below describe Folio 1.1.x and the
> archive tag `archive/switchboard-1.1.2`.

Download the [Switchboard releases](https://github.com/example-org/switchboard-releases/releases)
for Switchboard itself. Folio has no installer or release archive any more.

## Run Folio on macOS or Linux

Folio needs Python 3.9+ and nothing else. From a checkout:

```sh
bin/folio --version
bin/folio ui
```

`folio ui` opens an authenticated browser session at the local address. Use that command instead of a bare URL when signing in; the launch fragment is cleared immediately. Save `bin/` on your PATH (or symlink `bin/folio`) for future terminals. The default workspace
is `~/Library/Application Support/Folio/workspace` on macOS and
`${XDG_DATA_HOME:-~/.local/share}/folio/workspace` on Linux. Stop the server and copy
your planning data before updating a checkout; see [distribution and upgrades](distribution.md).

## Install Switchboard

Choose the Switchboard release archive matching your operating system and CPU:
`darwin-arm64`, `darwin-x64`, `linux-arm64`, or `linux-x64`. Linux archives target
glibc distributions. Verify the exact checksum from its release manifest and follow
the installer shipped with that archive. Its packaged Node runtime and production
dependencies are included; it does not need a global Node installation.

After installation, put its `bin` directory on PATH, then run:

```sh
switchboard init
switchboard doctor --json
switchboard service start
switchboard ui
```

`switchboard ui` opens a one-time sign-in link for the dashboard at **http://127.0.0.1:47831/**. `switchboard service install` optionally enables
login startup through macOS launchd or Linux user systemd. In a Linux session without
user systemd, use `service start`. Read the Switchboard release's platform limits
and harness prerequisites before starting agent work.

## Connect one project

In Folio, create or open a project using its existing project folder. Under project
**Details**, connect it to Switchboard and start with **Tasks I send**. Configure
and start that project's coordinator in Switchboard, then send a task with **Send
to agents**. Unassigned work queues for the coordinator; pinned tasks go to their
worker. Paused projects and unfinished dependencies remain respected.

Both apps must use the same operating-system user, Switchboard home, and project
folder. Keep the installed `switchboard` command on Folio's PATH. Folio uses its
noninteractive owner RPC bridge to authenticate against Switchboard's vault;
owner credentials stay in the vault. Unlock the vault or configure its private
passphrase file before syncing. Legacy Switchboard 1.0 `lead.json` installations
retain direct RPC compatibility. Set a custom `SWITCHBOARD_HOME` for both apps. Folio remains the authoritative
planning document; Switchboard executes tasks and keeps its own state. Saved notes
and decisions become versioned sources that agents can retrieve in bounded pages.
See [planning sources](planning-sources.md).

Sign into only the harnesses you intend to use with `switchboard harness-login`.
Installation, diagnostics, and automated pair checks make no model calls. Real
agent work uses the provider account and model you configure.

On Linux, install **Zenity** for Folio approval confirmations. Run Folio in your desktop session so dialogs appear on that
computer. Without a desktop, resolve approvals in Switchboard.
Stop Folio with `folio server-stop` and Switchboard with `switchboard service stop`
before upgrading. Folio does not install login startup automatically.

## Maintainer verification

The wheel and pair verifiers (`scripts/verify-wheel.py`, `scripts/verify-pair.py`) are
gone. Folio's own gate is `python3 -m unittest discover -s tests -v` or
`scripts/ci-local.sh`; see the README's Development section.

Native Windows and WSL desktop support are not part of Folio 1.1. Earlier release
records retain historical validation; they are not download instructions.
