"""
Repo-wide import bootstrap.

Why this exists: §7.1's required folder names use hyphens
(`graph-schema`, `policy-engine`, `memory-mcp-server`, `ingestion-api`, ...),
which are not valid Python package name segments (`import packages.graph-schema`
is a SyntaxError). Every service calls `bootstrap_imports()` once at startup to
add the repo root and each hyphenated package directory directly onto
`sys.path`, so modules inside them are imported by bare filename
(`import graph`, `import engine`) instead of by dotted path. This keeps the
folder structure exactly as specified while keeping the code importable.
"""
import sys
from pathlib import Path

_BOOTSTRAPPED = False


def bootstrap_imports():
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))  # enables `from packages.contracts import ...`
    # `evaluation` and `observability` have no hyphen and are dotted-importable
    # (`packages.evaluation`, `packages.observability`); only the two hyphenated
    # directories below actually need direct sys.path insertion for bare import.
    for hyphenated in ["graph-schema", "policy-engine"]:
        p = repo_root / "packages" / hyphenated
        if p.exists():
            sys.path.insert(0, str(p))
    _BOOTSTRAPPED = True
