"""Unit tests for node functions that do NOT require a live LLM call.

These exercise the deterministic / heuristic / fallback code paths directly
so CI can verify node behavior even without an LLM API key configured (the
graph smoke tests in test_graph_smoke.py are skipped in that situation, which
used to mean nodes.py had zero coverage in CI).
"""

from __future__ import annotations

import langgraph_agent_lab.llm as llm_module
import langgraph_agent_lab.nodes as nodes_module
from langgraph_agent_lab.state import ApprovalDecision


def _break_llm(monkeypatch):
    """Force get_llm() to raise, forcing nodes into their fallback paths."""

    def broken(*args, **kwargs):
        raise RuntimeError("no LLM configured (test)")

    monkeypatch.setattr(llm_module, "get_llm", broken)


def test_tool_node_simulates_transient_error_then_recovers():
    first = nodes_module.tool_node(
        {"route": "error", "attempt": 1, "query": "Timeout failure while processing request"}
    )
    assert first["tool_results"][0].upper().startswith("ERROR:")

    second = nodes_module.tool_node(
        {"route": "error", "attempt": 2, "query": "Timeout failure while processing request"}
    )
    assert not second["tool_results"][0].upper().startswith("ERROR:")


def test_tool_node_success_message_does_not_echo_raw_query():
    """Regression guard: the mock 'success' result must not parrot back the
    customer's own wording, since that previously fooled evaluate_node's
    keyword heuristic into requesting an unnecessary retry (see lab review)."""
    result = nodes_module.tool_node(
        {"route": "error", "attempt": 2, "query": "Timeout failure while processing request"}
    )
    text = result["tool_results"][0]
    assert "timeout" not in text.lower()
    assert "failure" not in text.lower() or text.upper().startswith("ERROR:")


def test_evaluate_node_heuristic_does_not_false_positive_on_echoed_query(monkeypatch):
    """Regression test for the S05_error false-retry bug: a genuinely
    successful tool result must not be misjudged as needing a retry just
    because the underlying text happens to contain words like
    'timeout'/'failure'."""
    _break_llm(monkeypatch)

    tool_result = nodes_module.tool_node(
        {"route": "error", "attempt": 2, "query": "Timeout failure while processing request"}
    )["tool_results"][0]

    result = nodes_module.evaluate_node({"tool_results": [tool_result]})
    assert result["evaluation_result"] == "success"


def test_evaluate_node_heuristic_flags_explicit_error(monkeypatch):
    _break_llm(monkeypatch)
    result = nodes_module.evaluate_node(
        {"tool_results": ["ERROR: Transient network/database failure on attempt 1"]}
    )
    assert result["evaluation_result"] == "needs_retry"


def test_evaluate_node_no_tool_results_needs_retry():
    result = nodes_module.evaluate_node({"tool_results": []})
    assert result["evaluation_result"] == "needs_retry"


def test_retry_or_fallback_node_increments_attempt():
    result = nodes_module.retry_or_fallback_node({"attempt": 1, "route": "error"})
    assert result["attempt"] == 2
    assert result["events"][0]["node"] == "retry"


def test_dead_letter_node_sets_final_answer():
    result = nodes_module.dead_letter_node({"attempt": 3, "max_attempts": 3, "query": "x"})
    assert result["final_answer"]
    assert "3" in result["final_answer"]


def test_finalize_node_reports_route():
    result = nodes_module.finalize_node({"route": "simple", "final_answer": "done"})
    assert "route=simple" in result["events"][0]["message"]


def test_classify_node_falls_back_without_llm(monkeypatch):
    _break_llm(monkeypatch)
    result = nodes_module.classify_node({"query": "Refund this customer and send confirmation email"})
    assert result["route"] == "risky"
    assert result["risk_level"] == "high"


def test_answer_node_falls_back_without_llm(monkeypatch):
    _break_llm(monkeypatch)
    result = nodes_module.answer_node(
        {"query": "lookup order", "tool_results": ["Order #12345: Status=Shipped"]}
    )
    assert result["final_answer"]


def test_approval_node_default_mock_approves():
    result = nodes_module.approval_node({"proposed_action": "refund order"})
    approval = result["approval"]
    assert isinstance(approval, ApprovalDecision)
    assert approval.approved is True


def test_approval_node_honors_interrupt_resume(monkeypatch):
    """Regression test: when LANGGRAPH_INTERRUPT=true, the decision returned
    by interrupt()/Command(resume=...) must be used verbatim, not silently
    overwritten by a mock 'always approve' decision."""
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")

    import langgraph.types as lg_types

    def fake_interrupt(_payload):
        return {"approved": False, "reviewer": "alice", "comment": "not today"}

    monkeypatch.setattr(lg_types, "interrupt", fake_interrupt)

    result = nodes_module.approval_node({"proposed_action": "delete account"})
    approval = result["approval"]
    assert approval.approved is False
    assert approval.reviewer == "alice"


def test_approval_node_fails_closed_on_unrecognized_resume(monkeypatch):
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")

    import langgraph.types as lg_types

    monkeypatch.setattr(lg_types, "interrupt", lambda _payload: "unexpected-string-payload")

    result = nodes_module.approval_node({"proposed_action": "delete account"})
    assert result["approval"].approved is False
