# Delivery scope and remaining external acceptance

Folio is distributed as source (WP-6): standalone archives, the Homebrew tap, wheel
builds and their scripts are gone, and so is any bundled runtime. Code and
documentation are Apache-2.0. Builds and tests run locally; no GitHub Actions or
package registry publication is used. Earlier repository histories and published
artifacts remain preserved independently. Current instructions are in
[distribution](distribution.md); the 1.1.x package release records are history and are
not part of this copy.

Native Windows and WSL desktop support remain outside this macOS/Linux release; the
Windows dialogs and notifications were cut. Destination native dialogs on Linux need
their own recorded execution (`scripts/smoke-linux-desktop.py`).

Not covered by this tree yet: Backlog-backed storage replacing the JSON store (WP-4,
WP-11) and the resulting line budget for the app's Python (3,000 lines), which
`tests/test_wp6_tree_hygiene.py` skips with a reason naming those work packages.
