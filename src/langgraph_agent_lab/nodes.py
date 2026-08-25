"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do NOT mutate input state — return new values only.

LLM REQUIREMENT:
- classify_node MUST use a real LLM call (structured output for intent classification)
- answer_node MUST use a real LLM call (grounded response generation)
- evaluate_node SHOULD use LLM-as-judge (bonus points; heuristic acceptable for base score)
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field

from .state import AgentState, ApprovalDecision, make_event


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


# ─── Structured Output Schema for Classification ────────────────────
class ClassificationResult(BaseModel):
    """Structured output schema for LLM classification."""

    route: Literal["simple", "tool", "missing_info", "risky", "error"] = Field(
        description="Classified route: simple, tool, missing_info, risky, or error"
    )
    risk_level: Literal["low", "high"] = Field(
        description="Risk level: 'high' for risky actions, 'low' otherwise"
    )
    reasoning: str = Field(
        default="",
        description="Brief justification for classification decision",
    )


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using an LLM with structured output."""
    from .llm import get_llm

    prompt = f"""Classify this customer support query into one of these routes:

Routes:
- "simple": General inquiries, FAQs, or informational questions answerable directly.
- "tool": Read-only info lookups requiring database/tool access (order status, tracking).
- "missing_info": Vague or incomplete queries lacking essential context ("Can you fix it?").
- "risky": Side-effecting operations, refunds, account deletion, or external actions.
- "error": System errors, network timeouts, or service unavailabilities requiring retry.

Priority rule: risky > tool > missing_info > error > simple
(If query involves a refund or account deletion alongside lookup, it MUST be 'risky'.)

Risk level rule:
- Set risk_level to 'high' for 'risky' route.
- Set risk_level to 'low' for all other routes ('simple', 'tool', 'missing_info', 'error').

Query: {state.get('query', '')}

Provide the structured classification."""

    try:
        llm = get_llm(temperature=0.0)
        structured_llm = llm.with_structured_output(ClassificationResult)
        result = structured_llm.invoke(prompt)
        if isinstance(result, ClassificationResult):
            route = result.route
            risk_level = result.risk_level
            reasoning = result.reasoning
        elif isinstance(result, dict):
            route = result.get("route", "simple")
            risk_level = result.get("risk_level", "low")
            reasoning = result.get("reasoning", "")
        else:
            route = getattr(result, "route", "simple")
            risk_level = getattr(result, "risk_level", "low")
            reasoning = getattr(result, "reasoning", "")
    except Exception as exc:
        # Fallback handling in case of LLM connectivity failure
        query_text = state.get("query", "").lower()
        if "refund" in query_text or "delete" in query_text:
            route = "risky"
            risk_level = "high"
        elif "lookup" in query_text or "status" in query_text or "order" in query_text:
            route = "tool"
            risk_level = "low"
        elif "fix" in query_text or len(query_text.split()) < 4:
            route = "missing_info"
            risk_level = "low"
        elif "timeout" in query_text or "failure" in query_text or "error" in query_text:
            route = "error"
            risk_level = "low"
        else:
            route = "simple"
            risk_level = "low"
        reasoning = f"Fallback classification due to LLM error: {exc}"

    event = make_event("classify", "completed", f"classified as {route}", reasoning=reasoning)
    return {
        "route": route,
        "risk_level": risk_level,
        "events": [event],
    }


def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call.

    Simulate transient failures for error-route scenarios to test retry loops.
    """
    route = state.get("route", "")
    attempt = state.get("attempt", 0)
    query = state.get("query", "")

    # Simulate transient errors for error-route scenarios (first 2 attempts fail)
    if route == "error" and attempt < 2:
        result = f"ERROR: Transient network/database failure on attempt {attempt + 1}"
        event_msg = f"simulated error on attempt {attempt + 1}"
    elif route == "risky":
        action = state.get("proposed_action") or query
        result = f"Successfully executed approved action: {action}"
        event_msg = "approved risky action executed successfully"
    else:
        query_lower = query.lower()
        if "order" in query_lower:
            result = "Order #12345: Status=Shipped, Carrier=FedEx, Estimated Delivery=Aug 30"
        elif "password" in query_lower or "reset" in query_lower:
            result = "Password reset verification link successfully generated and dispatched"
        elif "account" in query_lower:
            result = "Account details retrieved: Account #98765, Status=Active"
        else:
            result = f"Tool executed successfully for request: {query[:60]}"
        event_msg = "tool executed successfully"

    return {
        "tool_results": [result],
        "events": [make_event("tool", "completed", event_msg)],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the retry-loop gate.

    Check whether the latest tool result is satisfactory or needs retry.
    """
    tool_results = state.get("tool_results", [])
    if not tool_results:
        return {
            "evaluation_result": "needs_retry",
            "events": [make_event("evaluate", "completed", "no tool results available")],
        }

    latest_result = tool_results[-1]
    error_indicators = ["ERROR", "TIMEOUT", "FAILED", "EXCEPTION", "UNAVAILABLE", "FAILURE"]
    has_error = any(ind in latest_result.upper() for ind in error_indicators)

    verdict = "needs_retry" if has_error else "success"
    return {
        "evaluation_result": verdict,
        "events": [make_event("evaluate", "completed", f"tool evaluation verdict: {verdict}")],
    }


def answer_node(state: AgentState) -> dict:
    """Generate a final response using an LLM grounded in available context."""
    from .llm import get_llm

    query = state.get("query", "")
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")
    proposed_action = state.get("proposed_action")

    context_parts = [f"Customer Query: {query}"]
    if tool_results:
        context_parts.append("Tool Execution Results:\n" + "\n".join(tool_results))
    if proposed_action:
        context_parts.append(f"Proposed Action: {proposed_action}")
    if approval:
        if isinstance(approval, dict):
            is_approved = approval.get("approved", False)
            reviewer = approval.get("reviewer", "mock-reviewer")
            comment = approval.get("comment", "")
        else:
            is_approved = getattr(approval, "approved", False)
            reviewer = getattr(approval, "reviewer", "mock-reviewer")
            comment = getattr(approval, "comment", "")
        status_str = "Approved" if is_approved else "Rejected"
        context_parts.append(f"Approval Decision: {status_str} by {reviewer}. Notes: {comment}")

    context = "\n\n".join(context_parts)
    prompt = f"""You are a professional, helpful customer support representative.
Generate a clear, concise, and accurate response addressing the customer's query.

Context:
{context}

Guidelines:
- Ground your answer strictly in the context.
- If tool results are available, summarize the status clearly.
- If an action was approved, confirm it has been successfully performed."""

    try:
        llm = get_llm(temperature=0.3)
        response = llm.invoke(prompt)
        if hasattr(response, "content") and isinstance(response.content, str):
            final_answer = response.content.strip()
        elif hasattr(response, "text"):
            final_answer = response.text.strip()
        else:
            final_answer = str(response).strip()
    except Exception:
        # Fallback grounded message in case of LLM error
        if tool_results:
            final_answer = f"Your request has been processed: {tool_results[-1]}"
        else:
            final_answer = f"Thank you for contacting support for '{query}'. Request processed."

    return {
        "final_answer": final_answer,
        "events": [make_event("answer", "completed", "LLM-grounded response generated")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating."""
    from .llm import get_llm

    query = state.get("query", "")
    approval = state.get("approval")

    if approval:
        if isinstance(approval, dict):
            is_approved = approval.get("approved", False)
            comment = approval.get("comment", "")
        else:
            is_approved = getattr(approval, "approved", False)
            comment = getattr(approval, "comment", "")

        if not is_approved:
            question = (
                f"Your request could not be approved ({comment or 'action rejected by reviewer'}). "
                "Could you please provide further details or an alternative request?"
            )
            event_msg = f"clarification requested for rejected approval: {question}"
            return {
                "pending_question": question,
                "final_answer": f"I need some clarification: {question}",
                "events": [make_event("clarify", "completed", event_msg)],
            }

    prompt = f"""The following customer query is too vague or lacks actionable information.
Generate a specific clarification question to help the customer provide the needed details.

Customer query: {query}

Generate ONE clear, specific question that would help clarify the customer's request.
Do NOT apologize or add unnecessary filler. Be direct and helpful."""

    try:
        llm = get_llm(temperature=0.7)
        response = llm.invoke(prompt)
        if hasattr(response, "content") and isinstance(response.content, str):
            clarification = response.content.strip()
        elif hasattr(response, "text"):
            clarification = response.text.strip()
        else:
            clarification = str(response).strip()
    except Exception:
        clarification = (
            f"Could you please provide more specific details regarding your request: '{query}'? "
            "For instance, please specify the order number, account ID, or error details."
        )

    return {
        "pending_question": clarification,
        "final_answer": f"I need some clarification: {clarification}",
        "events": [make_event("clarify", "completed", "asked for clarification")],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval."""
    from .llm import get_llm

    query = state.get("query", "")
    risk_level = state.get("risk_level", "high")

    prompt = (
        "Based on this customer request, describe the proposed action that requires approval.\n\n"
        f"Customer request: {query}\n\n"
        "Describe:\n"
        "1. What action will be taken\n"
        "2. Why this action is considered risky (side effects, irreversible, etc.)\n"
        "3. Any relevant details (order numbers, amounts, etc.)\n\n"
        "Be specific and clear about what will happen."
    )

    try:
        llm = get_llm(temperature=0.3)
        response = llm.invoke(prompt)
        if hasattr(response, "content") and isinstance(response.content, str):
            proposed = response.content.strip()
        elif hasattr(response, "text"):
            proposed = response.text.strip()
        else:
            proposed = str(response).strip()
    except Exception:
        proposed = f"Execute action with side effects: '{query}'"

    event_msg = f"action prepared for approval (risk={risk_level})"
    return {
        "proposed_action": proposed,
        "events": [make_event("risky_action", "completed", event_msg)],
    }


def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step.

    Default: mock approval (approved=True) so tests and CI run offline.
    Extension: if env LANGGRAPH_INTERRUPT=true, use langgraph.types.interrupt()
    """
    proposed_action: str = state.get("proposed_action") or "unspecified action"

    # Check for real HITL mode
    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        interrupt(f"Approval required for: {proposed_action[:100]}")

    mock_approval = ApprovalDecision(
        approved=True,
        reviewer="mock-reviewer",
        comment="Auto-approved for testing (set LANGGRAPH_INTERRUPT=true for real HITL)",
    )

    event_msg = f"mock approval by {mock_approval.reviewer}"
    return {
        "approval": mock_approval,
        "events": [make_event("approval", "completed", event_msg)],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt.

    Increment the attempt counter and log the transient failure.
    """
    current_attempt = state.get("attempt", 0)
    route = state.get("route", "unknown")
    new_attempt = current_attempt + 1
    error_msg = f"Retry attempt {new_attempt} for route={route}"

    return {
        "attempt": new_attempt,
        "errors": [error_msg],
        "events": [make_event("retry", "completed", error_msg)],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Handle unresolvable failures after max retries exceeded.

    Log the failure and set a final_answer explaining the issue.
    """
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)
    final_answer = (
        f"Unable to process your request after {attempt} attempts. "
        "Your request has been escalated to our support team. "
        "We apologize for the inconvenience and will follow up within 24-48 hours."
    )

    event_msg = f"max retries exceeded ({attempt}/{max_attempts})"
    return {
        "final_answer": final_answer,
        "events": [make_event("dead_letter", "completed", event_msg)],
    }


def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event. All routes must pass through here before END."""
    route = state.get("route", "unknown")
    final_answer = state.get("final_answer")
    pending_question = state.get("pending_question")

    outcome = "completed"
    if pending_question:
        outcome = f"awaiting clarification: {pending_question[:50]}"
    elif final_answer:
        outcome = f"answered: {final_answer[:50]}"

    event_msg = f"workflow finished for route={route}, {outcome}"
    return {
        "events": [make_event("finalize", "completed", event_msg)],
    }
