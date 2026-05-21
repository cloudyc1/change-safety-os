from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

from change_safety_os.adapters.shell_adapter import run_command
from change_safety_os.core.config_loader import SafetyConfig


def run_required_guards(
    guard_names: Iterable[str],
    config: SafetyConfig,
    *,
    cwd: Path,
    dry_run: bool = False,
) -> Dict[str, dict]:
    results: Dict[str, dict] = {}
    for guard_name in sorted(set(guard_names)):
        guard = (config.guards or {}).get(guard_name) or {}
        commands = list(guard.get("commands") or [])
        command_results = []
        status = "planned" if dry_run else "passed"
        for command in commands:
            if dry_run:
                command_results.append({"command": command, "returncode": 0, "stdout": "", "stderr": "", "dry_run": True})
                continue
            result = run_command(command, cwd)
            command_results.append(
                {
                    "command": result.command,
                    "returncode": result.returncode,
                    "stdout": result.stdout[-4000:],
                    "stderr": result.stderr[-4000:],
                }
            )
            if not result.passed:
                status = "failed"
                break
        results[guard_name] = {"status": status, "commands": command_results}
    return results
