# Change Safety OS Design

## Objective

Reduce side effects in autonomous coding by adding an executable safety layer
around delivery. The layer must be project-agnostic, loosely coupled, and usable
without changing runtime business code. It does not stop an agent from editing
code; it stops an agent from delivering code until the target change works and
adjacent workflows have not regressed.

## Core idea

Side effects usually happen when a change touches shared state, shared helpers,
or protocol fields while only the direct workflow is tested. Change Safety OS
therefore makes every change run an auditable fix loop:

1. What is being changed.
2. Which workflows are affected.
3. Which protected protocol fields were touched.
4. Which contracts and invariants are at risk.
5. Which adjacent callers can be affected by changed symbols.
6. Which guards prove the direct and adjacent workflows still work.
7. Whether the agent should keep working, ask for human decision, or deliver.

## Architecture

### Config layer

`config/domains.yaml` maps file patterns to workflow domains. Each domain owns:

- risk level,
- adjacent domains,
- protocol contracts,
- required guards.

`config/contracts.yaml` stores invariants. These are not comments in code; they
are the contract checklist that every high-risk change must preserve.

`config/guard-matrix.yaml` stores test commands. A guard can run one or more
commands. Guards are selected by impacted domains.

`config/probe-registry.yaml` stores additional smoke probes. Probes are useful
when a workflow requires manual or device-level verification.

### Execution layer

The `bin/` scripts are the stable entry points:

- `start_change.py`: create a report directory and state file.
- `scan_impact.py`: scan changed files and update impact radius.
- `run_guards.py`: run required automated guards.
- `run_probes.py`: run or dry-run smoke probes.
- `check_contracts.py`: add contract review checklist and protected field hits.
- `trace_callers.py`: trace adjacent callers for changed symbols.
- `ack_contracts.py`: mark contract review as completed.
- `add_gap.py`: record an unchecked verification gap.
- `factory_gate.py`: run the full gate in one command.
- `finalize_change.py`: produce delivery-loop decision.

### State layer

Every run writes:

- `state.json`: machine-readable state.
- `change-safety-record.md`: human-readable audit report.

The state file is intentionally simple JSON so any agent, CI job, or external
orchestrator can read and modify it.

## Decision policy

- `critical` or `high` changes return `needs_work` unless required guards are `passed`.
- `critical` or `high` changes return `needs_work` unless impacted contracts are `reviewed`.
- `planned` dry-run results are not treated as proof.
- Any failed guard returns `needs_work`.
- Recorded unchecked gaps return `needs_human_decision`.
- Only `ready_to_deliver` means the original target and side-effect checks are both satisfied.
- A final answer must not claim "no side effects" if any gap remains.

## Integration in a 24-hour code factory

Recommended autonomous loop:

1. Create a safety record before editing.
2. Make the code change needed to actually fix the target bug or feature.
3. Scan impact after edits.
4. Check contracts and protected fields.
5. Trace adjacent callers.
6. Run guards selected by the scanner.
7. Run probes or record explicit gaps.
8. Acknowledge reviewed contracts.
9. Finalize.
10. If `needs_work`, continue editing and repeat from step 3.
11. Only `ready_to_deliver` allows commit, push, merge, or final handoff.

## Why this is not only tests

Tests prove selected behavior. Change Safety OS decides which tests and probes
are required for the actual touched surface. It turns "remember to check side
effects" into a deterministic gate.

## Extension points

- Add a new domain when a workflow starts sharing state with other workflows.
- Add a new contract when a protocol field gains business meaning.
- Add a guard when a regression would be costly.
- Add a probe when automated tests cannot cover a real browser, device, or
production-like workflow.
