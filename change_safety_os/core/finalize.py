from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from change_safety_os.core.change_context import ChangeContext
from change_safety_os.core.report_writer import ReportWriter


class FinalizeDecision:
    READY_TO_DELIVER = "ready_to_deliver"
    NEEDS_HUMAN_DECISION = "needs_human_decision"
    NEEDS_WORK = "needs_work"

    # Backward-compatible aliases for older reports/tests.
    ALLOWED = READY_TO_DELIVER
    ALLOWED_WITH_GAPS = NEEDS_HUMAN_DECISION
    BLOCKED = NEEDS_WORK


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str
    missing_guards: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "reason": self.reason,
            "missing_guards": self.missing_guards,
        }


def finalize_change(context: ChangeContext) -> Decision:
    state = context.state
    impact = state.get("impact") or {}
    risk = str(impact.get("risk") or "low")
    required_guards = list(impact.get("required_guards") or [])
    required_contracts = list(impact.get("contracts") or [])
    guards = state.get("guards") or {}
    gaps = list(state.get("unchecked_gaps") or [])
    contract_reviews = state.get("contract_reviews") or {}

    missing_guards = [guard for guard in required_guards if (guards.get(guard) or {}).get("status") != "passed"]
    failed_guards = [name for name, result in guards.items() if (result or {}).get("status") == "failed"]
    pending_contracts = [
        contract
        for contract in required_contracts
        if (contract_reviews.get(contract) or {}).get("status") != "reviewed"
    ]
    if failed_guards:
        decision = Decision(
            status=FinalizeDecision.NEEDS_WORK,
            reason=f"side-effect guard failed; keep fixing before delivery: {', '.join(sorted(failed_guards))}",
            missing_guards=missing_guards,
        )
    elif risk in {"high", "critical"} and missing_guards:
        decision = Decision(
            status=FinalizeDecision.NEEDS_WORK,
            reason=f"required guards have not passed; continue the fix loop: {', '.join(missing_guards)}",
            missing_guards=missing_guards,
        )
    elif risk in {"high", "critical"} and pending_contracts:
        decision = Decision(
            status=FinalizeDecision.NEEDS_WORK,
            reason=f"contracts have not been reviewed; review them before delivery: {', '.join(pending_contracts)}",
            missing_guards=missing_guards,
        )
    elif gaps:
        decision = Decision(
            status=FinalizeDecision.NEEDS_HUMAN_DECISION,
            reason="target may be fixed, but unchecked gaps need human delivery decision",
            missing_guards=missing_guards,
        )
    else:
        decision = Decision(
            status=FinalizeDecision.READY_TO_DELIVER,
            reason="target fix and side-effect checks are both ready for delivery",
            missing_guards=missing_guards,
        )

    ReportWriter(context).update_state(decision=decision.to_dict())
    return decision
