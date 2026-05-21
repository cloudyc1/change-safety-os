from __future__ import annotations

import subprocess
import re
from pathlib import Path
from typing import Dict, List


def _git_lines(args: List[str], cwd: Path) -> List[str]:
    result = subprocess.run(["git", *args], cwd=cwd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def changed_files(cwd: Path) -> List[str]:
    files = set()
    files.update(_git_lines(["diff", "--name-only"], cwd))
    files.update(_git_lines(["diff", "--cached", "--name-only"], cwd))
    files.update(_git_lines(["ls-files", "--others", "--exclude-standard"], cwd))
    return sorted(files)


def changed_line_map(cwd: Path) -> Dict[str, List[int]]:
    result = subprocess.run(["git", "diff", "--unified=0"], cwd=cwd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return {}
    current_file = ""
    line_map: Dict[str, set[int]] = {}
    hunk_pattern = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line.removeprefix("+++ b/").strip()
            line_map.setdefault(current_file, set())
            continue
        match = hunk_pattern.match(line)
        if not match or not current_file:
            continue
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        if count == 0:
            continue
        line_map.setdefault(current_file, set()).update(range(start, start + count))
    return {path: sorted(lines) for path, lines in line_map.items()}
