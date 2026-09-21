"""
NOTE: this __init__.py is never actually executed in the current codebase.
`packages/pathutil/bootstrap_imports()` adds this directory itself onto
sys.path (because `policy-engine`'s hyphen makes `packages.policy-engine` an
invalid dotted import), so every consumer imports `engine`/`registry` as bare
top-level modules and never goes through this package's __init__. Kept here
for documentation and in case this directory is ever renamed without the
hyphen, at which point dotted import (and this file) would become live.
"""
from .engine import PolicyEngine, PolicyRegistryEntry

__all__ = ["PolicyEngine", "PolicyRegistryEntry"]
