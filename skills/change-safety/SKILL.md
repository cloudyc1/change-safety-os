---
name: change-safety
description: Use when implementing or fixing code that may affect shared behavior, persisted state, workflow status, queues, permissions, navigation, external integrations, production regressions, suspected side effects, or when the user asks to avoid breaking adjacent behavior.
---

# Change Safety Skill

Use this skill before and after non-trivial code changes. It is project-agnostic:
it does not define which domains are high risk for a project and it does not
restrict which files can be edited. It forces an explicit impact loop so the
target change is completed without silently breaking adjacent workflows.

## Trigger Decision

Use the skill by default for:

- Bug fixes, features, refactors, shared helpers, workflow state, persisted
  fields, schedulers, queues, permissions, navigation, external APIs,
  production regressions, and suspected side effects.
- Any change touching files or state read by more than one user-facing workflow.
- Any request where the user says the change must not affect existing behavior,
  asks whether a bug is a side effect, or reports an unexpected regression after
  a recent change.

Skip only for pure documentation, comments, static copy, or isolated styling that
cannot alter runtime behavior. If unsure, use the skill.

## Project Discovery

Before applying CSO commands, discover the project's local rules:

1. Read the repo's `AGENTS.md`, `CLAUDE.md`, or equivalent agent instructions.
2. If present, read `change-safety-os/config/domains.yaml` to learn project
   domains, file patterns, adjacent workflows, contracts, and guards.
3. If present, use `change-safety-os/config/contracts.yaml`,
   `guard-matrix.yaml`, and `probe-registry.yaml` as the source of truth for
   local verification.
4. If CSO config is missing, use this skill as a manual checklist and recommend
   initializing project-specific config before relying on automated graph output.

## Install CSO for a Project

When the user asks to install CSO:

1. Put this skill folder at `~/.codex/skills/change-safety/`.
2. Ensure the project has the CSO CLI directory at `change-safety-os/` or install
   a packaged `cso` command if available.
3. Merge `change-safety-os/templates/agents-snippet.md` into the project's
   `AGENTS.md`, adapting project-specific high-risk workflows, fields, and
   required checks.
4. Confirm the project can run `python3 change-safety-os/bin/finalize_change.py`.

If the repository only contains the skill but not the CLI, explain that the skill
can guide behavior but the executable safety checks require the CSO CLI package
or the `change-safety-os/` directory.

## Before editing

1. Read project-local safety instructions and CSO config if they exist.
2. Start a record:

   `python3 change-safety-os/bin/start_change.py --goal "<goal>"`

3. State the exact in-scope workflow.
4. State adjacent workflows that share files, helpers, routes, state, storage,
   queues, permissions, or external integrations.
5. If the project has a CSO graph, query it with
   `python3 change-safety-os/bin/query_graph.py --file <changed-file>` or
   `python3 change-safety-os/bin/query_graph.py --domain <domain>`.
6. Refresh the graph with `python3 change-safety-os/bin/build_graph.py` after
   changing CSO config.
7. If a shared helper must change, explain why every caller should receive the
   new behavior. Otherwise add a narrower helper or handle the case at the call
   site.
8. Continue with the requested implementation only after the scope and adjacent
   workflows are clear.

## After editing

1. Scan impact:

   `python3 change-safety-os/bin/scan_impact.py`

2. Check contracts and protected fields:

   `python3 change-safety-os/bin/check_contracts.py`

3. Trace adjacent callers:

   `python3 change-safety-os/bin/trace_callers.py`

4. Use the graph summary from `scan_impact` as a review checklist, not as a hard
   edit boundary.

5. Run required guards:

   `python3 change-safety-os/bin/run_guards.py`

6. Run probes or explicitly record gaps:

   `python3 change-safety-os/bin/run_probes.py --dry-run`

7. After reading the contract checklist, acknowledge reviewed contracts:

   `python3 change-safety-os/bin/ack_contracts.py --note "<what was checked>"`

8. Finalize:

   `python3 change-safety-os/bin/finalize_change.py`

## Completion rule

Do not claim completion unless finalization returns `ready_to_deliver` and the
relevant adjacent workflows were actually checked. If finalization returns
`needs_work`, keep editing and validating. If it returns `needs_human_decision`,
state the unresolved gap and ask whether delivery is acceptable.

If the target bug is fixed but a side effect is found, keep working: narrow the
change, repair the side effect, rerun the relevant checks, and finalize again.
