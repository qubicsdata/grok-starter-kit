#!/usr/bin/env python3
"""Export reviewed tracked source, without Git history, workflows, logs or local data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED = ('.github/', '.super' + 'powers/', '.worktrees/', '.scratch/', 'docs/acceptance/', 'docs/superpowers/', 'dist/', 'build/', 'workspace/', 'demo-workspace/')


def host_patterns(environ=None, home=None):
    """The scan patterns, with this host's home and private temp directory taken from the environment.

    No literal home or temp path lives in this file (R-b): the personal-home pattern uses the
    account name of `home` (default Path.home()), and the temporary-host-path pattern is the
    resolved $TMPDIR (macOS gives every account a private one), absent when TMPDIR is unset.
    """
    environ = os.environ if environ is None else environ
    home = Path(home) if home is not None else Path.home()
    patterns = {
        'private-key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
        'github-token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
        'provider-token': re.compile(r'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{32,}\b'),
        'personal-home': re.compile(r'/(?:Users|home)/' + re.escape(home.name) + r'(?:\.guest)?(?:/|\b)'),
    }
    temporary = environ.get('TMPDIR')
    if temporary:
        patterns['temporary-host-path'] = re.compile(re.escape(str(Path(temporary).resolve())) + '/')
    return patterns


PATTERNS = host_patterns()


def included(name):
    if name.startswith(EXCLUDED) or name.endswith(('.log', '.pyc')):
        return False
    if name.startswith('docs/releases/') and name != 'docs/releases/1.1.0.md':
        return False
    if name == 'docs/mac-readiness-2026-09-18.md':
        return False
    return True


def scan(root, patterns=None):
    patterns = PATTERNS if patterns is None else patterns
    findings = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Source exports do not permit symbolic links: ' + str(path.relative_to(root)))
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        for kind, pattern in patterns.items():
            if pattern.search(content):
                findings.append({'file': str(path.relative_to(root)), 'pattern': kind})
    return findings


def export_source(output):
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('The destination must not exist; existing repositories are never overwritten.')
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    source_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.folio-source-', dir=output.parent) as temporary:
        stage = Path(temporary) / 'source';stage.mkdir()
        copied, excluded = [], []
        for name in filter(None, files):
            if not included(name):
                excluded.append(name);continue
            source = ROOT / name
            if source.is_symlink() or not source.is_file():
                raise ValueError('Invalid tracked source file: ' + name)
            target = stage / name;target.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(source,target);copied.append(name)
        findings = scan(stage)
        if findings:
            raise ValueError('Source scan refused publication; finding locations only: ' + json.dumps(findings))
        manifest = {'format':1,'product':'Folio','version':'1.1.0','license':'Apache-2.0','destination_repository':'example-org/folio-distribution','upstream_reviewed_commit':source_commit,'git_history_included':False,'github_actions_included':False,'copied_files':len(copied),'excluded_paths':excluded,'scan':{'finding_count':0,'patterns':list(PATTERNS),'binary_files_preserved':True},'files':{name:hashlib.sha256((stage/name).read_bytes()).hexdigest() for name in copied}}
        (stage/'SOURCE-EXPORT.json').write_text(json.dumps(manifest,indent=2)+'\n')
        os.rename(stage,output)
    print(json.dumps({'ok':True,'files':len(copied),'source_commit':source_commit,'history_included':False,'scan_findings':0}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args();export_source(args.output)
