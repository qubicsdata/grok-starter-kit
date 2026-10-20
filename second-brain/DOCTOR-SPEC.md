# sb --doctor: checks (template)

`sb --doctor` exits non-zero if ANY check fails (the template is stricter than a plain search tool).

| # | Check | Fails when | Exit |
|---|---|---|---|
| 1 | Router paths | a ROUTER.md path does not exist | 1 |
| 2 | Missing channel | a note has no `channel:` (and no channel tag) | 3 |
| 3 | One channel only | `channel` or `tags` name more than one configured channel | 3 |
| 4 | Folder agrees | the first folder of the note is not its channel | 3 |
| 5 | Cross-channel link | `links:` or a `[[...]]` link resolves to a note of another channel | 3 |
| 6 | Router row scope | a ROUTER.md row's paths sit outside its `Ch` folder | 3 |
| 7 | Not routed | a folder with notes has no ROUTER.md row (warning only) | 0 |
| 8 | Personal-data hint | a line looks like an email, phone number, IBAN or date of birth (warning; heuristic) | 0 |
| 9 | Unknown channel | `channel` is not in `second_brain.channels` (a word with a `name_hashes` entry counts as its channel) | 3 |

Output lists paths and check numbers only, never the matching line. With `name_hashes` entries the doctor needs the scan key and fails closed (exit 2) without a usable one; see `bin/README.md`.
