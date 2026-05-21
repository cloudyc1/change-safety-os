# Optional AGENTS.md Snippet

Use this snippet if the project wants Change Safety OS to become mandatory.

```md
## Change Safety OS

Use the `change-safety` skill before and after non-trivial code changes. Trigger
it by default for bug fixes, features, refactors, shared helpers, persisted
state, workflow status, scheduling, queues, billing, permissions, frontend
navigation, external integrations, production regressions, and suspected side
effects.

Project-specific high-risk domains, protocol fields, contracts, and verification
commands must live in this repo's `AGENTS.md` and `change-safety-os/config/*.yaml`.
Do not put one project's domain rules into the global skill.

Before editing code for any non-trivial task, start a safety record:

`python3 change-safety-os/bin/start_change.py --goal "<goal>"`

If the project has a CSO graph, query the affected file or domain before editing:

`python3 change-safety-os/bin/query_graph.py --file "<path>"`

Refresh the graph after safety config changes:

`python3 change-safety-os/bin/build_graph.py`

Before editing shared helpers, workflow state, queues, billing, publishing, UI navigation, permissions, external integrations, or persisted state, run:

`python3 change-safety-os/bin/scan_impact.py`

Then run contract and caller checks:

`python3 change-safety-os/bin/check_contracts.py`

`python3 change-safety-os/bin/trace_callers.py`

For high or critical impact changes, run required guards:

`python3 change-safety-os/bin/run_guards.py`

After reading the generated contract checklist:

`python3 change-safety-os/bin/ack_contracts.py --note "<reviewed items>"`

Before final handoff, run:

`python3 change-safety-os/bin/finalize_change.py`

If finalization returns `needs_work`, keep fixing and do not claim completion. Either run missing guards, fix the discovered side effect, narrow the change, or explicitly record unchecked gaps for human decision.
```
