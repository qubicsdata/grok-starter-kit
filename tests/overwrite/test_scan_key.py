"""The planner's doctor step with `second_brain.name_hashes` (keyed
name hashes): the planner loads the scan key the way `sb` does before it
runs the doctor in-process, and fails closed with the same note when the key
is missing or unusable (tools/KIT-PLAN-SPEC.md).

The key, the words and their hashes are synthetic and built at run time; the
key lives in the temp HOME of the case, never in a real one.
"""

import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import unittest

from support import EXIT_OK, KIT_PLAN, KIT_ROOT, HarnessCase, items_where

KEY = hashlib.sha256(b"kit_plan synthetic fixture scan key").digest()
OTHER_KEY = hashlib.sha256(b"kit_plan another synthetic scan key").digest()
WORD = "zq" + "vexilo"  # an invented word that names no channel
NOT_RUN = " (sb --doctor could not run: ScanKeyError)"

UNTAGGED = "notes/example-untagged.md"
HASHED = "dance-school/example-hashed.md"  # in its channel's folder: no folder mismatch

CASE = {
    "synthetic": True,
    "files": [
        {"path": UNTAGGED, "front_matter": {}},
        # Tagged only through name_hashes: with the right key it counts as dance-school.
        {"path": HASHED, "front_matter": {"channel": WORD}},
    ],
    "expect": {},
}


def name_hash(key, word):
    return hmac.new(key, word.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


class ScanKeyDoctorTest(HarnessCase):
    """`report` doctor item of checkpoint 3 with and without the scan key."""

    def make_world(self, name_hashes=True, key=KEY, key_mode=0o600):
        if name_hashes:
            self.CONFIG_EXTRA = {"second_brain": {"name_hashes": {name_hash(KEY, WORD): "dance-school"}}}
        world = self.world(CASE)
        if key is not None:
            folder = os.path.join(world.home, ".config", "grok-kit")
            os.makedirs(folder, 0o700, exist_ok=True)
            os.chmod(folder, 0o700)
            path = os.path.join(folder, "scan.key")
            self.assertTrue(path.startswith(self.tmp + os.sep), "fixture key outside the temp folder")
            with open(path, "wb") as fh:
                fh.write(key)
            os.chmod(path, key_mode)
        return world

    def doctor_item(self, plan):
        reports = items_where(plan, type="report", kind="doctor")
        self.assertEqual(len(reports), 1, "exactly one doctor report item")
        return reports[0]

    def finding_paths(self, item):
        return sorted({f["path"] for f in item["findings"]})

    def test_doctor_runs_with_the_key(self):
        """With name_hashes and her key, the doctor runs: no ScanKeyError, the
        untagged note is a finding and the hash-tagged note is not."""
        plan = self.dry_run(self.make_world())
        item = self.doctor_item(plan)
        self.assertNotIn("could not run", item["reason"])
        self.assertEqual(item["findings"], [{"path": UNTAGGED, "check": 2}])

    def test_doctor_matches_with_her_key_only(self):
        """The doctor hashes with the key in her HOME: under another key the
        hashed word names no channel and that note becomes a finding."""
        plan = self.dry_run(self.make_world(key=OTHER_KEY))
        item = self.doctor_item(plan)
        self.assertNotIn("could not run", item["reason"])
        self.assertIn(HASHED, self.finding_paths(item))

    def test_missing_key_fails_closed(self):
        plan = self.dry_run(self.make_world(key=None))
        item = self.doctor_item(plan)
        self.assertTrue(item["reason"].endswith(NOT_RUN), item["reason"])
        self.assertEqual(item["findings"], [])

    def test_key_open_to_others_fails_closed(self):
        plan = self.dry_run(self.make_world(key_mode=0o644))
        item = self.doctor_item(plan)
        self.assertTrue(item["reason"].endswith(NOT_RUN), item["reason"])
        self.assertEqual(item["findings"], [])

    def test_short_key_fails_closed(self):
        plan = self.dry_run(self.make_world(key=KEY[:16]))
        item = self.doctor_item(plan)
        self.assertTrue(item["reason"].endswith(NOT_RUN), item["reason"])
        self.assertEqual(item["findings"], [])

    def test_without_name_hashes_the_key_is_not_read(self):
        """No name_hashes: an unusable key file changes nothing, the doctor
        runs as before (the hashed word is then just an unknown channel)."""
        plan = self.dry_run(self.make_world(name_hashes=False, key_mode=0o644))
        item = self.doctor_item(plan)
        self.assertNotIn("could not run", item["reason"])
        self.assertEqual(self.finding_paths(item), [HASHED, UNTAGGED])

    def test_without_name_hashes_and_no_key(self):
        plan = self.dry_run(self.make_world(name_hashes=False, key=None))
        item = self.doctor_item(plan)
        self.assertNotIn("could not run", item["reason"])
        self.assertEqual(self.finding_paths(item), [HASHED, UNTAGGED])

    def test_key_under_home_flag_without_HOME(self):
        """No $HOME: the key is looked up under --home, like the settings."""
        world = self.make_world()
        env = world.env()
        del env["HOME"]
        proc = subprocess.run(
            [sys.executable, KIT_PLAN, "--dry-run", "--json", "--kit", KIT_ROOT, "--config", world.config_path,
             "--state", world.state_path, "--setup-dir", world.setup, "--home", world.home],
            cwd=world.tmp, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=300,
        )
        self.assertEqual(proc.returncode, EXIT_OK, proc.stderr.strip()[-400:])
        item = self.doctor_item(json.loads(proc.stdout))
        self.assertNotIn("could not run", item["reason"])
        self.assertEqual(item["findings"], [{"path": UNTAGGED, "check": 2}])

    def test_apply_accepts_the_plan_made_with_the_key(self):
        world = self.make_world()
        plan = self.dry_run(world)
        self.assertEqual(self.dry_run(world)["sha256"], plan["sha256"], "the plan is stable")
        code, out, err = self.apply(world, plan["sha256"])
        self.assertEqual(code, EXIT_OK, err.strip()[-400:])

    def test_key_bytes_are_never_printed(self):
        world = self.make_world()
        outputs = []
        for args in (("--dry-run",), ("--dry-run", "--json")):
            code, out, err = world.run(*args)
            self.assertEqual(code, EXIT_OK, err.strip()[-400:])
            outputs.extend((out, err))
        text = "\n".join(outputs)
        for form in (KEY.hex(), KEY.hex().upper(), base64.b64encode(KEY).decode(),
                     base64.b32encode(KEY).decode(), repr(KEY)):
            with self.subTest(form=form[:4]):
                self.assertNotIn(form, text)


if __name__ == "__main__":
    unittest.main()
