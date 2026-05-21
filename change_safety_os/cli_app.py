from __future__ import annotations

import argparse
import shutil
import sys
from importlib import resources
from pathlib import Path
from typing import Iterable, Optional

from change_safety_os import cli


ASSET_PACKAGE = "change_safety_os.assets"


def _copy_asset_dir(asset_name: str, target: Path, *, force: bool = False) -> list[Path]:
    copied: list[Path] = []
    source = resources.files(ASSET_PACKAGE).joinpath(asset_name)
    if not source.is_dir():
        raise FileNotFoundError(f"missing packaged asset directory: {asset_name}")

    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if destination.exists() and not force:
            continue
        if item.is_dir():
            if destination.exists() and force:
                shutil.rmtree(destination)
            shutil.copytree(item, destination)
        else:
            shutil.copyfile(item, destination)
        copied.append(destination)
    return copied


def _install_codex_skill(*, force: bool = False) -> Path:
    codex_home = Path.home() / ".codex"
    skill_target = codex_home / "skills" / "change-safety"
    skill_target.mkdir(parents=True, exist_ok=True)
    source = resources.files(ASSET_PACKAGE).joinpath("skills", "change-safety", "SKILL.md")
    destination = skill_target / "SKILL.md"
    if force or not destination.exists():
        shutil.copyfile(source, destination)
    return destination


def init(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize Change Safety OS in the current project.")
    parser.add_argument(
        "--root",
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root. Defaults to current directory.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing CSO config/template files.")
    parser.add_argument(
        "--skip-codex-skill",
        "--skip-skill",
        action="store_true",
        help="Do not install the change-safety Codex skill into ~/.codex/skills.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = args.root.resolve()
    cso_root = root / "change-safety-os"
    copied = []
    copied.extend(_copy_asset_dir("config", cso_root / "config", force=args.force))
    copied.extend(_copy_asset_dir("templates", cso_root / "templates", force=args.force))

    skill_path: Path | None = None
    if not args.skip_codex_skill:
        skill_path = _install_codex_skill(force=args.force)

    print(f"project={root}")
    print(f"cso_dir={cso_root}")
    print(f"files_copied={len(copied)}")
    if skill_path:
        print(f"codex_skill={skill_path}")
    print("next=merge change-safety-os/templates/agents-snippet.md into AGENTS.md and customize config/*.yaml")
    return 0


def _print_help() -> None:
    print(
        """usage: cso <command> [options]

Commands:
  init                 Initialize ./change-safety-os config/templates and install Codex skill
  run                  Run the full CSO gate (start/scan/contracts/trace/guards/probes/finalize)
  start                Start a safety record
  scan                 Scan changed files and update impact state
  contracts            Check contracts and protected fields
  trace                Trace callers for changed symbols
  guards               Run selected guard commands
  probes               Run selected probes
  ack                  Mark contract reviews as acknowledged
  evidence             Add evidence to the latest safety record
  gap                  Record an unchecked gap
  finalize             Finalize the latest safety record
  graph build          Build workflow graph
  graph update         Refresh workflow graph and report changed/unchanged
  graph query          Query graph by --file or --domain

Examples:
  cso init
  cso run --goal "fix checkout retry bug"
  cso graph build
  cso graph update
  cso graph query --file backend/services/orders.py
"""
    )


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if not args or args[0] in {"-h", "--help"}:
        _print_help()
        return 0

    command = args[0]
    rest = args[1:]
    if command == "init":
        return init(rest)
    if command == "run":
        return cli.factory_gate(rest)
    if command == "start":
        return cli.start_change(rest)
    if command == "scan":
        return cli.scan_impact(rest)
    if command == "contracts":
        return cli.check_contracts(rest)
    if command == "trace":
        return cli.trace_callers(rest)
    if command == "guards":
        return cli.run_guards(rest)
    if command == "probes":
        return cli.run_probes(rest)
    if command == "ack":
        return cli.ack_contracts(rest)
    if command == "evidence":
        return cli.add_evidence(rest)
    if command == "gap":
        return cli.add_gap(rest)
    if command == "finalize":
        return cli.finalize(rest)
    if command == "graph":
        if not rest or rest[0] in {"-h", "--help"}:
            print("usage: cso graph <build|update|query> [options]")
            return 0
        graph_command = rest[0]
        graph_rest = rest[1:]
        if graph_command == "build":
            return cli.build_graph(graph_rest)
        if graph_command == "update":
            return cli.update_graph(graph_rest)
        if graph_command == "query":
            return cli.query_graph(graph_rest)
        print(f"unknown graph command: {graph_command}", file=sys.stderr)
        return 2

    print(f"unknown command: {command}", file=sys.stderr)
    _print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
