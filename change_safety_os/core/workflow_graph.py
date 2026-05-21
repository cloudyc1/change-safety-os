from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from change_safety_os.core.config_loader import SafetyConfig


@dataclass(frozen=True)
class GraphNode:
    id: str
    type: str
    label: str
    data: Dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    type: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowGraph:
    version: int
    generated_at: str
    fingerprint: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "fingerprint": self.fingerprint,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


def _node_id(node_type: str, value: str) -> str:
    return f"{node_type}:{value}"


def _add_node(nodes: Dict[str, GraphNode], node_type: str, value: str, *, label: str | None = None, data: Mapping[str, Any] | None = None) -> str:
    node_id = _node_id(node_type, value)
    if node_id not in nodes:
        nodes[node_id] = GraphNode(
            id=node_id,
            type=node_type,
            label=label or value,
            data=dict(data or {}),
        )
    return node_id


def _add_edge(edges: Dict[tuple[str, str, str], GraphEdge], source: str, target: str, edge_type: str) -> None:
    key = (source, target, edge_type)
    if key not in edges:
        edges[key] = GraphEdge(source=source, target=target, type=edge_type)


def _fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def build_workflow_graph(config: SafetyConfig) -> WorkflowGraph:
    nodes: Dict[str, GraphNode] = {}
    edges: Dict[tuple[str, str, str], GraphEdge] = {}

    for domain_name, domain in sorted((config.domains or {}).items()):
        domain_id = _add_node(
            nodes,
            "domain",
            str(domain_name),
            data={"risk": str(domain.get("risk") or "low")},
        )
        for pattern in domain.get("files") or []:
            pattern_id = _add_node(nodes, "file_pattern", str(pattern))
            _add_edge(edges, domain_id, pattern_id, "matches_file")
        for adjacent_domain in domain.get("adjacent_domains") or []:
            adjacent_id = _add_node(nodes, "domain", str(adjacent_domain))
            _add_edge(edges, domain_id, adjacent_id, "adjacent_to")
        for contract in domain.get("contracts") or []:
            contract_id = _add_node(nodes, "contract", str(contract), data=config.contracts.get(str(contract), {}))
            _add_edge(edges, domain_id, contract_id, "requires_contract")
        for guard in domain.get("guards") or []:
            guard_id = _add_node(nodes, "guard", str(guard), data=config.guards.get(str(guard), {}))
            _add_edge(edges, domain_id, guard_id, "requires_guard")

    for probe_name, probe in sorted((config.probes or {}).items()):
        probe_id = _add_node(nodes, "probe", str(probe_name), data=probe)
        for domain_name in probe.get("required_for") or []:
            domain_id = _add_node(nodes, "domain", str(domain_name))
            _add_edge(edges, domain_id, probe_id, "requires_probe")

    payload = {
        "domains": config.domains,
        "contracts": config.contracts,
        "guards": config.guards,
        "probes": config.probes,
    }
    return WorkflowGraph(
        version=1,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        fingerprint=_fingerprint(payload),
        nodes=sorted(nodes.values(), key=lambda node: node.id),
        edges=sorted(edges.values(), key=lambda edge: (edge.source, edge.type, edge.target)),
    )


def write_workflow_graph(graph: WorkflowGraph, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(graph.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_workflow_graph(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _domain_nodes(graph: Mapping[str, Any]) -> set[str]:
    return {str(node.get("id")) for node in graph.get("nodes", []) if node.get("type") == "domain"}


def summarize_domain_impact(domains: Sequence[str], graph: WorkflowGraph | Mapping[str, Any]) -> dict:
    graph_dict = graph.to_dict() if isinstance(graph, WorkflowGraph) else dict(graph)
    domain_ids = {_node_id("domain", str(domain)) for domain in domains}
    known_domains = _domain_nodes(graph_dict)
    adjacent_domains: set[str] = set()
    contracts: set[str] = set()
    guards: set[str] = set()
    probes: set[str] = set()

    for edge in graph_dict.get("edges", []):
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        edge_type = str(edge.get("type"))
        if source not in domain_ids:
            continue
        if edge_type == "adjacent_to" and target in known_domains:
            adjacent_domains.add(target.split(":", 1)[1])
        elif edge_type == "requires_contract":
            contracts.add(target.split(":", 1)[1])
        elif edge_type == "requires_guard":
            guards.add(target.split(":", 1)[1])
        elif edge_type == "requires_probe":
            probes.add(target.split(":", 1)[1])

    return {
        "domains": sorted(str(domain) for domain in domains),
        "adjacent_domains": sorted(adjacent_domains - set(domains)),
        "contracts": sorted(contracts),
        "guards": sorted(guards),
        "probes": sorted(probes),
    }


def match_domains_for_files(files: Iterable[str], graph: WorkflowGraph | Mapping[str, Any]) -> List[str]:
    graph_dict = graph.to_dict() if isinstance(graph, WorkflowGraph) else dict(graph)
    domain_patterns: Dict[str, List[str]] = {}

    for edge in graph_dict.get("edges", []):
        if edge.get("type") != "matches_file":
            continue
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if not source.startswith("domain:") or not target.startswith("file_pattern:"):
            continue
        domain_patterns.setdefault(source.split(":", 1)[1], []).append(target.split(":", 1)[1])

    matched: set[str] = set()
    for raw_file in files:
        normalized = str(raw_file).strip().lstrip("./")
        if not normalized:
            continue
        for domain, patterns in domain_patterns.items():
            if any(fnmatch.fnmatch(normalized, pattern.strip().lstrip("./")) for pattern in patterns):
                matched.add(domain)
    return sorted(matched)
