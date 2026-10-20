"""Structure checks for the kit repo: layout, no submodules, .gitignore coverage, no secret-scanner
suppressions."""

import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The documented repo layout (README.md and the design layout).
LAYOUT_FILES = [
    "README.md",
    "AGENTS.md",
    "PARAMETERS.md",
    "kit.config.example.yaml",
    "LICENSE",
    "NOTICE",
    "VENDORED.md",
    "EXTERNAL-DEPENDENCIES.md",
    "CHANGELOG.md",
    ".gitignore",
    "onboarding/discovery-prompt.md",
    "onboarding/current-state.md",
    "second-brain/README.md",
    "second-brain/ROUTER.md",
    "second-brain/DOCTOR-SPEC.md",
    "routines/morning-brief.md",
    "agents/dev-lead/AGENT.md",
    "runner/DESIGN.md",
    "runner/TERMS-NOTICE.md",
    "runner/LICENSE",
    "runner/runner.config.example.json",
    "tools/ci_local.py",
    "tools/README.md",
]

LAYOUT_DIRS = [
    "onboarding",
    "second-brain",
    "second-brain/bin",
    "second-brain/dance-school",
    "second-brain/other-activities",
    "grok-skills/sb-lookup",
    "grok-skills/content-calendar-planner",
    "grok-skills/comms-template-writer",
    "routines",
    "agents/dev-lead",
    "runner",
    "runner/bin",
    "runner/fixtures",
    "vendor/accelerator",
    "vendor/folio",
    "tests/fixtures/existing-setup",
    "tools",
]

HOSTED_CI_PATHS = [
    ".github/workflows",
    ".gitlab-ci.yml",
    ".circleci",
    ".travis.yml",
    "azure-pipelines.yml",
    "bitbucket-pipelines.yml",
    "Jenkinsfile",
]

# Paths that must be ignored, and paths that must stay trackable.
IGNORED = [
    "kit.config.yaml",
    "runner/logs/run.log",
    "runner/logs/nested/run.log",
    "runner/backlog/task-1.md",
    "local.env",
    ".env",
    "runner/secrets.env",
    "__pycache__/mod.cpython-39.pyc",
    "tools/__pycache__/ci_local.cpython-39.pyc",
    "tools/stray.pyc",
]

NOT_IGNORED = [
    "kit.config.example.yaml",
    "runner/runner.config.example.json",
    "runner/DESIGN.md",
    "runner/bin/README.md",
    "tools/ci_local.py",
    "README.md",
]


# Files the secret scanners read to skip findings, rules or paths, and their inline markers.
# Joined at run time, so this file never holds a marker whole (a scanner would honour it here).
SCANNER_IGNORE_FILES = (
    "." + "gitleaks" + "ignore",
    "." + "gitleaks" + ".toml",
    "." + "trufflehog" + "ignore",
)
SCANNER_INLINE_MARKERS = (
    "gitleaks" + ":" + "allow",
    "trufflehog" + ":" + "ignore",
)


def _git(*args, cwd=ROOT):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )


def scanner_suppressions(root):
    """(ignore files, files holding an inline marker) among the files git tracks under root, as
    sorted paths relative to root. File names and markers match in any case; symlinks are not
    followed."""
    proc = subprocess.run(["git", "ls-files", "-z"], cwd=root, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError("git ls-files failed")
    names = set(name.lower() for name in SCANNER_IGNORE_FILES)
    markers = [marker.encode() for marker in SCANNER_INLINE_MARKERS]
    files, marked = [], []
    for raw in proc.stdout.split(b"\0"):
        if not raw:
            continue
        rel = os.fsdecode(raw)
        if os.path.basename(rel).lower() in names:
            files.append(rel)
        path = os.path.join(root, rel)
        if os.path.islink(path) or not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            data = handle.read().lower()
        if any(marker in data for marker in markers):
            marked.append(rel)
    return sorted(files), sorted(marked)


def _in_git_work_tree():
    if shutil.which("git") is None:
        return False
    proc = _git("rev-parse", "--is-inside-work-tree")
    return proc.returncode == 0 and proc.stdout.strip() == "true"


class LayoutTest(unittest.TestCase):
    def test_layout_files_exist(self):
        missing = [p for p in LAYOUT_FILES if not os.path.isfile(os.path.join(ROOT, p))]
        self.assertEqual(missing, [], "missing layout files")

    def test_layout_dirs_exist(self):
        missing = [p for p in LAYOUT_DIRS if not os.path.isdir(os.path.join(ROOT, p))]
        self.assertEqual(missing, [], "missing layout dirs")

    def test_grok_skills_have_skill_md(self):
        for name in ("sb-lookup", "content-calendar-planner", "comms-template-writer"):
            with self.subTest(skill=name):
                self.assertTrue(
                    os.path.isfile(os.path.join(ROOT, "grok-skills", name, "SKILL.md"))
                )

    def test_existing_setup_fixtures_present(self):
        folder = os.path.join(ROOT, "tests", "fixtures", "existing-setup")
        cases = sorted(n for n in os.listdir(folder) if n.startswith("case-"))
        self.assertGreaterEqual(len(cases), 6)


class NoSubmodulesTest(unittest.TestCase):
    def test_no_gitmodules(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, ".gitmodules")))

    def test_no_nested_git(self):
        nested = []
        for dirpath, dirnames, filenames in os.walk(ROOT):
            if dirpath == ROOT:
                # The repo's own .git (dir or worktree gitfile) is allowed.
                dirnames[:] = [d for d in dirnames if d != ".git"]
                continue
            if ".git" in dirnames or ".git" in filenames:
                nested.append(os.path.relpath(dirpath, ROOT))
            dirnames[:] = [d for d in dirnames if d != ".git"]
        self.assertEqual(nested, [], "nested .git found")

    def test_no_gitlink_entries(self):
        if not _in_git_work_tree():
            self.skipTest("not inside a git work tree")
        proc = _git("ls-files", "-s")
        self.assertEqual(proc.returncode, 0, "git ls-files failed")
        gitlinks = [
            line.split("\t", 1)[-1]
            for line in proc.stdout.splitlines()
            if line.startswith("160000 ")
        ]
        self.assertEqual(gitlinks, [], "gitlink (mode 160000) entries found")

    def test_no_hosted_ci_config(self):
        present = [p for p in HOSTED_CI_PATHS if os.path.exists(os.path.join(ROOT, p))]
        self.assertEqual(present, [], "hosted CI config found; CI is local only")


class GitignoreTest(unittest.TestCase):
    def setUp(self):
        if not _in_git_work_tree():
            self.skipTest("not inside a git work tree")
        self.assertTrue(os.path.isfile(os.path.join(ROOT, ".gitignore")))

    def _ignored(self, path):
        proc = _git("check-ignore", "-q", "--no-index", path)
        self.assertIn(proc.returncode, (0, 1), "git check-ignore error")
        return proc.returncode == 0

    def test_required_paths_ignored(self):
        for path in IGNORED:
            with self.subTest(path=path):
                self.assertTrue(self._ignored(path), "not ignored")

    def test_kit_files_not_ignored(self):
        for path in NOT_IGNORED:
            with self.subTest(path=path):
                self.assertFalse(self._ignored(path), "wrongly ignored")


class ScannerSuppressionTest(unittest.TestCase):
    """Nothing tracked may tell gitleaks or trufflehog to skip a finding, a rule or a path."""

    def setUp(self):
        if not _in_git_work_tree():
            self.skipTest("not inside a git work tree")

    def test_no_tracked_scanner_ignore_file(self):
        files, _ = scanner_suppressions(ROOT)
        self.assertEqual(files, [], "secret-scanner ignore or config file tracked")

    def test_no_tracked_inline_suppression_marker(self):
        _, marked = scanner_suppressions(ROOT)
        self.assertEqual(marked, [], "inline secret-scanner suppression marker in a tracked file")


class ScannerSuppressionPlantedTest(unittest.TestCase):
    """scanner_suppressions() finds what is planted in a temp git repo, so the checks above go red."""

    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("git not installed")

    def new_repo(self):
        repo = tempfile.mkdtemp(prefix="kit-structure-")
        self.addCleanup(shutil.rmtree, repo, True)
        self.assertEqual(_git("init", "-q", cwd=repo).returncode, 0, "git init failed")
        self.write(repo, "README.md", "Example\n", track=True)
        return repo

    def write(self, repo, rel, text, track):
        path = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        if track:
            self.assertEqual(_git("add", "--", rel, cwd=repo).returncode, 0, "git add failed")

    def test_clean_repo_has_none(self):
        self.assertEqual(scanner_suppressions(self.new_repo()), ([], []))

    def test_each_ignore_file_is_found_in_any_folder_and_case(self):
        for name in SCANNER_IGNORE_FILES:
            for rel in (name, os.path.join("deep", "dir", name), name.upper()):
                with self.subTest(rel=rel):
                    repo = self.new_repo()
                    self.write(repo, rel, "x\n", track=True)
                    self.assertEqual(scanner_suppressions(repo), ([rel], []))

    def test_each_inline_marker_is_found_in_any_case(self):
        for marker in SCANNER_INLINE_MARKERS:
            for text in ("value = 1  # " + marker + "\n", "<!-- " + marker.upper() + " -->\n"):
                with self.subTest(marker=marker.split(":")[0], upper=text.startswith("<")):
                    repo = self.new_repo()
                    rel = os.path.join("src", "settings.py")
                    self.write(repo, rel, text, track=True)
                    self.assertEqual(scanner_suppressions(repo), ([], [rel]))

    def test_untracked_files_do_not_count(self):
        repo = self.new_repo()
        self.write(repo, SCANNER_IGNORE_FILES[0], "x\n", track=False)
        self.write(repo, "notes.md", SCANNER_INLINE_MARKERS[0] + "\n", track=False)
        self.assertEqual(scanner_suppressions(repo), ([], []))

    def test_longer_names_are_not_ignore_files(self):
        repo = self.new_repo()
        for name in SCANNER_IGNORE_FILES:
            self.write(repo, name + ".md", "x\n", track=True)
            self.write(repo, "x" + name, "x\n", track=True)
        self.assertEqual(scanner_suppressions(repo), ([], []))


if __name__ == "__main__":
    unittest.main()
