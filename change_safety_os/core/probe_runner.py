from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

from change_safety_os.adapters.shell_adapter import run_command
from change_safety_os.core.config_loader import SafetyConfig


def select_required_probes(domains: Iterable[str], config: SafetyConfig) -> list[str]:
    domain_set = set(domains)
    selected = []
    for probe_name, probe in (config.probes or {}).items():
        required_for = set(probe.get("required_for") or [])
        if domain_set & required_for:
            selected.append(str(probe_name))
    return sorted(selected)


def run_required_probes(
    probe_names: Iterable[str],
    config: SafetyConfig,
    *,
    cwd: Path,
    dry_run: bool = False,
) -> Dict[str, dict]:
    results: Dict[str, dict] = {}
    for probe_name in sorted(set(probe_names)):
        probe = (config.probes or {}).get(probe_name) or {}
        command = str(probe.get("command") or "").strip()
        if not command:
            results[probe_name] = {"status": "skipped", "reason": "missing command"}
            continue
        if dry_run:
            results[probe_name] = {"status": "planned", "command": command, "dry_run": True}
            continue
        result = run_command(command, cwd)
        results[probe_name] = {
            "status": "passed" if result.passed else "failed",
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
        }
    return results
