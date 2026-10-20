# bin/

`sb` is a read-only, channel-aware search over your notes with a `--doctor` health check. It reads the `second_brain:` block of `kit.config.yaml` (home, router file, channels, roots, path defaults, name hashes, boost paths, doctor switches) instead of built-in values. It never writes, moves or deletes anything; the one exception is `sb --init-key`, which creates your scan key for name hashes outside every repo (see below).

## Requirements

- Python 3.9 or newer, standard library only. Nothing to install.
- ripgrep (`rg`) is optional. When it is already on your PATH, `sb` uses it to find candidate lines faster; without it the pure-Python engine gives the same ranked output. The kit never installs ripgrep.

## Usage

```
sb <query...> [--channel <name>] [--limit N] [--raw] [--engine auto|rg|python] [--config PATH]
sb --doctor [--config PATH]
sb --init-key
sb --hash-name < words.txt
sb --help
```

- `--channel X` is strict: only notes whose channel is exactly `X`; untagged and mixed notes are withheld and counted.
- `--engine auto` (default) picks `rg` when it is installed, else `python`; `SB_ENGINE` sets the default. `--engine rg` without ripgrep is a usage error.
- `--raw` also searches the raw roots and raw-looking files, which rank below curated notes.
- The config is the first of `--config PATH`, `$KIT_CONFIG`, `$KIT_HOME/kit.config.yaml`, `$HOME/grok-kit/kit.config.yaml`; with none of them the built-in defaults equal `kit.config.example.yaml`. `$SB_HOME` wins over `second_brain.home`.
- Never read: dot files and folders, `node_modules/`, `bin/`, the router file, `*.env`, `*secret*`, `*token*`, `*credential*` names, files over 2 MiB and binary files. A line that looks like a credential is withheld.

Exit codes: 0 search ran (hits or none); 2 usage or config error, or a missing or unusable scan key while `name_hashes` has entries.

## `sb --doctor`

Checks 1 to 9 of `../DOCTOR-SPEC.md` over every `*.md` note below a folder of the home (top-level files such as `README.md` and the router are not notes). One line per finding, `FAIL <check> <path>` or `WARN <check> <path>`, sorted by check then path, then a summary line. The matching line is never printed.

| Exit | Meaning |
|---|---|
| 0 | no failing check (warnings 7 and 8, and checks switched to warnings, do not fail) |
| 1 | a router path is missing (check 1) and nothing else failed |
| 3 | a tag isolation check failed (2 to 6, 9) |

`second_brain.doctor.fail_on_*` turns a check's `FAIL` into `WARN` (untagged, multiple channels, folder mismatch, cross-channel link, missing router path). The doctor never spawns `rg`.

## Name hashes and the scan key

`second_brain.name_hashes` lets a word that is not a channel name (say, the name of a studio) count as a channel without writing that word into the config. Each key is the first 16 hex characters of HMAC-SHA256 over the folded word (lower case, accents stripped), keyed with your **scan key**: 32 random bytes that live only on your box. Without the key, a list of likely words does not turn a hash back into the word.

- **Where:** `~/.config/grok-kit/scan.key` (`$XDG_CONFIG_HOME/grok-kit/scan.key` when `XDG_CONFIG_HOME` is set to an absolute path). The file has mode 0600, its folder 0700. That is outside every repo, and `scan.key` is in the kit's `.gitignore` too. If your `~/.config` is itself a repo (a dotfiles repo) or is backed up, exclude `grok-kit/scan.key` there as well. Never put the key into an env file, a note or a chat.
- **Create it once:** `sb --init-key`. It prints the path, never the key, and refuses to replace an existing key. If the `grok-kit` folder already exists and other users can open it, the command refuses and tells you to `chmod 700` it; sb never changes your folder's mode.
- **Hash a word:** `sb --hash-name < words.txt` reads one word per line from stdin (not from the command line, so the words stay out of your shell history) and prints one hash per non-blank line, in order. A line that is not one word of letters and digits is refused, and nothing is printed. Put each hash into the config as `"<hash>": "<channel>"`.
- **Fails closed:** while `name_hashes` has entries, search and `--doctor` need the key. If it is missing, unreadable, a symlink, not yours, open to group or others, or not exactly 32 bytes, sb stops with exit 2 and says how to create it. There is no fallback to unkeyed hashes. With `name_hashes: {}` (the default) no key is needed and none is created.

### Rotating the key

A new key makes every existing `name_hashes` entry invalid, so rotating means re-hashing from the plain words you still have:

1. Keep your plain words at hand (one per line, outside the second brain and outside every repo).
2. Delete the old key: `rm ~/.config/grok-kit/scan.key`.
3. `sb --init-key`
4. `sb --hash-name < words.txt`, then replace every `name_hashes` key with the new hash of the same word (the channels stay the same).
5. `sb --doctor`: a note whose `channel:` still relies on an old hash shows up as `FAIL 9` (unknown channel) until its entry is re-hashed.

Rotate when the key may have been seen by someone else (copied off the box, open to other users).

**Contract change:** older kit versions used the first 16 hex characters of an unkeyed sha256 of the word. Those entries no longer match anything; re-hash them with the steps above (steps 3 to 5 if you have no key yet).

## Tests

```
python3 -m unittest discover -s second-brain/tests -p 'test_*.py'
python3 second-brain/tests/mutation_check.py      # dev check, a few minutes
```

The suite builds every fixture in a temp folder (synthetic notes, a fake HOME, PATH folders with and without `rg`); the rg-engine tests skip when ripgrep is not installed. `python3 tools/ci_local.py` runs the suite as step `sb`.
