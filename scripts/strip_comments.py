"""Remove # comments from repo Python files (tokenize-based, string-safe)."""
from __future__ import annotations

import io
import sys
import tokenize
from pathlib import Path

REPO = Path(r"C:\Users\xief\.local\bin\ucmerced")
TARGETS = sorted((REPO / "ice_pipeline").glob("*.py")) + sorted((REPO / "scripts").glob("*.py"))
SELF = Path(__file__).resolve()


def strip_file(path: Path) -> int:
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    removals = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                removals.append((tok.start[0] - 1, tok.start[1]))
    except tokenize.TokenizeError:
        print(f"  SKIP (tokenize error): {path.name}")
        return 0
    if not removals:
        return 0
    for lineno, col in removals:
        line = lines[lineno]
        eol = "\n" if line.endswith("\n") else ""
        kept = line[:col].rstrip()
        lines[lineno] = (kept + eol) if kept else None
    out = "".join(l for l in lines if l is not None)
    path.write_text(out, encoding="utf-8")
    return len(removals)


total = 0
for p in TARGETS:
    if p.resolve() == SELF:
        continue
    n = strip_file(p)
    if n:
        print(f"  {p.relative_to(REPO)}: {n} comments removed")
        total += n
print(f"TOTAL comments removed: {total}")
