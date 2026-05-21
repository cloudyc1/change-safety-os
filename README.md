# Change Safety OS

Change Safety OS (CSO) is a project-agnostic safety layer for AI-assisted code changes.
It helps agents identify impact, trace adjacent workflows, run project-specific checks,
and avoid shipping unintended side effects.

CSO does not restrict which files an agent can edit. It makes the agent prove that the
target change works and that adjacent behavior was checked.

## What Is Included

- `skills/change-safety/SKILL.md`: Codex skill that triggers on risky code changes.
- `cso`: packaged CLI for starting records, scanning impact, graph queries, guards, probes, and finalization.
- `bin/*.py`: compatibility entry points for cloned-repo usage.
- `change_safety_os/`: Python implementation.
- `config/*.yaml`: generic starter config. Replace with project-specific domains, contracts, and checks.
- `templates/agents-snippet.md`: AGENTS.md snippet for making CSO mandatory in a repo.
- `tests/`: unit tests for the CSO tool itself.

## Install

When the package is published to PyPI:

```bash
python3 -m pip install change-safety-os
```

The package name is `change-safety-os`; the installed command is `cso`.
Do not use `pip install cso` unless you intentionally want a different package
with that PyPI name.

Before PyPI release, install directly from GitHub:

```bash
python3 -m pip install "git+https://github.com/cloudyc1/change-safety-os.git"
```

Then initialize CSO inside each target project:

```bash
cd /path/to/project
cso init
```

`cso init` creates `./change-safety-os/config`, `./change-safety-os/templates`,
and installs the global Codex skill to `~/.codex/skills/change-safety/SKILL.md`.
Finally merge `change-safety-os/templates/agents-snippet.md` into the target project's
`AGENTS.md`.

If `cso` is not found after installation, add the Python scripts directory printed
by `python3 -m site --user-base` plus `/bin` to `PATH`, or invoke the script by its
absolute path. If you use pyenv, make sure the Python version used for installation
is active, then run `pyenv rehash`.

## One-Prompt Install

In a target project, you can ask Codex:

```text
Install CSO:
1. Run python3 -m pip install git+https://github.com/cloudyc1/change-safety-os.git
   unless change-safety-os is already available from PyPI.
2. Run cso init in this repository.
3. Merge change-safety-os/templates/agents-snippet.md into AGENTS.md.
4. Adapt change-safety-os/config/*.yaml to this project's domains, contracts, and checks.
```

## Configure A Project

The default config is intentionally generic and should be adapted.

Edit these files inside the target project:

- `change-safety-os/config/domains.yaml`: map project file patterns to domains and adjacent domains.
- `change-safety-os/config/contracts.yaml`: define invariants that must be reviewed before delivery.
- `change-safety-os/config/guard-matrix.yaml`: replace placeholder guard commands with real test/build commands.
- `change-safety-os/config/probe-registry.yaml`: add optional smoke probes.
- `change-safety-os/config/risk-rules.yaml`: define protected field names that require extra review.

The global skill should stay generic. Project-specific high-risk workflows and fields belong in
the target project's `AGENTS.md` and `change-safety-os/config/*.yaml`.

## Basic Workflow

Run these commands from the target project root.

```bash
cso start --goal "fix checkout retry bug"
cso graph query --file backend/services/orders.py
cso scan
cso contracts
cso trace
cso guards
cso probes --dry-run
cso ack --note "reviewed impacted contracts"
cso finalize
```

For autonomous or one-shot use:

```bash
cso run --goal "fix checkout retry bug" --dry-run
```

`cso finalize` returns one of:

- `ready_to_deliver`: target change and side-effect checks are ready.
- `needs_work`: keep fixing, testing, or narrowing the change.
- `needs_human_decision`: the target may be fixed, but a recorded gap needs human acceptance.

## Workflow Graph

Build or refresh the graph after changing CSO config:

```bash
cso graph build
cso graph update
```

Query by file or domain:

```bash
cso graph query --file backend/services/orders.py
cso graph query --domain workflow_jobs
```

The graph is a review checklist, not an edit permission boundary. If the graph is incomplete,
fall back to code search and update `config/*.yaml`.

## Run CSO Tool Checks

From this repository root:

```bash
python3 -m compileall change_safety_os bin
python3 -m pytest tests -q
```

Dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Local package validation for maintainers:

```bash
python3 -m pip install -e .
cso --help
```

This installs the current checkout in editable mode only to verify packaging.
It is not the user-facing install command. End users should use
`python3 -m pip install change-safety-os` after PyPI publishing, or the GitHub
install command before publishing.

## License

MIT License
