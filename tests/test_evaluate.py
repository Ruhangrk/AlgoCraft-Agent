"""Evaluate threshold unit tests."""

from __future__ import annotations

from app.graph.nodes.evaluate import evaluate_metrics, evaluate_node


def test_evaluate_pass() -> None:
    v, _ = evaluate_metrics({"fills": 5, "pnl_paise": 10}, min_fills=2, soft_min_pnl_paise=1)
    assert v == "pass"


def test_evaluate_weak() -> None:
    v, fb = evaluate_metrics({"fills": 5, "pnl_paise": 0}, min_fills=2, soft_min_pnl_paise=1)
    assert v == "weak"
    assert "pnl" in fb


def test_evaluate_fail_fills() -> None:
    v, _ = evaluate_metrics({"fills": 0, "pnl_paise": 100}, min_fills=2)
    assert v == "fail"


def test_evaluate_node_sets_retry() -> None:
    out = evaluate_node(
        {
            "cpp_results": {"fills": 0, "pnl_paise": 0},
            "iteration": 0,
            "max_iterations": 3,
        }
    )
    assert out["eval_verdict"] == "fail"
    assert out["_retry"] is True
    assert out["iteration"] == 1
