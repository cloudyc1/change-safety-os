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

`cso start --goal "<goal>"`

If the project has a CSO graph, query the affected file or domain before editing:

`cso graph query --file "<path>"`

Refresh the graph after safety config changes:

`cso graph update`

Before editing shared helpers, workflow state, queues, billing, publishing, UI navigation, permissions, external integrations, or persisted state, run:

`cso scan`

Then run contract and caller checks:

`cso contracts`

`cso trace`

For high or critical impact changes, run required guards:

`cso guards`

After reading the generated contract checklist:

`cso ack --note "<reviewed items>"`

Before final handoff, run:

`cso finalize`

If finalization returns `needs_work`, keep fixing and do not claim completion. Either run missing guards, fix the discovered side effect, narrow the change, or explicitly record unchecked gaps for human decision.
```
