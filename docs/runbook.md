# Change Safety OS Runbook

## Normal change

```bash
cso start --goal "describe the change"
cso evidence --kind reproduction --text "what failed before the change"
cso scan
cso contracts
cso trace
cso guards
cso probes --dry-run
cso ack --note "reviewed changed contracts"
cso finalize
```

If finalization prints `decision=needs_work`, keep fixing and do not hand off
as complete.

## Temporary local scan

Use a temporary report root when you do not want report files in the repository:

```bash
cso start --goal "temporary scan" --report-root /private/tmp/change-safety-reports
cso scan --report-root /private/tmp/change-safety-reports
cso contracts --report-root /private/tmp/change-safety-reports
cso trace --report-root /private/tmp/change-safety-reports
cso guards --report-root /private/tmp/change-safety-reports --dry-run
cso finalize --report-root /private/tmp/change-safety-reports
```

Expected behavior for high-risk dry-run only: finalization returns `needs_work`
because `planned` is not proof and contracts are not reviewed.

## One-command gate

```bash
cso run --goal "describe the change" --dry-run
```

This runs impact scanning, contract checks, protected field scanning, caller
tracing, guard selection, probe selection, and finalization. In `--dry-run`, it
must return `needs_work` for high-risk changes because selected guards are only
planned.

## Review contracts

After reading the generated `Contract Review` section in the markdown report:

```bash
cso ack --note "reviewed protocol invariants and adjacent workflows"
```

Only acknowledge contracts after checking the listed invariants against the code
change. This is intentionally separate from automated tests.

## Add a domain

1. Add file patterns to `config/domains.yaml`.
2. Add adjacent domains.
3. Add contracts.
4. Add guards.
5. Run `cso scan --files <path>` to verify mapping.

## Add a guard

1. Add a named guard to `config/guard-matrix.yaml`.
2. Attach it to one or more domains in `config/domains.yaml`.
3. Run `cso guards --dry-run` and confirm the command is selected.
4. Run the guard for real before trusting it.

## Record an unchecked gap

Edit the current report's `state.json`:

```json
{
  "unchecked_gaps": [
    "manual integration smoke test not run because the test account was unavailable"
  ]
}
```

Then run `cso finalize` again. The decision should become
`needs_human_decision` only if required guards passed.

## Factory policy

For autonomous agents, treat `decision=needs_work` as a hard delivery stop, not
an editing stop. The next action must be one of:

- run the missing guards,
- narrow the code change and rescan,
- fix the discovered side effect and rescan,
- ask for human approval with explicit gaps.
