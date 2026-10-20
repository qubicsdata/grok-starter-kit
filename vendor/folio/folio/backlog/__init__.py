"""The only path between Folio and Backlog.md task files: a pinned binary driven by fixed argv.

`tools` resolves and verifies the binary (version 1.53.0, recorded sha256), `guard` refuses
`onStatusChange` before any edit, `adapter` wraps `task`/`doc`/`doctor` with refusal of option-like
values. Nothing in this package writes under backlog/** except through the binary (static test).
"""
