from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional

from change_safety_os.adapters.git_adapter import changed_files, changed_line_map
from change_safety_os.core.change_context import ChangeContext
from change_safety_os.core.config_loader import SafetyConfig
from change_safety_os.core.contract_ack import ack_contracts as ack_contracts_core
from change_safety_os.core.contract_checker import check_contracts as check_contracts_core
from change_safety_os.core.evidence import add_evidence as add_evidence_core
from change_safety_os.core.finalize import FinalizeDecision, finalize_change
from change_safety_os.core.guard_runner import run_required_guards
from change_safety_os.core.impact_scanner import scan_files
from change_safety_os.core.protected_field_scanner import scan_protected_fields
from change_safety_os.core.probe_runner import run_required_probes, select_required_probes
from change_safety_os.core.report_writer import ReportWriter
from change_safety_os.core.symbol_tracer import extract_symbols_from_files, trace_symbols
from change_safety_os.core.workflow_graph import (
    build_workflow_graph,
    load_workflow_graph,
    match_domains_for_files,
    summarize_domain_impact,
    write_workflow_graph,
)


def _default_cso_path(name: str) -> Path:
    project_local = Path("change-safety-os") / name
    if Path("change-safety-os").exists() or project_local.exists():
        return project_local
    return Path(name)


DEFAULT_REPORT_ROOT = _default_cso_path("reports")
DEFAULT_CONFIG_DIR = _default_cso_path("config")
DEFAULT_GRAPH_PATH = _default_cso_path("graph") / "workflow-graph.json"


def _project_root() -> Path:
    return Path.cwd()


def _context(report_root: Path, report_dir: Optional[Path]) -> ChangeContext:
    if report_dir:
        return ChangeContext.load(report_dir)
    return ChangeContext.load_latest(report_root)


def start_change(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Start a change safety record.")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args(list(argv) if argv is not None else None)

    context = ChangeContext.start(goal=args.goal, report_root=args.report_root)
    print(context.report_dir)
    return 0


def scan_impact(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Scan changed files and update the latest safety record.")
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--files", nargs="*")
    args = parser.parse_args(list(argv) if argv is not None else None)

    config = SafetyConfig.load(args.config_dir)
    files = args.files if args.files else changed_files(_project_root())
    result = scan_files(files, config)
    graph = build_workflow_graph(config)
    graph_impact = summarize_domain_impact(result.domains, graph)
    context = _context(args.report_root, args.report_dir)
    impact_state = result.to_dict()
    impact_state["graph"] = graph_impact
    impact_state["graph_fingerprint"] = graph.fingerprint
    ReportWriter(context).update_state(impact=impact_state)
    print(f"risk={result.risk}")
    print(f"domains={','.join(result.domains) or 'none'}")
    print(f"guards={','.join(result.required_guards) or 'none'}")
    print(f"graph_adjacent={','.join(graph_impact['adjacent_domains']) or 'none'}")
    return 0


def add_evidence(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Add evidence to the latest safety record.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--kind", default="note")
    parser.add_argument("--text", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    context = _context(args.report_root, args.report_dir)
    add_evidence_core(context, kind=args.kind, text=args.text)
    print("evidence=added")
    return 0


def check_contracts(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Check contracts and protected fields for the latest safety record.")
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)

    config = SafetyConfig.load(args.config_dir)
    context = _context(args.report_root, args.report_dir)
    impact = context.state.get("impact") or {}
    files = impact.get("files") or changed_files(_project_root())
    contract_reviews = check_contracts_core(impact, config)
    protected_fields = config.risk_rules.get("protected_fields") or []
    protected_field_hits = scan_protected_fields(
        files,
        _project_root(),
        protected_fields,
        changed_lines=changed_line_map(_project_root()),
    )
    ReportWriter(context).update_state(
        contract_reviews=contract_reviews,
        protected_field_hits=protected_field_hits,
    )
    print(f"contracts={','.join(contract_reviews.keys()) or 'none'}")
    print(f"protected_field_hits={len(protected_field_hits)}")
    return 0


def ack_contracts(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Mark contract reviews as completed.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--contracts", nargs="*")
    parser.add_argument("--note", default="")
    args = parser.parse_args(list(argv) if argv is not None else None)

    context = _context(args.report_root, args.report_dir)
    ack_contracts_core(context, args.contracts if args.contracts else None, note=args.note)
    print("contracts=reviewed")
    return 0


def trace_callers(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Trace callers for changed symbols.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--symbols", nargs="*")
    parser.add_argument("--max-symbols", type=int, default=40)
    args = parser.parse_args(list(argv) if argv is not None else None)

    context = _context(args.report_root, args.report_dir)
    impact = context.state.get("impact") or {}
    files = impact.get("files") or changed_files(_project_root())
    symbols = args.symbols or extract_symbols_from_files(files, project_root=_project_root(), limit=args.max_symbols)
    caller_map = trace_symbols(symbols, project_root=_project_root(), exclude_files=files)
    ReportWriter(context).update_state(traced_symbols=symbols, caller_map=caller_map)
    print(f"symbols={len(symbols)}")
    print(f"caller_symbols={len(caller_map)}")
    return 0


def add_gap(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Record an unchecked gap in the latest safety record.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--text", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    context = _context(args.report_root, args.report_dir)
    gaps = list(context.state.get("unchecked_gaps") or [])
    gaps.append(args.text)
    ReportWriter(context).update_state(unchecked_gaps=gaps)
    print("gap=added")
    return 0


def run_guards(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run required guards for the latest safety record.")
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    config = SafetyConfig.load(args.config_dir)
    context = _context(args.report_root, args.report_dir)
    impact = context.state.get("impact") or {}
    results = run_required_guards(
        impact.get("required_guards") or [],
        config,
        cwd=_project_root(),
        dry_run=args.dry_run,
    )
    ReportWriter(context).update_state(guards=results)
    failed = [name for name, result in results.items() if result.get("status") == "failed"]
    planned = [name for name, result in results.items() if result.get("status") == "planned"]
    if failed:
        print(f"guards=failed:{','.join(failed)}")
    elif planned:
        print(f"guards=planned:{','.join(planned)}")
    else:
        print("guards=passed")
    return 1 if failed and not args.dry_run else 0


def run_probes(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run manual or scripted probes for impacted domains.")
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    config = SafetyConfig.load(args.config_dir)
    context = _context(args.report_root, args.report_dir)
    impact = context.state.get("impact") or {}
    probe_names = select_required_probes(impact.get("domains") or [], config)
    results = run_required_probes(probe_names, config, cwd=_project_root(), dry_run=args.dry_run)
    ReportWriter(context).update_state(probes=results)
    failed = [name for name, result in results.items() if result.get("status") == "failed"]
    planned = [name for name, result in results.items() if result.get("status") == "planned"]
    if failed:
        print(f"probes=failed:{','.join(failed)}")
    elif planned:
        print(f"probes=planned:{','.join(planned)}")
    else:
        print("probes=passed")
    return 1 if failed and not args.dry_run else 0


def finalize(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Finalize the latest safety record.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)

    context = _context(args.report_root, args.report_dir)
    decision = finalize_change(context)
    print(f"decision={decision.status}")
    print(f"reason={decision.reason}")
    return 1 if decision.status == FinalizeDecision.NEEDS_WORK else 0


def factory_gate(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the full change safety chain.")
    parser.add_argument("--goal")
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-guards", action="store_true")
    parser.add_argument("--skip-probes", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.report_dir:
        context = ChangeContext.load(args.report_dir)
    elif args.goal:
        context = ChangeContext.start(goal=args.goal, report_root=args.report_root)
    else:
        context = ChangeContext.load_latest(args.report_root)

    config = SafetyConfig.load(args.config_dir)
    files = changed_files(_project_root())
    impact = scan_files(files, config)
    graph = build_workflow_graph(config)
    impact_state = impact.to_dict()
    impact_state["graph"] = summarize_domain_impact(impact.domains, graph)
    impact_state["graph_fingerprint"] = graph.fingerprint
    ReportWriter(context).update_state(impact=impact_state)

    contract_reviews = check_contracts_core(impact.to_dict(), config)
    protected_fields = config.risk_rules.get("protected_fields") or []
    protected_field_hits = scan_protected_fields(
        impact.files,
        _project_root(),
        protected_fields,
        changed_lines=changed_line_map(_project_root()),
    )

    symbols = extract_symbols_from_files(impact.files, project_root=_project_root())
    caller_map = trace_symbols(symbols, project_root=_project_root(), exclude_files=impact.files)

    updates = {
        "contract_reviews": contract_reviews,
        "protected_field_hits": protected_field_hits,
        "traced_symbols": symbols,
        "caller_map": caller_map,
    }

    if not args.skip_guards:
        updates["guards"] = run_required_guards(impact.required_guards, config, cwd=_project_root(), dry_run=args.dry_run)
    if not args.skip_probes:
        probe_names = select_required_probes(impact.domains, config)
        updates["probes"] = run_required_probes(probe_names, config, cwd=_project_root(), dry_run=args.dry_run)
    ReportWriter(context).update_state(**updates)

    decision = finalize_change(context)
    print(context.report_dir)
    print(f"decision={decision.status}")
    print(f"reason={decision.reason}")
    return 1 if decision.status == FinalizeDecision.NEEDS_WORK else 0


def build_graph(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the CSO workflow graph from project safety config.")
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_GRAPH_PATH)
    args = parser.parse_args(list(argv) if argv is not None else None)

    config = SafetyConfig.load(args.config_dir)
    graph = build_workflow_graph(config)
    write_workflow_graph(graph, args.output)
    domain_count = sum(1 for node in graph.nodes if node.type == "domain")
    print(args.output)
    print(f"domains={domain_count}")
    print(f"nodes={len(graph.nodes)}")
    print(f"edges={len(graph.edges)}")
    print(f"fingerprint={graph.fingerprint}")
    return 0


def update_graph(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Update the CSO workflow graph and report whether it changed.")
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_GRAPH_PATH)
    args = parser.parse_args(list(argv) if argv is not None else None)

    old_fingerprint = ""
    if args.output.exists():
        old_graph = load_workflow_graph(args.output)
        old_fingerprint = str(old_graph.get("fingerprint") or "")

    config = SafetyConfig.load(args.config_dir)
    graph = build_workflow_graph(config)
    write_workflow_graph(graph, args.output)

    status = "unchanged" if old_fingerprint == graph.fingerprint else "updated"
    domain_count = sum(1 for node in graph.nodes if node.type == "domain")
    print(args.output)
    print(f"status={status}")
    print(f"domains={domain_count}")
    print(f"nodes={len(graph.nodes)}")
    print(f"edges={len(graph.edges)}")
    print(f"fingerprint={graph.fingerprint}")
    return 0


def query_graph(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Query CSO workflow graph impact by domain or file.")
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--graph-file", type=Path, default=DEFAULT_GRAPH_PATH)
    parser.add_argument("--domain", nargs="*")
    parser.add_argument("--file", nargs="*")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.graph_file.exists():
        graph = load_workflow_graph(args.graph_file)
    else:
        graph = build_workflow_graph(SafetyConfig.load(args.config_dir))

    domains = sorted({str(domain) for domain in (args.domain or []) if str(domain).strip()})
    if args.file:
        domains = sorted(set(domains) | set(match_domains_for_files(args.file, graph)))

    summary = summarize_domain_impact(domains, graph)
    print(json_dumps(summary))
    return 0


def json_dumps(payload: dict) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
