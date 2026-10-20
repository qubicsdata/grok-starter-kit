# vendor/folio: Folio, the local planning UI (kit notes)

This folder holds Folio, a local planning UI (Apache-2.0; its LICENSE and NOTICE are kept), copied
file by file from the cleaned, scanned source tree (see `VENDORED.md` at the kit root for the source
sha). No git history, no submodule, no link to any other repository. It binds to 127.0.0.1 only and
needs Python 3.9+ (install with uv from this folder); Node is not needed for Folio itself.

Folio's own README.md (next to this file) describes the product and its commands. The kit's rules:

- Optional and off by default (`folio.enabled`).
- Channel profiles and migration allow-lists are optional and off (`folio.machine_profile: none`).
- External task-service sync is off (`folio.task_sync: false`).
- Never run `backlog browser`.

## Kit defaults and what they mean in Folio

Folio keeps its per-machine settings in `$XDG_CONFIG_HOME/folio/config.json` (default
`~/.config/folio/config.json`). With every kit default the kit writes **no** Folio config at all:
no file means no plugin is enabled and the About panel shows no attribution, website or help link.

| Kit key (`kit.config.yaml`) | Default | In Folio |
|---|---|---|
| `folio.enabled` | `false` | the kit installs and starts nothing; Phase 7 of `AGENTS.md` asks first |
| `folio.source` | `${KIT_HOME}/vendor/folio` | this folder, installed with uv |
| `folio.data_dir` | empty | empty = Folio's default workspace (`$FOLIO_WORKSPACE`, else the user data folder); a value is passed as `--data-dir` |
| `folio.task_sync` | `false` | nothing to switch off: this Folio has no task sync. The Switchboard integration is removed (README "Switchboard freeze"; `--no-sync` is accepted and does nothing) and `folio sync` is not part of this version |
| `folio.machine_profile` | `none` | this Folio reads no channel profile (the README's `machine_profile` arrives with a later Folio version), so no channel restriction applies |
| `folio.migration_allow_list` | empty (off) | this Folio has no allow-list migration (`folio migrate` arrives later); `folio migrate-workspace` copies a workspace only when you run it |
| `folio.backlog_version` | `1.53.0` | the Backlog.md version Folio pins and checks (`folio/backlog/tools.py`) |
| `folio.about.attribution` | empty | `about.attribution` in Folio's local config: one line, at most 200 characters |
| `folio.about.website` | empty | `about.website`: an http(s) address, e.g. `kit.homepage` |
| `folio.about.help_url` | empty | `about.help_url`: an http(s) address for "Installation and support" |

To show your own About texts, set them in `kit.config.yaml` and add them to Folio's local config as
`{"about": {"attribution": "Maintained by <your-name>", "website": "https://example.com/"}}`
(keep any `plugins` entry you already have). An unknown key, a non-text value, more than one line or
an address that is not http(s) makes `folio-server` refuse to start with one line naming the problem,
the same as a bad plugin config. kit tests (`tests/test_folio_defaults.py`) check every default
against the vendored code and fail when a later Folio adds sync, a channel profile or an allow-list,
so the matching kit key gets wired before it can default on.

## What the kit copy changes

- Left out: internal session records (the dot-prefixed records folder and `docs/acceptance/`),
  release records (`docs/releases/`, the two historical Mac handoff notes), the plan and its reviews
  (`docs/superpowers/`), and any
  Homebrew or standalone build script.
- NOTICE and `folio/static/NOTICE.txt` carry the kit's decided wording (company copyright line only).
- The product surfaces are generic: the brand title and the web manifest say "Folio", `pyproject.toml`
  has no project URLs, and the About texts come from the local config (above) instead of the code
  (`product_info` in `folio/api.py`, read once by `build_app` with the plugin config; tested in
  `tests/test_kit_about.py`).
- Generic placeholders replace the original organisation and channel names in the documentation and
  tests: the example tasks repository, channel and deploy-key names in README.md, `docs/` and
  `tests/`. "Example Org", `example-org` and `example-channel` are placeholders, not values to keep;
  your own name comes from `kit.config.yaml` (`kit.author_name`, `kit.homepage`).
- `tests/KEEP.md` points at the shifted `folio/web.py` lines; the kept security tests are unchanged.
- `tests/test_wp8_ollama_url.py` joins its userinfo sample URL at run time, so secret scanners find
  no credential-shaped URL in the copy; the test is unchanged.

## Checks

From this folder: `python3 -m unittest discover -s tests -v` runs Folio's own suite (stdlib only).
Set `FOLIO_BACKLOG_BIN` to the pinned Backlog.md 1.53.0 binary for that run only; without it the
Backlog.md contract tests fail unless you opt out with `FOLIO_BACKLOG_CONTRACT=skip`. Tests that need
Chrome skip without it. From the kit root, `python3 tools/ci_local.py --with-folio` runs the same suite
as the `folio` step: PASS with the binary, SKIP (the contract opted out) without it, and `--release`
turns that SKIP into a failure.
