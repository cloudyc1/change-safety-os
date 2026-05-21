from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Set


DEFAULT_SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
}

CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx"}


def _iter_text_files(project_root: Path) -> Iterable[Path]:
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        if set(path.relative_to(project_root).parts) & DEFAULT_SKIP_DIRS:
            continue
        if path.suffix not in CODE_SUFFIXES:
            continue
        yield path


def trace_symbols(
    symbols: Iterable[str],
    *,
    project_root: Path,
    exclude_files: Iterable[str] = (),
) -> Dict[str, List[str]]:
    exclude: Set[str] = {str(path).strip().lstrip("./") for path in exclude_files}
    clean_symbols = sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})
    result: Dict[str, List[str]] = {symbol: [] for symbol in clean_symbols}
    if not clean_symbols:
        return result

    for path in _iter_text_files(project_root):
        rel_path = str(path.relative_to(project_root))
        if rel_path in exclude:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for symbol in clean_symbols:
            if symbol in text:
                result[symbol].append(rel_path)

    return {symbol: sorted(files) for symbol, files in result.items() if files}


def extract_symbols_from_files(files: Iterable[str], *, project_root: Path, limit: int = 40) -> List[str]:
    patterns = [
        re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:(]"),
        re.compile(r"^\s*(?:export\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*="),
    ]
    symbols: List[str] = []
    seen: Set[str] = set()
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
        for line in lines:
            for pattern in patterns:
                match = pattern.match(line)
                if not match:
                    continue
                symbol = match.group(1)
                if symbol not in seen:
                    seen.add(symbol)
                    symbols.append(symbol)
                if len(symbols) >= limit:
                    return symbols
    return symbols
