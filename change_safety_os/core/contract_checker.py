from __future__ import annotations

from typing import Dict

from change_safety_os.core.config_loader import SafetyConfig


def check_contracts(impact: dict, config: SafetyConfig) -> Dict[str, dict]:
    reviews: Dict[str, dict] = {}
    for contract_name in sorted(impact.get("contracts") or []):
        contract = (config.contracts or {}).get(contract_name) or {}
        reviews[str(contract_name)] = {
            "status": "review_required",
            "owner": str(contract.get("owner") or ""),
            "invariants": list(contract.get("invariants") or []),
            "requires": list(contract.get("requires") or []),
        }
    return reviews
