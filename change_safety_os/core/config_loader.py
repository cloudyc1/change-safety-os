from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


@dataclass(frozen=True)
class SafetyConfig:
    domains: Dict[str, Any]
    contracts: Dict[str, Any]
    guards: Dict[str, Any]
    probes: Dict[str, Any]
    risk_rules: Dict[str, Any]

    @classmethod
    def load(cls, config_dir: Path) -> "SafetyConfig":
        return cls(
            domains=_read_yaml(config_dir / "domains.yaml").get("domains", {}),
            contracts=_read_yaml(config_dir / "contracts.yaml").get("contracts", {}),
            guards=_read_yaml(config_dir / "guard-matrix.yaml").get("guards", {}),
            probes=_read_yaml(config_dir / "probe-registry.yaml").get("probes", {}),
            risk_rules=_read_yaml(config_dir / "risk-rules.yaml"),
        )

