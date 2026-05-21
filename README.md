# Change Safety OS

Change Safety OS (CSO) is a project-agnostic safety layer for AI-assisted code changes.
It helps agents identify impact, trace adjacent workflows, run project-specific checks,
and avoid shipping unintended side effects.

CSO does not restrict which files an agent can edit. It makes the agent prove that the
target change works and that adjacent behavior was checked.

## What Is Included

- `skills/change-safety/SKILL.md`: Codex skill that triggers on risky code changes.
- `bin/*.py`: CLI entry points for starting records, scanning impact, graph queries, guards, probes, and finalization.
- `change_safety_os/`: Python implementation.
- `config/*.yaml`: generic starter config. Replace with project-specific domains, contracts, and checks.
- `templates/agents-snippet.md`: AGENTS.md snippet for making CSO mandatory in a repo.
- `tests/`: unit tests for the CSO tool itself.

## Install For Codex

From a cloned copy of this repository:

```bash
mkdir -p ~/.codex/skills/change-safety
cp skills/change-safety/SKILL.md ~/.codex/skills/change-safety/SKILL.md
```

Then copy this repository's contents into the target project as `change-safety-os/`.
Do not copy the `.git` directory into the target project.

Example:

```bash
git clone https://github.com/cloudyc1/change-safety-os.git /tmp/change-safety-os
mkdir -p /path/to/project/change-safety-os
rsync -a --exclude='.git/' /tmp/change-safety-os/ /path/to/project/change-safety-os/
```

Finally merge `templates/agents-snippet.md` into the target project's `AGENTS.md`.

## One-Prompt Install

In a target project, you can ask Codex:

```text
Install CSO from https://github.com/cloudyc1/change-safety-os:
1. Copy skills/change-safety/SKILL.md to ~/.codex/skills/change-safety/SKILL.md.
2. Copy the repository contents into ./change-safety-os.
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
python3 change-safety-os/bin/start_change.py --goal "fix checkout retry bug"
python3 change-safety-os/bin/query_graph.py --file backend/services/orders.py
python3 change-safety-os/bin/scan_impact.py
python3 change-safety-os/bin/check_contracts.py
python3 change-safety-os/bin/trace_callers.py
python3 change-safety-os/bin/run_guards.py
python3 change-safety-os/bin/run_probes.py --dry-run
python3 change-safety-os/bin/ack_contracts.py --note "reviewed impacted contracts"
python3 change-safety-os/bin/finalize_change.py
```

`finalize_change.py` returns one of:

- `ready_to_deliver`: target change and side-effect checks are ready.
- `needs_work`: keep fixing, testing, or narrowing the change.
- `needs_human_decision`: the target may be fixed, but a recorded gap needs human acceptance.

## Workflow Graph

Build or refresh the graph after changing CSO config:

```bash
python3 change-safety-os/bin/build_graph.py
```

Query by file or domain:

```bash
python3 change-safety-os/bin/query_graph.py --file backend/services/orders.py
python3 change-safety-os/bin/query_graph.py --domain workflow_jobs
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

## License

MIT License
