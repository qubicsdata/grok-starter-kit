# workspace-companion

Cross-repo workspace mapping — service dependency graph, large-codebase navigation, and dependency-ordered cross-repo change planning. Backed by an auto-bootstrapped `.accelerator-workspace.yaml` manifest that describes all repos, services, and their cross-repo dependencies in a single source of truth.

## Installation

workspace-companion is installed as part of the accelerator plugin suite.

## Usage

Start by bootstrapping your workspace with `/workspace-init`, which scans all repos and generates `.accelerator-workspace.yaml`. Then use `/impact` to understand the blast radius of changes, or `/cross-repo-plan` to get a dependency-ordered sequence of per-repo changes.

Example:
```bash
# Initialize workspace (scans for git repos and generates manifest)
/workspace-init root=/path/to/workspace

# See the blast radius of changing a service
/impact my-service

# Get a cross-repo change plan
/cross-repo-plan "add authentication to api service"

# Refresh the manifest after repos change
/workspace-map root=/path/to/workspace

# Find a symbol/file/string across workspace repos
/find "EventBus"
```

## Dependencies

- requires: ai-baseline

## Commands

- `/workspace-init [root=<path>]` — Bootstrap a workspace, scan repos, generate the manifest
- `/workspace-map [root=<path>]` — Refresh the manifest from current repo state
- `/impact <service>` — Blast-radius report for changing a service
- `/cross-repo-plan <change description>` — Dependency-ordered cross-repo change plan
- `/find <query>` — Find a symbol/file/string across workspace repos

## Author

<your-name> (you@example.com)
