"""Pure-Python backtest/run evaluation thresholds."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.graph.state import AgentState
from app.graph.thinking import thought


def evaluate_metrics(
    metrics: dict[str, Any],
    *,
    min_fills: int | None = None,
    max_fills: int | None = None,
    soft_min_pnl_paise: int | None = None,
) -> tuple[str, str]:
    """Return (verdict, feedback)."""
    settings = get_settings()
    min_f = settings.agent_min_fills if min_fills is None else min_fills
    max_f = settings.agent_max_fills if max_fills is None else max_fills
    soft = (
        settings.agent_soft_min_pnl_paise
        if soft_min_pnl_paise is None
        else soft_min_pnl_paise
    )

    fills = int(metrics.get("fills") or 0)
    pnl = int(metrics.get("pnl_paise") or 0)

    if fills < min_f:
        return "fail", f"too few fills ({fills} < {min_f})"
    if fills > max_f:
        return "fail", f"too many fills ({fills} > {max_f})"
    if pnl >= soft:
        return "pass", f"fills={fills} pnl_paise={pnl} (>= {soft})"
    return "weak", f"fills ok ({fills}) but pnl_paise={pnl} < soft min {soft}"


def evaluate_node(state: AgentState) -> dict[str, Any]:
    settings = get_settings()
    max_it = int(state.get("max_iterations") or settings.agent_max_iterations)
    cpp = state.get("cpp_results") or {}
    pnl = cpp.get("pnl_paise")
    if pnl is None:
        pnl = cpp.get("returned_paise") or 0
    metrics = {
        "fills": int(cpp.get("fills") or 0),
        "pnl_paise": int(pnl or 0),
        "backtest_id": cpp.get("id"),
        "run_id": cpp.get("run_id") or cpp.get("id"),
        "event_count": int(cpp.get("event_count") or len(cpp.get("events") or [])),
        "selected": cpp.get("selected"),
        "mode": cpp.get("mode"),
    }
    if state.get("error"):
        return {
            "metrics": metrics,
            "eval_verdict": "error",
            "feedback": state["error"],
            "_retry": False,
            **thought(
                "evaluate",
                f"Verdict=error due to prior error: {state['error']}",
                phase="decide",
                data=metrics,
            ),
        }

    verdict, feedback = evaluate_metrics(metrics)
    out: dict[str, Any] = {
        "metrics": metrics,
        "eval_verdict": verdict,
        "feedback": feedback,
        "_retry": False,
        "max_iterations": max_it,
    }
    it = int(state.get("iteration") or 0)
    if verdict in ("fail", "weak") and it < max_it:
        out["iteration"] = it + 1
        out["_retry"] = True
        retry_note = f" Will retry propose (iteration {it + 1}/{max_it})."
    else:
        retry_note = " Done → respond."
    out.update(
        thought(
            "evaluate",
            f"Verdict={verdict}: {feedback}.{retry_note}",
            phase="decide",
            data={"verdict": verdict, "metrics": metrics, "retry": out["_retry"]},
        )
    )
    return out
