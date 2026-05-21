from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml


IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "target",
    "coverage",
    ".next",
    ".nuxt",
    "change-safety-os",
}

AI_RULE_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".cursorrules",
    ".cursor/rules",
]


@dataclass(frozen=True)
class ProjectProfile:
    root_name: str
    ecosystems: List[str] = field(default_factory=list)
    package_managers: List[str] = field(default_factory=list)
    ai_rule_files: List[str] = field(default_factory=list)
    key_directories: List[str] = field(default_factory=list)
    guard_commands: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _existing_dirs(root: Path, candidates: Iterable[str]) -> List[str]:
    found: List[str] = []
    for candidate in candidates:
        path = root / candidate
        if path.is_dir():
            found.append(candidate.strip("/"))
    return found


def _existing_files(root: Path, candidates: Iterable[str]) -> List[str]:
    found: List[str] = []
    for candidate in candidates:
        path = root / candidate
        if path.is_file():
            found.append(candidate)
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file():
                    found.append(_relative(child, root))
    return found


def _has_any(root: Path, candidates: Iterable[str]) -> bool:
    return any((root / candidate).exists() for candidate in candidates)


def _read_package_scripts(package_json: Path) -> Dict[str, Any]:
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, dict) else {}


def _package_manager_for(root: Path) -> str | None:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "package-lock.json").exists():
        return "npm"
    if (root / "package.json").exists():
        return "npm"
    return None


def _script_command(prefix: str, manager: str, script: str) -> str:
    command = f"{manager} run {script}" if manager in {"npm", "pnpm", "yarn"} else f"npm run {script}"
    return f"cd {prefix} && {command}" if prefix else command


def _discover_javascript_guards(root: Path) -> List[str]:
    commands: List[str] = []
    package_files = sorted(root.glob("package.json")) + sorted(root.glob("*/package.json"))
    for package_file in package_files:
        package_dir = package_file.parent
        if package_dir.name in IGNORED_DIRS:
            continue
        scripts = _read_package_scripts(package_file)
        if not scripts:
            continue
        prefix = "" if package_dir == root else _relative(package_dir, root)
        manager = _package_manager_for(package_dir) or _package_manager_for(root) or "npm"
        for script in ("lint", "build", "test"):
            if script in scripts:
                commands.append(_script_command(prefix, manager, script))
    return commands


def _discover_python_guards(root: Path) -> List[str]:
    commands: List[str] = []
    candidates = [root] + [path for path in sorted(root.iterdir()) if path.is_dir() and path.name not in IGNORED_DIRS]
    for candidate in candidates:
        has_python_project = any(
            (candidate / marker).exists()
            for marker in ("pyproject.toml", "requirements.txt", "setup.py", "tox.ini", "pytest.ini")
        )
        has_tests = (candidate / "tests").is_dir() or bool(list(candidate.glob("test_*.py")))
        if not has_python_project and not has_tests:
            continue
        prefix = "" if candidate == root else _relative(candidate, root)
        command = "python -m pytest"
        commands.append(f"cd {prefix} && {command}" if prefix else command)
    return commands


def scan_project(root: Path) -> ProjectProfile:
    root = root.resolve()
    ecosystems: set[str] = set()
    package_managers: set[str] = set()
    key_directories: set[str] = set()
    guard_commands: Dict[str, List[str]] = {}

    for directory in sorted(root.iterdir()) if root.exists() else []:
        if directory.is_dir() and directory.name not in IGNORED_DIRS:
            key_directories.add(directory.name)

    if _has_any(root, ["package.json", "frontend/package.json", "web/package.json", "client/package.json"]):
        ecosystems.add("javascript")
        for package_root in [root, root / "frontend", root / "web", root / "client"]:
            manager = _package_manager_for(package_root)
            if manager:
                package_managers.add(manager)
        frontend_commands = _discover_javascript_guards(root)
        if frontend_commands:
            guard_commands["frontend_guard"] = frontend_commands

    if _has_any(root, ["pyproject.toml", "requirements.txt", "setup.py", "backend", "app"]):
        ecosystems.add("python")
        package_managers.add("pip")
        backend_commands = _discover_python_guards(root)
        if backend_commands:
            guard_commands["backend_guard"] = backend_commands

    if (root / "go.mod").exists():
        ecosystems.add("go")
        guard_commands["backend_guard"] = sorted(set(guard_commands.get("backend_guard", []) + ["go test ./..."]))
    if (root / "Cargo.toml").exists():
        ecosystems.add("rust")
        guard_commands["backend_guard"] = sorted(set(guard_commands.get("backend_guard", []) + ["cargo test"]))

    return ProjectProfile(
        root_name=root.name,
        ecosystems=sorted(ecosystems),
        package_managers=sorted(package_managers),
        ai_rule_files=sorted(_existing_files(root, AI_RULE_FILES)),
        key_directories=sorted(key_directories),
        guard_commands={key: commands for key, commands in sorted(guard_commands.items())},
    )


def _patterns_for_existing_dirs(root: Path, candidates: Iterable[str]) -> List[str]:
    return [f"{directory}/**" for directory in _existing_dirs(root, candidates)]


def _domain(
    *,
    risk: str,
    files: List[str],
    adjacent_domains: List[str],
    contracts: List[str],
    guards: List[str],
) -> dict:
    return {
        "risk": risk,
        "files": files,
        "adjacent_domains": adjacent_domains,
        "contracts": contracts,
        "guards": guards,
    }


def build_project_config(root: Path, profile: ProjectProfile) -> Dict[str, dict]:
    root = root.resolve()
    domains: Dict[str, dict] = {}

    backend_files = _patterns_for_existing_dirs(root, ["backend", "server", "api", "app"])
    if backend_files or "python" in profile.ecosystems or "go" in profile.ecosystems or "rust" in profile.ecosystems:
        domains["backend_api"] = _domain(
            risk="high",
            files=backend_files or ["**/*.py"],
            adjacent_domains=["frontend_ui", "database_persistence", "external_integrations", "auth_permissions"],
            contracts=["api_contract", "persistence_contract", "auth_permission_contract"],
            guards=["backend_guard"] if profile.guard_commands.get("backend_guard") else [],
        )

    frontend_files = _patterns_for_existing_dirs(root, ["frontend", "web", "client"])
    if frontend_files or "javascript" in profile.ecosystems:
        domains["frontend_ui"] = _domain(
            risk="medium",
            files=frontend_files or ["src/**", "app/**", "pages/**", "components/**"],
            adjacent_domains=["backend_api", "auth_permissions"],
            contracts=["frontend_navigation_contract", "api_contract"],
            guards=["frontend_guard"] if profile.guard_commands.get("frontend_guard") else [],
        )

    workflow_files = _patterns_for_existing_dirs(
        root,
        ["jobs", "workers", "tasks", "queues", "schedulers", "backend/jobs", "backend/workers", "backend/tasks"],
    )
    if workflow_files:
        domains["workflow_jobs"] = _domain(
            risk="high",
            files=workflow_files,
            adjacent_domains=["backend_api", "database_persistence", "external_integrations"],
            contracts=["workflow_lifecycle_contract", "idempotency_contract", "persistence_contract"],
            guards=["workflow_guard"],
        )

    persistence_files = _patterns_for_existing_dirs(
        root,
        ["migrations", "db", "database", "models", "schemas", "backend/migrations", "backend/models", "backend/schemas", "backend/app/models", "backend/app/schemas"],
    )
    if persistence_files:
        domains["database_persistence"] = _domain(
            risk="high",
            files=persistence_files,
            adjacent_domains=["backend_api", "workflow_jobs"],
            contracts=["persistence_contract"],
            guards=["persistence_guard"],
        )

    integration_files = _patterns_for_existing_dirs(
        root,
        ["integrations", "clients", "adapters", "backend/integrations", "backend/clients", "backend/adapters", "backend/app/integrations"],
    )
    if integration_files:
        domains["external_integrations"] = _domain(
            risk="high",
            files=integration_files,
            adjacent_domains=["backend_api", "workflow_jobs"],
            contracts=["external_integration_contract", "idempotency_contract"],
            guards=["integration_guard"],
        )

    auth_files = _patterns_for_existing_dirs(
        root,
        ["auth", "permissions", "security", "backend/auth", "backend/permissions", "backend/security", "frontend/auth"],
    )
    if auth_files:
        domains["auth_permissions"] = _domain(
            risk="critical",
            files=auth_files,
            adjacent_domains=["backend_api", "frontend_ui", "database_persistence"],
            contracts=["auth_permission_contract", "persistence_contract"],
            guards=["auth_guard"],
        )

    if profile.ai_rule_files:
        domains["agent_rules"] = _domain(
            risk="medium",
            files=profile.ai_rule_files,
            adjacent_domains=list(domains.keys()),
            contracts=[],
            guards=["cso_guard"],
        )

    return {
        "domains": domains,
        "contracts": default_contracts(),
        "guards": default_guards(profile),
        "probes": {"probes": {}},
        "risk_rules": default_risk_rules(),
    }


def default_contracts() -> Dict[str, dict]:
    return {
        "contracts": {
            "api_contract": {
                "owner": "project/backend",
                "invariants": [
                    "Request and response shapes remain compatible with documented callers.",
                    "Error status, retry behavior, pagination, filtering, and sorting semantics do not change silently.",
                ],
            },
            "frontend_navigation_contract": {
                "owner": "project/frontend",
                "invariants": [
                    "Direct entry, refresh, back/forward, continue, and success-return paths are checked separately.",
                    "Existing completed and historical records remain readable unless explicitly redefined.",
                ],
            },
            "workflow_lifecycle_contract": {
                "owner": "project/workflows",
                "invariants": [
                    "Work does not become terminal while required downstream work is still active.",
                    "Retry, cancellation, timeout, and backfill paths preserve idempotency.",
                ],
            },
            "persistence_contract": {
                "owner": "project/persistence",
                "invariants": [
                    "Schema and model changes preserve existing data or include a migration path.",
                    "Reads and writes agree on field meaning, nullability, uniqueness, and lifecycle.",
                ],
            },
            "external_integration_contract": {
                "owner": "project/integrations",
                "invariants": [
                    "External payloads, callbacks, identifiers, retries, and timeout handling remain compatible.",
                    "External side effects are idempotent or protected by dedupe keys.",
                ],
            },
            "auth_permission_contract": {
                "owner": "project/security",
                "invariants": [
                    "Authentication, authorization, tenant isolation, and role checks are not broadened silently.",
                    "Sensitive state cannot be read or mutated through a route that did not previously allow it.",
                ],
            },
            "idempotency_contract": {
                "owner": "project/platform",
                "invariants": [
                    "Shared identifiers, dedupe keys, and run keys keep a documented uniqueness scope.",
                    "Re-running a task, callback, or repair command does not duplicate user-visible work.",
                ],
            },
        }
    }


def default_guards(profile: ProjectProfile) -> Dict[str, dict]:
    guards: Dict[str, dict] = {
        "cso_guard": {
            "commands": [
                "cso --help",
            ]
        }
    }
    for guard_name, commands in profile.guard_commands.items():
        guards[guard_name] = {"commands": commands}
    for guard_name in ("workflow_guard", "persistence_guard", "integration_guard", "auth_guard"):
        guards.setdefault(guard_name, {"commands": []})
    return {"guards": guards}


def default_risk_rules() -> Dict[str, dict]:
    return {
        "risk_order": ["low", "medium", "high", "critical"],
        "protected_fields": [
            "*_id",
            "status",
            "state",
            "run_key",
            "dedupe_key",
            "tenant_id",
            "user_id",
            "role",
            "permission",
            "token",
            "secret",
            "api_key",
        ],
    }


def write_yaml(path: Path, payload: Dict[str, Any], *, force: bool = False) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return True
