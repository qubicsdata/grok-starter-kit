"""Tests for tools/verify_pins.py and the shipped tools/pins.json.

Every artifact and every pins file used here is synthetic and built at test
time in a temp folder; the shipped pins and EXTERNAL-DEPENDENCIES.md are only
read, never written. `KIT_VERIFY_PINS=<path>` points the suite at another
copy of the script (the shipped pins file stays the one under tools/).
"""

import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFY_PINS = os.environ.get("KIT_VERIFY_PINS") or os.path.join(ROOT, "tools", "verify_pins.py")
SHIPPED_PINS = os.path.join(ROOT, "tools", "pins.json")
EXTERNAL_DEPS = os.path.join(ROOT, "EXTERNAL-DEPENDENCIES.md")

PAYLOAD = b"example artifact payload\n"
RESULT_RE = re.compile(r"^RESULT: (PASS|FAIL) \((\d+) pins?, (\d+) required, (\d+) warnings?, (\d+) errors?\)$")


def _load():
    spec = importlib.util.spec_from_file_location("verify_pins", VERIFY_PINS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hex_digest(algo, data):
    return hashlib.new(algo, data).hexdigest()


def sri_digest(algo, data):
    return "%s-%s" % (algo, base64.b64encode(hashlib.new(algo, data).digest()).decode("ascii"))


def pin(name="example-tool", digest=None, algo="sha256", required=True, **extra):
    entry = {
        "name": name,
        "version": "1.2.3",
        "platform": "linux-x64",
        "url": "https://example.com/downloads/%s-1.2.3.tar.gz" % name,
        "algo": algo,
        "digest": hex_digest(algo or "sha256", PAYLOAD) if digest is None else digest,
        "required": required,
    }
    entry.update(extra)
    return entry


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kitpins-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write_bytes(self, name, data):
        path = os.path.join(self.tmp, name)
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def write_pins(self, pins, name="pins.json"):
        return self.write_bytes(name, json.dumps({"schema": 1, "pins": pins}, indent=2).encode("utf-8"))

    def artifact(self, data=PAYLOAD, name="artifact.tar.gz"):
        return self.write_bytes(name, data)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, VERIFY_PINS, *args],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=120,
        )

    def result_line(self, proc):
        lines = [line for line in proc.stdout.splitlines() if line.startswith("RESULT:")]
        self.assertEqual(len(lines), 1, proc.stdout + proc.stderr)
        match = RESULT_RE.match(lines[0])
        self.assertIsNotNone(match, lines[0])
        return match


class DigestParsingTest(unittest.TestCase):
    """parse_digest(algo, digest) -> raw bytes, or ValueError when malformed."""

    def setUp(self):
        self.vp = _load()

    def test_hex_forms(self):
        for algo in ("sha256", "sha512"):
            with self.subTest(algo=algo):
                raw = hashlib.new(algo, PAYLOAD).digest()
                self.assertEqual(self.vp.parse_digest(algo, hex_digest(algo, PAYLOAD)), raw)

    def test_uppercase_hex_is_accepted(self):
        raw = hashlib.sha256(PAYLOAD).digest()
        self.assertEqual(self.vp.parse_digest("sha256", hex_digest("sha256", PAYLOAD).upper()), raw)

    def test_sri_forms(self):
        for algo in ("sha256", "sha512"):
            with self.subTest(algo=algo):
                raw = hashlib.new(algo, PAYLOAD).digest()
                self.assertEqual(self.vp.parse_digest(algo, sri_digest(algo, PAYLOAD)), raw)

    def test_malformed_digests_are_rejected(self):
        good256 = hex_digest("sha256", PAYLOAD)
        good512 = hex_digest("sha512", PAYLOAD)
        sri512 = sri_digest("sha512", PAYLOAD)
        b64_of_32 = base64.b64encode(hashlib.sha256(PAYLOAD).digest()).decode("ascii")
        cases = [
            ("sha256", good256[:-1]),                 # one hex digit short
            ("sha256", good256 + "0"),                # one hex digit long
            ("sha256", "g" + good256[1:]),            # not hex
            ("sha256", good512),                      # sha512 length under sha256
            ("sha512", good256),                      # sha256 length under sha512
            ("sha256", "sha256:" + good256),          # colon prefix form
            ("sha256", " " + good256),                # surrounding blank
            ("sha256", good256 + "\n"),
            ("sha512", "sha512-" + b64_of_32),        # SRI with the wrong length
            ("sha512", "sha256-" + b64_of_32),        # SRI prefix is not the pin's algo
            ("sha512", "sha512-!!!!"),                # not base64
            ("sha512", sri512.rstrip("=")),           # padding stripped
            ("sha512", sri512[len("sha512-"):]),      # bare base64, no SRI prefix
            ("sha512", sri512 + "?opt"),              # SRI options are not supported
            ("sha512", ""),
            ("md5", hashlib.md5(PAYLOAD).hexdigest()),  # unsupported algo
        ]
        for algo, digest in cases:
            with self.subTest(algo=algo, digest=digest):
                with self.assertRaises(ValueError):
                    self.vp.parse_digest(algo, digest)

    def test_non_string_digest_is_rejected(self):
        with self.assertRaises(ValueError):
            self.vp.parse_digest("sha256", 12345)


class PlaceholderTest(unittest.TestCase):
    def setUp(self):
        self.vp = _load()

    def test_placeholders(self):
        for value in (None, "", "   ", "<pinned-at-build>", "sha256-<pinned-at-build>", "TODO", "tbd"):
            with self.subTest(value=value):
                self.assertTrue(self.vp.is_placeholder(value))

    def test_real_values_are_not_placeholders(self):
        for value in ("1.2.3", hex_digest("sha256", PAYLOAD), sri_digest("sha512", PAYLOAD),
                      "https://example.com/a.tar.gz"):
            with self.subTest(value=value):
                self.assertFalse(self.vp.is_placeholder(value))


class VerifyArtifactTest(TempDirTest):
    def test_sha256_hex_match(self):
        pins = self.write_pins([pin()])
        proc = self.run_cli("--pins", pins, "example-tool", self.artifact())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK example-tool", proc.stdout)

    def test_sha256_hex_mismatch(self):
        pins = self.write_pins([pin()])
        proc = self.run_cli("--pins", pins, "example-tool", self.artifact(PAYLOAD + b"x"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("MISMATCH example-tool", proc.stdout)
        self.assertNotIn("OK example-tool", proc.stdout)

    def test_sha512_sri_match(self):
        pins = self.write_pins([pin(algo="sha512", digest=sri_digest("sha512", PAYLOAD))])
        proc = self.run_cli("--pins", pins, "example-tool", self.artifact())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK example-tool", proc.stdout)

    def test_sha512_sri_mismatch(self):
        pins = self.write_pins([pin(algo="sha512", digest=sri_digest("sha512", PAYLOAD))])
        proc = self.run_cli("--pins", pins, "example-tool", self.artifact(b"other\n"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("MISMATCH example-tool", proc.stdout)

    def test_mismatch_shows_digests_in_the_pins_form(self):
        expected = sri_digest("sha512", PAYLOAD)
        pins = self.write_pins([pin(algo="sha512", digest=expected)])
        proc = self.run_cli("--pins", pins, "example-tool", self.artifact(b"other\n"))
        self.assertIn(expected, proc.stdout)
        self.assertIn(sri_digest("sha512", b"other\n"), proc.stdout)

    def test_sha256_sri_and_sha512_hex_match(self):
        for algo, digest in (("sha256", sri_digest("sha256", PAYLOAD)), ("sha512", hex_digest("sha512", PAYLOAD))):
            with self.subTest(algo=algo, digest=digest):
                pins = self.write_pins([pin(algo=algo, digest=digest)])
                proc = self.run_cli("--pins", pins, "example-tool", self.artifact())
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_empty_artifact(self):
        pins = self.write_pins([pin(digest=hex_digest("sha256", b""))])
        proc = self.run_cli("--pins", pins, "example-tool", self.artifact(b""))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_artifact_larger_than_one_read_chunk(self):
        data = os.urandom(3 * 1024 * 1024 + 17)
        pins = self.write_pins([pin(algo="sha512", digest=sri_digest("sha512", data))])
        proc = self.run_cli("--pins", pins, "example-tool", self.artifact(data))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_right_pin_is_selected_among_several(self):
        pins = self.write_pins([
            pin("example-a", digest=hex_digest("sha256", b"a")),
            pin("example-b"),
            pin("example-c", digest=hex_digest("sha256", b"c")),
        ])
        self.assertEqual(self.run_cli("--pins", pins, "example-b", self.artifact()).returncode, 0)
        self.assertEqual(self.run_cli("--pins", pins, "example-a", self.artifact()).returncode, 1)

    def test_unknown_pin_exits_2(self):
        pins = self.write_pins([pin()])
        proc = self.run_cli("--pins", pins, "example-missing", self.artifact())
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unknown pin", proc.stderr)

    def test_missing_artifact_exits_2(self):
        pins = self.write_pins([pin()])
        proc = self.run_cli("--pins", pins, "example-tool", os.path.join(self.tmp, "absent.tar.gz"))
        self.assertEqual(proc.returncode, 2)

    def test_directory_as_artifact_exits_2(self):
        pins = self.write_pins([pin()])
        proc = self.run_cli("--pins", pins, "example-tool", self.tmp)
        self.assertEqual(proc.returncode, 2)

    def test_optional_pin_without_digest_cannot_verify(self):
        pins = self.write_pins([pin(digest=None, required=False)])
        # pin() fills a digest when None is passed; set it to null explicitly.
        with open(pins, encoding="utf-8") as handle:
            data = json.load(handle)
        data["pins"][0]["digest"] = None
        data["pins"][0]["algo"] = None
        data["pins"][0]["version"] = None
        with open(pins, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        proc = self.run_cli("--pins", pins, "example-tool", self.artifact())
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no digest", proc.stdout + proc.stderr)
        self.assertNotIn("None", proc.stdout)

    def test_placeholder_digest_cannot_verify(self):
        pins = self.write_pins([pin(digest="<pinned-at-build>")])
        proc = self.run_cli("--pins", pins, "example-tool", self.artifact())
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("OK example-tool", proc.stdout)

    def test_pins_file_with_errors_blocks_verification(self):
        pins = self.write_pins([pin(), pin("example-bad", digest="abc")])
        proc = self.run_cli("--pins", pins, "example-tool", self.artifact())
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("OK example-tool", proc.stdout)

    def test_name_without_file_is_a_usage_error(self):
        pins = self.write_pins([pin()])
        self.assertEqual(self.run_cli("--pins", pins, "example-tool").returncode, 2)


class CheckModeTest(TempDirTest):
    """No artifact given: the pins file is validated, dev mode or --release."""

    def test_all_good_passes_in_both_modes(self):
        pins = self.write_pins([pin(), pin("example-sri", algo="sha512", digest=sri_digest("sha512", PAYLOAD))])
        for extra in ([], ["--release"]):
            with self.subTest(extra=extra):
                proc = self.run_cli("--pins", pins, *extra)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                match = self.result_line(proc)
                self.assertEqual(match.groups(), ("PASS", "2", "2", "0", "0"))

    def test_required_placeholder_warns_in_dev_mode(self):
        pins = self.write_pins([pin(), pin("example-later", digest="<pinned-at-build>")])
        proc = self.run_cli("--pins", pins)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertRegex(proc.stdout, r"(?m)^WARN example-later: ")
        self.assertEqual(self.result_line(proc).groups(), ("PASS", "2", "2", "1", "0"))

    def test_required_placeholder_fails_release(self):
        pins = self.write_pins([pin(), pin("example-later", digest="<pinned-at-build>")])
        proc = self.run_cli("--pins", pins, "--release")
        self.assertEqual(proc.returncode, 1)
        self.assertRegex(proc.stdout, r"(?m)^ERROR example-later: ")
        self.assertEqual(self.result_line(proc).groups(), ("FAIL", "2", "2", "0", "1"))

    def test_every_placeholder_field_of_a_required_pin_fails_release(self):
        for field, value in (("digest", None), ("digest", ""), ("version", "<pinned-at-build>"),
                             ("url", "<pinned-at-build>"), ("platform", ""), ("algo", None)):
            with self.subTest(field=field, value=value):
                entry = pin()
                entry[field] = value
                if field == "algo":
                    entry["digest"] = "<pinned-at-build>"
                pins = self.write_pins([entry])
                self.assertEqual(self.run_cli("--pins", pins).returncode, 0)
                proc = self.run_cli("--pins", pins, "--release")
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertIn(field, proc.stdout)

    def test_optional_pin_without_digest_is_fine(self):
        entry = pin("example-optional", required=False, digest="", algo=None, version=None)
        entry["digest"] = None
        pins = self.write_pins([pin(), entry])
        for extra in ([], ["--release"]):
            with self.subTest(extra=extra):
                proc = self.run_cli("--pins", pins, *extra)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertNotIn("WARN", proc.stdout)
                self.assertEqual(self.result_line(proc).groups(), ("PASS", "2", "1", "0", "0"))

    def test_optional_pin_with_placeholder_digest_is_fine(self):
        pins = self.write_pins([pin("example-optional", required=False, digest="<pinned-at-build>")])
        proc = self.run_cli("--pins", pins, "--release")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_malformed_digest_fails_in_both_modes(self):
        for required in (True, False):
            for digest in ("abc", "sha512-" + base64.b64encode(b"short").decode("ascii")):
                with self.subTest(required=required, digest=digest):
                    pins = self.write_pins([pin(), pin("example-bad", digest=digest, required=required)])
                    for extra in ([], ["--release"]):
                        proc = self.run_cli("--pins", pins, *extra)
                        self.assertEqual(proc.returncode, 1, proc.stdout)
                        self.assertRegex(proc.stdout, r"(?m)^ERROR example-bad: ")

    def test_digest_with_a_real_value_but_no_algo_fails(self):
        for required in (True, False):
            with self.subTest(required=required):
                pins = self.write_pins([pin(required=required, algo=None)])
                self.assertEqual(self.run_cli("--pins", pins).returncode, 1)

    def test_form_field_must_match_the_digest(self):
        pins = self.write_pins([pin(form="sri")])
        proc = self.run_cli("--pins", pins)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("form", proc.stdout)
        pins = self.write_pins([pin(form="hex")])
        self.assertEqual(self.run_cli("--pins", pins).returncode, 0)

    def test_schema_errors(self):
        bad_entries = {
            "missing key": {k: v for k, v in pin().items() if k != "platform"},
            "required not bool": pin(required="true"),
            "url not https": pin(url="http://example.com/a.tar.gz"),
            "bad name": pin(name="Example Tool"),
            "version not a string": pin(version=123),
            "negative size": pin(size=-1),
            "size not an integer": pin(size="12"),
            "unsupported algo": pin(algo="md5", digest="0" * 32),
            "not an object": "example-tool",
        }
        for label, entry in bad_entries.items():
            with self.subTest(case=label):
                pins = self.write_pins([pin("example-ok"), entry])
                proc = self.run_cli("--pins", pins)
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertIn("ERROR", proc.stdout)

    def test_duplicate_names_fail(self):
        pins = self.write_pins([pin(), pin()])
        proc = self.run_cli("--pins", pins)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("duplicate", proc.stdout)

    def test_empty_pin_list_fails(self):
        pins = self.write_pins([])
        self.assertEqual(self.run_cli("--pins", pins).returncode, 1)

    def test_top_level_without_pins_list_fails(self):
        path = self.write_bytes("pins.json", b'{"schema": 1, "pins": {}}')
        self.assertEqual(self.run_cli("--pins", path).returncode, 1)

    def test_unsupported_schema_version_fails(self):
        path = self.write_bytes("pins.json", json.dumps({"schema": 2, "pins": [pin()]}).encode("utf-8"))
        self.assertEqual(self.run_cli("--pins", path).returncode, 1)

    def test_invalid_json_exits_2(self):
        path = self.write_bytes("pins.json", b"{not json")
        proc = self.run_cli("--pins", path)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("RESULT: PASS", proc.stdout)

    def test_missing_pins_file_exits_2(self):
        self.assertEqual(self.run_cli("--pins", os.path.join(self.tmp, "absent.json")).returncode, 2)

    def test_list_prints_every_pin(self):
        pins = self.write_pins([pin(), pin("example-two", required=False)])
        proc = self.run_cli("--pins", pins, "--list")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("example-tool", proc.stdout)
        self.assertIn("example-two", proc.stdout)

    def test_unknown_flag_exits_2(self):
        self.assertEqual(self.run_cli("--no-such-flag").returncode, 2)


class ShippedPinsTest(unittest.TestCase):
    """The tools/pins.json that ships with the kit."""

    PLATFORMS = ("darwin-arm64", "darwin-x64", "linux-x64", "linux-arm64")

    @classmethod
    def setUpClass(cls):
        cls.vp = _load()
        with open(SHIPPED_PINS, encoding="utf-8") as handle:
            cls.data = json.load(handle)
        cls.pins = cls.data["pins"]
        cls.by_name = {p["name"]: p for p in cls.pins}

    def test_names_are_unique(self):
        self.assertEqual(len(self.by_name), len(self.pins))

    def test_validates_clean_in_release_mode(self):
        report = self.vp.check_pins(self.data, release=True)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_no_placeholder_on_any_required_pin(self):
        for entry in self.pins:
            if entry["required"]:
                for field in ("version", "platform", "url", "algo", "digest"):
                    with self.subTest(pin=entry["name"], field=field):
                        self.assertFalse(self.vp.is_placeholder(entry[field]))

    def test_every_digest_is_well_formed(self):
        for entry in self.pins:
            if self.vp.is_placeholder(entry.get("digest")):
                continue
            with self.subTest(pin=entry["name"]):
                raw = self.vp.parse_digest(entry["algo"], entry["digest"])
                self.assertEqual(len(raw), hashlib.new(entry["algo"]).digest_size)

    def test_npm_pins_keep_the_sri_form(self):
        for entry in self.pins:
            if entry["url"].startswith("https://registry.npmjs.org/"):
                with self.subTest(pin=entry["name"]):
                    self.assertTrue(entry["digest"].startswith("sha512-"), entry["digest"])

    def test_required_set(self):
        expected = {"claude-code"}
        for platform in self.PLATFORMS:
            expected |= {"claude-code-" + platform, "uv-" + platform, "node-" + platform}
        required = {p["name"] for p in self.pins if p["required"] is True}
        self.assertEqual(required, expected)

    def test_required_pins_cover_every_platform(self):
        for prefix in ("claude-code-", "uv-", "node-"):
            platforms = {p["platform"] for p in self.pins
                         if p["required"] and p["name"].startswith(prefix)}
            with self.subTest(prefix=prefix):
                self.assertEqual(platforms, set(self.PLATFORMS))

    def test_versions_agree_within_a_tool(self):
        for prefix in ("claude-code", "uv-", "node-"):
            versions = {p["version"] for p in self.pins if p["name"].startswith(prefix)}
            with self.subTest(prefix=prefix):
                self.assertEqual(len(versions), 1, versions)

    def test_native_installer_pins_are_optional(self):
        native = [p for p in self.pins if p["name"].startswith("claude-code-native-")]
        self.assertEqual(len(native), 4)
        for entry in native:
            self.assertIs(entry["required"], False)
            self.assertEqual(entry["algo"], "sha256")

    def test_backlog_pin(self):
        entry = self.by_name["backlog.md"]
        self.assertEqual(entry["version"], "1.53.0")
        self.assertEqual(entry["algo"], "sha512")
        self.assertIs(entry["required"], False)
        self.assertTrue(entry["digest"].startswith("sha512-"))

    def test_release_gate_dev_tools_are_optional(self):
        for name, version in (("gitleaks", "8.21.2"), ("trufflehog", "3.88.0")):
            with self.subTest(name=name):
                entry = self.by_name[name]
                self.assertEqual(entry["version"], version)
                self.assertEqual(entry["algo"], "sha256")
                self.assertIs(entry["required"], False)

    def test_ripgrep_is_optional_and_never_pinned(self):
        entry = self.by_name.get("ripgrep")
        if entry is None:
            return
        self.assertIs(entry["required"], False)
        self.assertTrue(self.vp.is_placeholder(entry.get("digest")))

    def test_urls_are_https(self):
        for entry in self.pins:
            with self.subTest(pin=entry["name"]):
                self.assertTrue(entry["url"].startswith("https://"))

    def test_cli_release_passes_on_the_shipped_pins(self):
        proc = subprocess.run(
            [sys.executable, VERIFY_PINS, "--release"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertRegex(proc.stdout, r"(?m)^RESULT: PASS \(")


class ExternalDependenciesDocTest(unittest.TestCase):
    """EXTERNAL-DEPENDENCIES.md and tools/pins.json carry the same checksums."""

    @classmethod
    def setUpClass(cls):
        with open(SHIPPED_PINS, encoding="utf-8") as handle:
            cls.by_name = {p["name"]: p for p in json.load(handle)["pins"]}
        with open(EXTERNAL_DEPS, encoding="utf-8") as handle:
            cls.text = handle.read()

    def pinned_rows(self):
        rows = []
        in_table = False
        for line in self.text.splitlines():
            if line.startswith("| Pin |"):
                in_table = True
                continue
            if in_table and line.startswith("|---"):
                continue
            if in_table and line.startswith("|"):
                rows.append([cell.strip() for cell in line.strip("|").split("|")])
            elif in_table:
                break
        return rows

    def test_pinned_table_rows_match_pins_json(self):
        rows = self.pinned_rows()
        self.assertGreaterEqual(len(rows), 17)
        for cells in rows:
            name, version, platform, checksum, url = cells[:5]
            required = cells[-1]
            with self.subTest(pin=name):
                entry = self.by_name[name]
                self.assertEqual(version, entry["version"])
                self.assertEqual(platform, entry["platform"])
                self.assertEqual(checksum, "`%s` `%s`" % (entry["algo"], entry["digest"]))
                self.assertEqual(url, entry["url"])
                self.assertEqual(required, "yes" if entry["required"] else "no")

    def test_every_pinned_digest_is_documented(self):
        for name, entry in self.by_name.items():
            digest = entry.get("digest")
            if not digest:
                continue
            # The summary table records Backlog.md's integrity without the SRI prefix.
            bare = digest.split("-", 1)[1] if digest.startswith("sha512-") else digest
            with self.subTest(pin=name):
                self.assertIn(bare, self.text)

    def test_no_placeholder_left_in_the_doc(self):
        self.assertNotIn("<pinned-at-build>", self.text)

    def test_ripgrep_is_documented_as_optional(self):
        rows = [line for line in self.text.splitlines() if line.startswith("| ripgrep |")]
        self.assertEqual(len(rows), 1)
        self.assertIn("optional", rows[0])
        self.assertIn("never installed", rows[0])


if __name__ == "__main__":
    unittest.main()
