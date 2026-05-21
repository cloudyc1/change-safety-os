from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Dict, Iterable, List, Optional


def _field_matches(token: str, field_pattern: str) -> bool:
    return fnmatch.fnmatch(token, field_pattern)


def _line_has_field(line: str, field_pattern: str) -> bool:
    if "*" in field_pattern:
        parts = field_pattern.split("*")
        start = parts[0]
        end = parts[-1]
        return bool(start and start in line) or bool(end and end in line)
    return field_pattern in line


def scan_protected_fields(
    files: Iterable[str],
    project_root: Path,
    protected_fields: Iterable[str],
    changed_lines: Optional[Dict[str, Iterable[int]]] = None,
) -> List[dict]:
    fields = [str(field) for field in protected_fields if str(field).strip()]
    hits: List[dict] = []
    changed_line_sets = {
        str(path).strip().lstrip("./"): {int(line) for line in lines}
        for path, lines in (changed_lines or {}).items()
    }
    for raw_file in files:
        rel_path = str(raw_file).strip().lstrip("./")
        if not rel_path:
            continue
        path = project_root / rel_path
        if not path.exists() or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for index, line in enumerate(lines, start=1):
            if rel_path in changed_line_sets and index not in changed_line_sets[rel_path]:
                continue
            for field in fields:
                if _field_matches(field, field) and _line_has_field(line, field):
                    hits.append({"file": rel_path, "field": field, "line": index})
    return hits
