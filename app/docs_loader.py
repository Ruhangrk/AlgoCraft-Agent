"""Load curated C++ docs for LLM nodes (index + selective bodies)."""

from __future__ import annotations

from pathlib import Path

from app.config import REPO_ROOT

DOCS_ROOT = REPO_ROOT / "docs"


def resolve_doc(path: str) -> Path:
    """Resolve a docs-relative path like `docs/cpp/INDEX.md` or `cpp/INDEX.md`."""
    raw = path.strip().lstrip("/")
    if raw.startswith("docs/"):
        candidate = REPO_ROOT / raw
    else:
        candidate = DOCS_ROOT / raw
    return candidate.resolve()


def load_doc(path: str) -> str:
    p = resolve_doc(path)
    if not str(p).startswith(str(DOCS_ROOT.resolve())):
        raise ValueError(f"doc path escapes docs root: {path}")
    if not p.is_file():
        raise FileNotFoundError(f"doc not found: {path}")
    return p.read_text(encoding="utf-8")


def load_docs(paths: list[str], *, missing_ok: bool = False) -> str:
    """Concatenate docs with path headers. Cap callers to ≤2–3 bodies after INDEX."""
    chunks: list[str] = []
    for path in paths:
        try:
            body = load_doc(path)
        except (FileNotFoundError, ValueError):
            if missing_ok:
                continue
            raise
        chunks.append(f"### {path}\n{body.strip()}")
    return "\n\n".join(chunks)


def codegen_context() -> str:
    """Default Phase B context: INDEX + shape + interface + pitfalls."""
    return load_docs(
        [
            "docs/cpp/INDEX.md",
            "docs/cpp/codegen_shape.md",
            "docs/cpp/strategy_interface.md",
            "docs/cpp/pitfalls.md",
        ]
    )
