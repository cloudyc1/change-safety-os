from __future__ import annotations

import fnmatch
from dataclasses import asdict, dataclass
from typing import Iterable, List

from change_safety_os.core.config_loader import SafetyConfig


RISK_ORDER = ["low", "medium", "high", "critical"]


@dataclass(frozen=True)
class ImpactScanResult:
    files: List[str]
    domains: List[str]
    adjacent_domains: List[str]
    contracts: List[str]
    required_guards: List[str]
    risk: str

    def to_dict(self) -> dict:
        return asdict(self)


def _matches(path: str, pattern: str) -> bool:
    normalized_path = path.strip().lstrip("./")
    normalized_pattern = pattern.strip().lstrip("./")
    return fnmatch.fnmatch(normalized_path, normalized_pattern)


def _max_risk(current: str, candidate: str) -> str:
    current_index = RISK_ORDER.index(current) if current in RISK_ORDER else 0
    candidate_index = RISK_ORDER.index(candidate) if candidate in RISK_ORDER else 0
    return candidate if candidate_index > current_index else current


def scan_files(files: Iterable[str], config: SafetyConfig) -> ImpactScanResult:
    changed_files = sorted({str(path).strip().lstrip("./") for path in files if str(path).strip()})
    domains = set()
    adjacent = set()
    contracts = set()
    guards = set()
    risk = "low"

    for domain_name, domain in (config.domains or {}).items():
        patterns = domain.get("files") or []
        if any(_matches(path, pattern) for path in changed_files for pattern in patterns):
            domains.add(str(domain_name))
            adjacent.update(str(item) for item in (domain.get("adjacent_domains") or []))
            contracts.update(str(item) for item in (domain.get("contracts") or []))
            guards.update(str(item) for item in (domain.get("guards") or []))
            risk = _max_risk(risk, str(domain.get("risk") or "low"))

    return ImpactScanResult(
        files=changed_files,
        domains=sorted(domains),
        adjacent_domains=sorted(adjacent - domains),
        contracts=sorted(contracts),
        required_guards=sorted(guards),
        risk=risk,
    )

