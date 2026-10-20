"""The local commit after a finished backlog job uses runner.commit_identity, never a built-in agent identity.

Contract (crlib/backlog.commit_local and its caller sched._reap_backlog):
  * runner.commit_identity "Name <address>" is used for author AND committer, and wins over the repo's git config.
  * Unset ("" or missing) or still the template placeholder "<your-name> <you@example.com>": the repo's own git
    config (user.name + user.email) is used.
  * Neither, or a malformed commit_identity: no commit; the job stays done and scheduler.jsonl gets an
    {"event": "commit_skipped", "job": <id>, "reason": ...} record whose reason names runner.commit_identity.
Git runs only inside the temp KIT_HOME (the sandbox's audit hook); global and system git config are ignored."""
import os, subprocess, unittest
import k5support as K
from k5support import TempEnv
from crlib import sched as S
from crlib.common import append_jsonl, log_path, read_jsonl, to_epoch

NOW = to_epoch("2026-10-18T12:00:00+03:00")
TEMPLATE = "<your-name> <you@example.com>"
CONFIGURED = ("Example Dev", "dev@example.com")
REPO = ("Example Repo User", "repo-user@example.org")


def git(cwd, *args):
    return subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=True, timeout=60)


class CommitIdentityTests(unittest.TestCase):
    def setUp(self):
        self.t = TempEnv().__enter__()
        for k in ("EMAIL", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            os.environ.pop(k, None)
        os.environ["CR_NOW"] = "2026-10-18T12:00:00+03:00"
        self.wt = os.path.join(self.t.d, "wt")
        r = subprocess.run(["git", "init", "-q", "-b", "main", self.wt], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.wt, "result.md"), "w") as f:
            f.write("example output\n")

    def tearDown(self):
        self.t.__exit__()

    def repo_identity(self, name, email):
        git(self.wt, "config", "user.name", name)
        git(self.wt, "config", "user.email", email)

    def finish_job(self, identity=None, drop_key=False):
        cfg = self.t.cfg
        if drop_key:
            cfg["runner"].pop("commit_identity", None)
        elif identity is not None:
            cfg["runner"]["commit_identity"] = identity
        doc = {"jobs": [{"id": "J1", "title": "example job", "commit": "yes", "worktree": self.wt}]}
        state = {"J1": {"status": "running", "run_id": "bl-J1-example", "pid": None, "attempts": 1}}
        append_jsonl(log_path(cfg, "runs.jsonl"), {"event": "finish", "run_id": "bl-J1-example", "rc": 0})
        try:
            S._reap_backlog(cfg, doc, state, NOW, procs_alive=lambda pid: False)
        except Exception as e:  # noqa: BLE001
            self.fail("_reap_backlog raised %s: %s" % (type(e).__name__, e))
        self.assertEqual(state["J1"]["status"], "done")
        return state["J1"]

    def head_identities(self):
        r = git(self.wt, "log", "-1", "--format=%an <%ae>%n%cn <%ce>")
        return r.stdout.strip().splitlines() if r.returncode == 0 else None

    def skipped_records(self):
        return [r for r in read_jsonl(log_path(self.t.cfg, "scheduler.jsonl")) if r.get("event") == "commit_skipped"]

    def assert_committed_as(self, v, name, email):
        self.assertTrue(v.get("commit"), "no commit recorded for the job")
        want = "%s <%s>" % (name, email)
        self.assertEqual(self.head_identities(), [want, want])
        self.assertEqual(self.skipped_records(), [])

    def assert_skipped(self, v):
        self.assertFalse(v.get("commit"), "a commit was made")
        self.assertIsNone(self.head_identities(), "the worktree got a commit")
        recs = self.skipped_records()
        self.assertEqual(len(recs), 1, "expected one commit_skipped record in scheduler.jsonl")
        self.assertEqual(recs[0].get("job"), "J1")
        self.assertIn("runner.commit_identity", recs[0].get("reason", ""))

    def test_configured_identity_is_used(self):
        v = self.finish_job("%s <%s>" % CONFIGURED)
        self.assert_committed_as(v, *CONFIGURED)

    def test_configured_identity_wins_over_repo_config(self):
        self.repo_identity(*REPO)
        v = self.finish_job("%s <%s>" % CONFIGURED)
        self.assert_committed_as(v, *CONFIGURED)

    def test_unset_identity_uses_repo_config(self):
        self.repo_identity(*REPO)
        self.assert_committed_as(self.finish_job(""), *REPO)

    def test_missing_key_uses_repo_config(self):
        self.repo_identity(*REPO)
        self.assert_committed_as(self.finish_job(drop_key=True), *REPO)

    def test_template_placeholder_counts_as_unset(self):
        self.repo_identity(*REPO)
        self.assert_committed_as(self.finish_job(TEMPLATE), *REPO)

    def test_neither_skips_the_commit_and_logs_why(self):
        self.assert_skipped(self.finish_job(""))

    def test_placeholder_and_no_repo_config_skips(self):
        self.assert_skipped(self.finish_job(TEMPLATE))

    def test_malformed_identity_skips_even_with_repo_config(self):
        for bad in ("Example Dev", "<dev@example.com>", "Example Dev <not-an-address>"):
            with self.subTest(identity=bad):
                self.fresh_worktree()
                self.repo_identity(*REPO)
                self.assert_skipped(self.finish_job(bad))

    def fresh_worktree(self):
        """A new worktree and empty logs for the next subTest (same TempEnv)."""
        import shutil
        shutil.rmtree(self.wt)
        for name in ("scheduler.jsonl", "runs.jsonl"):
            p = log_path(self.t.cfg, name)
            if os.path.exists(p):
                os.remove(p)
        subprocess.run(["git", "init", "-q", "-b", "main", self.wt], capture_output=True, timeout=60)
        with open(os.path.join(self.wt, "result.md"), "w") as f:
            f.write("example output\n")


if __name__ == "__main__":
    unittest.main()
