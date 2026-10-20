#!/usr/bin/env python3
"""Structural validator for agent-builder plugin. Run from repo root."""
import json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'agent-builder')

PASS, FAIL = [], []

def check(cond, msg):
    if cond:
        PASS.append(msg)
    else:
        FAIL.append(msg)
    return cond

def frontmatter_fields(path, *fields):
    try:
        with open(path) as f:
            content = f.read()
    except OSError as e:
        check(False, f'{path}: unreadable ({e})')
        return
    if not content.startswith('---'):
        check(False, f'{path}: missing frontmatter')
        return
    parts = content.split('---', 2)
    if len(parts) < 3:
        check(False, f'{path}: malformed frontmatter (no closing ---)')
        return
    header = parts[1]
    for field in fields:
        check(bool(re.search(rf'^{re.escape(field)}:\s', header, re.MULTILINE)),
              f'{path}: frontmatter has "{field}"')

def run():
    # plugin.json
    pj = os.path.join(ROOT, '.claude-plugin', 'plugin.json')
    if not check(os.path.exists(pj), 'plugin.json exists'):
        report(); return
    try:
        with open(pj) as f:
            m = json.load(f)
    except json.JSONDecodeError as e:
        check(False, f'plugin.json is valid JSON: {e}')
        report()
        return
    for field in ['name', 'version', 'description', 'category', 'author']:
        check(field in m, f'plugin.json has "{field}"')
    check(isinstance(m.get('author'), dict), 'plugin.json author is object')
    author = m.get('author')
    check('name' in author if isinstance(author, dict) else False, 'plugin.json author.name present')

    # required files
    required = [
        'agents/builder-orchestrator.md',
        'agents/domain-researcher.md',
        'agents/intake-agent.md',
        'agents/design-agent.md',
        'agents/generate-agent.md',
        'agents/critic-agent.md',
        'agents/auditor-agent.md',
        'agents/publisher-agent.md',
        'agents/test-agent.md',
        'agents/panel/security-reviewer.md',
        'agents/panel/ux-reviewer.md',
        'agents/panel/topology-reviewer.md',
        'skills/plugin-structure-spec.md',
        'skills/best-practices-index.md',
        'skills/task-scoring.md',
        'skills/checkpoint-gate.md',
        'skills/runtime-knowledge-fetch.md',
        'skills/version-self-check.md',
        'skills/domain-research-searches.md',
        'skills/archetype-selection.md',
        'skills/archetype-usage.md',
        'commands/build-agent.md',
        'README.md',
    ]
    for rel in required:
        path = os.path.join(ROOT, rel)
        if check(os.path.exists(path), f'{rel} exists'):
            if rel.startswith('agents/'):
                frontmatter_fields(path, 'name', 'description')
            elif rel.startswith('skills/'):
                frontmatter_fields(path, 'name', 'description')
            elif rel.startswith('commands/'):
                frontmatter_fields(path, 'description')

    report()

def report():
    print(f'\nPASS: {len(PASS)}  FAIL: {len(FAIL)}')
    for msg in FAIL:
        print(f'  FAIL  {msg}')
    sys.exit(len(FAIL))

if __name__ == '__main__':
    run()
