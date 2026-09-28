"""Unit tests for C++ docs loader."""

from __future__ import annotations

import pytest

from app.docs_loader import codegen_context, load_doc, load_docs


def test_load_index() -> None:
    text = load_doc("docs/cpp/INDEX.md")
    assert "codegen_shape.md" in text


def test_codegen_context_includes_shape() -> None:
    ctx = codegen_context()
    assert "Generated strategy shape" in ctx
    assert "Strategy interface" in ctx
    assert "pitfalls" in ctx.lower() or "Float money" in ctx


def test_path_escape_rejected() -> None:
    with pytest.raises(ValueError):
        load_doc("docs/cpp/../../.env")


def test_load_docs_missing_ok() -> None:
    out = load_docs(["docs/cpp/INDEX.md", "docs/cpp/nope.md"], missing_ok=True)
    assert "INDEX.md" in out
