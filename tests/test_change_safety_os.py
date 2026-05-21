from pathlib import Path

import pytest

from change_safety_os.cli_app import main as cso_main
from change_safety_os.core.change_context import ChangeContext
from change_safety_os.core.config_loader import SafetyConfig
from change_safety_os.core.contract_ack import ack_contracts
from change_safety_os.core.contract_checker import check_contracts
from change_safety_os.core.evidence import add_evidence
from change_safety_os.core.finalize import FinalizeDecision, finalize_change
from change_safety_os.core.guard_runner import run_required_guards
from change_safety_os.core.impact_scanner import scan_files
from change_safety_os.core.protected_field_scanner import scan_protected_fields
from change_safety_os.core.symbol_tracer import extract_symbols_from_files, trace_symbols
from change_safety_os.core.report_writer import ReportWriter
from change_safety_os.core.workflow_graph import (
    build_workflow_graph,
    match_domains_for_files,
    summarize_domain_impact,
    write_workflow_graph,
    load_workflow_graph,
)


def _write_config(root: Path) -> Path:
    config_dir = root / "config"
    config_dir.mkdir()
    (config_dir / "domains.yaml").write_text(
        """
domains:
  scheduler:
    files:
      - jobs/scheduler.py
      - workers/**
    contracts:
      - workflow_lifecycle
    adjacent_domains:
      - payments
      - frontend
    guards:
      - scheduler_guard
    risk: high
  frontend:
    files:
      - frontend/src/**
    contracts: []
    adjacent_domains: []
    guards:
      - frontend_guard
    risk: medium
""",
        encoding="utf-8",
    )
    (config_dir / "contracts.yaml").write_text(
        """
contracts:
  workflow_lifecycle:
    fields:
      - task_id
      - status
    requires:
      - caller_map
      - state_matrix
      - adjacent_guard
""",
        encoding="utf-8",
    )
    (config_dir / "guard-matrix.yaml").write_text(
        """
guards:
  scheduler_guard:
    commands:
      - python3 -c "print('scheduler')"
  frontend_guard:
    commands:
      - npm run lint
""",
        encoding="utf-8",
    )
    (config_dir / "risk-rules.yaml").write_text("risk_order: [low, medium, high, critical]\n", encoding="utf-8")
    (config_dir / "probe-registry.yaml").write_text("probes: {}\n", encoding="utf-8")
    return config_dir


def test_start_change_creates_report_state(tmp_path: Path):
    report_root = tmp_path / "reports"
    context = ChangeContext.start(goal="fix scheduled job short runs", report_root=report_root)

    assert context.change_id
    assert context.report_dir.exists()
    assert (context.report_dir / "change-safety-record.md").exists()
    assert (context.report_dir / "state.json").exists()
    assert context.state["goal"] == "fix scheduled job short runs"


def test_scan_files_maps_domains_contracts_and_guards(tmp_path: Path):
    config = SafetyConfig.load(_write_config(tmp_path))

    result = scan_files(
        [
            "jobs/scheduler.py",
            "frontend/src/pages/Home.tsx",
        ],
        config,
    )

    assert result.risk == "high"
    assert result.domains == ["frontend", "scheduler"]
    assert result.adjacent_domains == ["payments"]
    assert result.contracts == ["workflow_lifecycle"]
    assert result.required_guards == ["frontend_guard", "scheduler_guard"]


def test_finalize_needs_work_high_risk_without_guard_results(tmp_path: Path):
    context = ChangeContext.start(goal="fix scheduling", report_root=tmp_path / "reports")
    writer = ReportWriter(context)
    writer.update_state(
        impact={
            "risk": "high",
            "domains": ["scheduler"],
            "contracts": ["workflow_lifecycle"],
            "required_guards": ["scheduler_guard"],
        }
    )

    decision = finalize_change(context)

    assert decision.status == FinalizeDecision.NEEDS_WORK
    assert "required guards have not passed" in decision.reason


def test_finalize_needs_human_decision_when_guards_pass_and_gap_recorded(tmp_path: Path):
    context = ChangeContext.start(goal="fix scheduling", report_root=tmp_path / "reports")
    writer = ReportWriter(context)
    writer.update_state(
        impact={"risk": "high", "domains": ["scheduler"], "required_guards": ["scheduler_guard"]},
        guards={"scheduler_guard": {"status": "passed", "commands": []}},
        unchecked_gaps=["manual smoke test not run"],
    )

    decision = finalize_change(context)

    assert decision.status == FinalizeDecision.NEEDS_HUMAN_DECISION


def test_finalize_ready_to_deliver_low_risk_without_required_guards(tmp_path: Path):
    context = ChangeContext.start(goal="copy change", report_root=tmp_path / "reports")
    writer = ReportWriter(context)
    writer.update_state(impact={"risk": "low", "domains": [], "required_guards": []})

    decision = finalize_change(context)

    assert decision.status == FinalizeDecision.READY_TO_DELIVER


def test_finalize_needs_work_high_risk_without_contract_review(tmp_path: Path):
    context = ChangeContext.start(goal="fix scheduling", report_root=tmp_path / "reports")
    writer = ReportWriter(context)
    writer.update_state(
        impact={"risk": "high", "domains": ["scheduler"], "contracts": ["workflow_lifecycle"], "required_guards": []}
    )

    decision = finalize_change(context)

    assert decision.status == FinalizeDecision.NEEDS_WORK
    assert "contracts have not been reviewed" in decision.reason


def test_ack_contracts_allows_reviewed_contracts(tmp_path: Path):
    context = ChangeContext.start(goal="fix scheduling", report_root=tmp_path / "reports")
    writer = ReportWriter(context)
    writer.update_state(
        impact={"risk": "high", "domains": ["scheduler"], "contracts": ["workflow_lifecycle"], "required_guards": []},
        contract_reviews={"workflow_lifecycle": {"status": "review_required"}},
    )

    ack_contracts(context, note="reviewed adjacent workflow invariants")
    decision = finalize_change(context)

    assert context.state["contract_reviews"]["workflow_lifecycle"]["status"] == "reviewed"
    assert decision.status == FinalizeDecision.READY_TO_DELIVER


def test_dry_run_guards_are_planned_not_passed(tmp_path: Path):
    config = SafetyConfig.load(_write_config(tmp_path))

    results = run_required_guards(["scheduler_guard"], config, cwd=tmp_path, dry_run=True)

    assert results["scheduler_guard"]["status"] == "planned"


def test_scan_protected_fields_reports_changed_protocol_fields(tmp_path: Path):
    source = tmp_path / "jobs/scheduler.py"
    source.parent.mkdir(parents=True)
    source.write_text("payload['task_id'] = task_id\nstatus = 'completed'\n", encoding="utf-8")

    hits = scan_protected_fields([str(source.relative_to(tmp_path))], tmp_path, ["task_id", "status"])

    assert hits == [
        {"file": "jobs/scheduler.py", "field": "task_id", "line": 1},
        {"file": "jobs/scheduler.py", "field": "status", "line": 2},
    ]


def test_scan_protected_fields_can_limit_to_changed_lines(tmp_path: Path):
    source = tmp_path / "jobs/scheduler.py"
    source.parent.mkdir(parents=True)
    source.write_text("task_id = 'old'\nstatus = 'changed'\n", encoding="utf-8")

    hits = scan_protected_fields(
        [str(source.relative_to(tmp_path))],
        tmp_path,
        ["task_id", "status"],
        changed_lines={"jobs/scheduler.py": [2]},
    )

    assert hits == [{"file": "jobs/scheduler.py", "field": "status", "line": 2}]


def test_check_contracts_requires_review_and_includes_invariants(tmp_path: Path):
    config = SafetyConfig.load(_write_config(tmp_path))
    impact = scan_files(["jobs/scheduler.py"], config)

    reviews = check_contracts(impact.to_dict(), config)

    assert reviews["workflow_lifecycle"]["status"] == "review_required"
    assert reviews["workflow_lifecycle"]["owner"] == ""
    assert reviews["workflow_lifecycle"]["requires"] == ["caller_map", "state_matrix", "adjacent_guard"]


def test_add_evidence_appends_to_state_and_report(tmp_path: Path):
    context = ChangeContext.start(goal="fix scheduling", report_root=tmp_path / "reports")

    add_evidence(context, kind="log", text="job runner claimed an unexpected task")

    assert context.state["evidence_before_change"] == [
        {"kind": "log", "text": "job runner claimed an unexpected task"}
    ]
    assert "job runner claimed an unexpected task" in context.record_path.read_text(encoding="utf-8")


def test_trace_symbols_finds_adjacent_callers(tmp_path: Path):
    service = tmp_path / "jobs/scheduler.py"
    router = tmp_path / "api/routes/tasks.py"
    service.parent.mkdir(parents=True)
    router.parent.mkdir(parents=True)
    service.write_text("def release_device():\n    return True\n", encoding="utf-8")
    router.write_text("from app.services.collection_service import release_device\nrelease_device()\n", encoding="utf-8")

    result = trace_symbols(
        ["release_device"],
        project_root=tmp_path,
        exclude_files=["jobs/scheduler.py"],
    )

    assert result["release_device"] == ["api/routes/tasks.py"]


def test_extract_symbols_from_changed_files(tmp_path: Path):
    source = tmp_path / "jobs/scheduler.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "class BatchReconciler:\n    pass\n\nasync def settle_batch():\n    return True\n",
        encoding="utf-8",
    )

    symbols = extract_symbols_from_files(["jobs/scheduler.py"], project_root=tmp_path)

    assert symbols == ["BatchReconciler", "settle_batch"]


def test_workflow_graph_builds_domain_edges_from_config(tmp_path: Path):
    config = SafetyConfig.load(_write_config(tmp_path))

    graph = build_workflow_graph(config)
    graph_dict = graph.to_dict()

    node_ids = {node["id"] for node in graph_dict["nodes"]}
    edge_keys = {(edge["source"], edge["target"], edge["type"]) for edge in graph_dict["edges"]}

    assert "domain:scheduler" in node_ids
    assert "contract:workflow_lifecycle" in node_ids
    assert "guard:scheduler_guard" in node_ids
    assert (
        "domain:scheduler",
        "contract:workflow_lifecycle",
        "requires_contract",
    ) in edge_keys
    assert (
        "domain:scheduler",
        "domain:payments",
        "adjacent_to",
    ) in edge_keys


def test_workflow_graph_summarizes_adjacent_validation_surface(tmp_path: Path):
    config = SafetyConfig.load(_write_config(tmp_path))
    graph = build_workflow_graph(config)

    summary = summarize_domain_impact(["scheduler"], graph)

    assert summary == {
        "domains": ["scheduler"],
        "adjacent_domains": ["frontend", "payments"],
        "contracts": ["workflow_lifecycle"],
        "guards": ["scheduler_guard"],
        "probes": [],
    }


def test_workflow_graph_matches_files_and_round_trips_json(tmp_path: Path):
    config = SafetyConfig.load(_write_config(tmp_path))
    graph = build_workflow_graph(config)
    graph_path = tmp_path / "workflow-graph.json"

    write_workflow_graph(graph, graph_path)
    loaded = load_workflow_graph(graph_path)

    assert loaded["fingerprint"] == graph.fingerprint
    assert match_domains_for_files(
        ["workers/email_worker.py", "frontend/src/pages/Home.tsx"],
        loaded,
    ) == ["frontend", "scheduler"]


def test_cso_init_creates_project_config_and_templates(tmp_path: Path):
    exit_code = cso_main(["init", "--root", str(tmp_path), "--skip-skill"])

    assert exit_code == 0
    assert (tmp_path / "change-safety-os" / "config" / "domains.yaml").exists()
    assert (tmp_path / "change-safety-os" / "config" / "contracts.yaml").exists()
    assert (tmp_path / "change-safety-os" / "templates" / "agents-snippet.md").exists()


def test_cso_graph_build_update_and_query(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    config_dir = _write_config(tmp_path)
    graph_path = tmp_path / "graph" / "workflow-graph.json"

    assert cso_main(["graph", "build", "--config-dir", str(config_dir), "--output", str(graph_path)]) == 0
    assert graph_path.exists()

    assert cso_main(["graph", "update", "--config-dir", str(config_dir), "--output", str(graph_path)]) == 0
    update_output = capsys.readouterr().out
    assert "status=unchanged" in update_output

    assert cso_main(["graph", "query", "--graph-file", str(graph_path), "--file", "jobs/scheduler.py"]) == 0
    query_output = capsys.readouterr().out
    assert '"scheduler"' in query_output
