# 🛤️ Prompt cho Người 2: Remaining Nodes + Routing Functions

## Nhiệm vụ của bạn

Implement **2 files chính**:
1. **`src/langgraph_agent_lab/nodes.py`** - Implement 6 nodes còn lại
2. **`src/langgraph_agent_lab/routing.py`** - Implement 4 routing functions

---

## Prerequisites (Người 1 đã làm xong)

Đảm bảo Người 1 đã thêm các fields này vào `state.py`:
- `evaluation_result: str | None`
- `pending_question: str | None`
- `proposed_action: str | None`
- `approval: ApprovalDecision | None`

---

## PHẦN 1: nodes.py - 6 Remaining Nodes

### Imports cần thiết (thêm vào đầu file)

```python
from .state import AgentState, make_event, ApprovalDecision
```

### 3.1 ask_clarification_node

```python
def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating.
    
    Generate a specific clarification question based on the vague/incomplete query.
    """
```

**Implementation:**
```python
def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating."""
    from .llm import get_llm
    from .state import make_event
    
    query = state.get("query", "")
    
    # Use LLM to generate a specific clarification question
    llm = get_llm(temperature=0.7)
    
    prompt = f"""The following customer query is too vague or lacks actionable information.
Generate a specific clarification question to help the customer provide the needed details.

Customer query: {query}

Generate ONE clear, specific question that would help clarify the customer's request.
Do NOT apologize or add unnecessary filler. Be direct and helpful."""

    response = llm.invoke(prompt)
    
    # Extract content from response
    if hasattr(response, 'content'):
        clarification = response.content
    elif hasattr(response, 'text'):
        clarification = response.text
    else:
        clarification = str(response)
    
    return {
        "pending_question": clarification.strip(),
        "final_answer": f"I need some clarification: {clarification.strip()}",
        "events": [make_event("clarify", "completed", "asked for clarification")]
    }
```

---

### 3.2 risky_action_node

```python
def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval.
    
    Describe the proposed action and why it requires approval.
    """
```

**Implementation:**
```python
def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval."""
    from .llm import get_llm
    from .state import make_event
    
    query = state.get("query", "")
    
    # Use LLM to prepare the action description
    llm = get_llm(temperature=0.3)
    
    prompt = f"""Based on this customer request, describe the proposed action that requires approval.

Customer request: {query}

Describe:
1. What action will be taken
2. Why this action is considered risky (side effects, irreversible, etc.)
3. Any relevant details (order numbers, amounts, etc.)

Be specific and clear about what will happen."""

    response = llm.invoke(prompt)
    
    # Extract content from response
    if hasattr(response, 'content'):
        proposed = response.content
    elif hasattr(response, 'text'):
        proposed = response.text
    else:
        proposed = str(response)
    
    # Risk level should already be "high" from classify_node
    risk_level = state.get("risk_level", "high")
    
    return {
        "proposed_action": proposed.strip(),
        "events": [make_event("risky_action", "completed", f"action prepared for approval (risk={risk_level})")]
    }
```

---

### 3.3 approval_node

```python
def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step.
    
    Default: mock approval (approved=True) so tests and CI run offline.
    Extension: if env LANGGRAPH_INTERRUPT=true, use langgraph.types.interrupt()
    """
```

**Implementation:**
```python
def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step."""
    import os
    from .state import ApprovalDecision, make_event
    
    proposed_action = state.get("proposed_action", "unspecified action")
    
    # Check for real HITL mode
    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        # Real HITL - interrupt the graph
        from langgraph.types import interrupt
        interrupt(f"Approval required for: {proposed_action[:100]}")
    
    # Default: mock approval (for testing and offline CI)
    # In production, this would be replaced by actual human approval
    mock_approval = ApprovalDecision(
        approved=True,
        reviewer="mock-reviewer",
        comment="Auto-approved for testing (set LANGGRAPH_INTERRUPT=true for real HITL)"
    )
    
    return {
        "approval": mock_approval,
        "events": [make_event("approval", "completed", f"mock approval by {mock_approval.reviewer}")]
    }
```

---

### 3.4 retry_or_fallback_node

```python
def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt.
    
    Increment the attempt counter and log the transient failure.
    """
```

**Implementation:**
```python
def retry_or_fallback_node(state: AgentState) -> dict:
    current_attempt = state.get("attempt", 0)
    route = state.get("route", "unknown")
    
    # Increment attempt counter
    new_attempt = current_attempt + 1
    
    # Log the retry
    error_msg = f"Retry attempt {new_attempt} for route={route}"
    
    return {
        "attempt": new_attempt,
        "errors": [error_msg],
        "events": [make_event("retry", "completed", error_msg)]
    }
```

---

### 3.5 dead_letter_node

```python
def dead_letter_node(state: AgentState) -> dict:
    """Handle unresolvable failures after max retries exceeded.
    
    Log the failure and set a final_answer explaining the issue.
    """
```

**Implementation:**
```python
def dead_letter_node(state: AgentState) -> dict:
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)
    query = state.get("query", "unknown query")
    
    # Generate dead letter message
    final_answer = (
        f"Unable to process your request after {attempt} attempts. "
        f"Your request has been escalated to our support team. "
        f"We apologize for the inconvenience and will follow up within 24-48 hours."
    )
    
    return {
        "final_answer": final_answer,
        "events": [make_event("dead_letter", "completed", f"max retries exceeded ({attempt}/{max_attempts})")]
    }
```

---

### 3.6 finalize_node

```python
def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event. All routes must pass through here before END.
    """
```

**Implementation:**
```python
def finalize_node(state: AgentState) -> dict:
    route = state.get("route", "unknown")
    final_answer = state.get("final_answer")
    pending_question = state.get("pending_question")
    
    # Determine what was produced
    outcome = "completed"
    if pending_question:
        outcome = f"awaiting clarification: {pending_question[:50]}"
    elif final_answer:
        outcome = f"answered: {final_answer[:50]}"
    
    return {
        "events": [make_event("finalize", "completed", f"workflow finished for route={route}, {outcome}")]
    }
```

---

## PHẦN 2: routing.py - 4 Routing Functions

### 4.1 route_after_classify

```python
def route_after_classify(state: AgentState) -> str:
    """Map classified route to the next graph node.
    """
```

**Implementation:**
```python
def route_after_classify(state: AgentState) -> str:
    # Mapping from classify result to next node
    route_map = {
        "simple": "answer",
        "tool": "tool",
        "missing_info": "clarify",
        "risky": "risky_action",
        "error": "retry",
    }
    
    route = state.get("route", "")
    
    # Get next node, default to "answer" for unknown routes
    return route_map.get(route, "answer")
```

---

### 4.2 route_after_evaluate

```python
def route_after_evaluate(state: AgentState) -> str:
    """Decide if tool result is satisfactory or needs retry.
    """
```

**Implementation:**
```python
def route_after_evaluate(state: AgentState) -> str:
    evaluation_result = state.get("evaluation_result", "success")
    
    if evaluation_result == "needs_retry":
        return "retry"
    
    return "answer"
```

---

### 4.3 route_after_retry (⚠️ MUST BE BOUNDED)

```python
def route_after_retry(state: AgentState) -> str:
    """Decide whether to retry the tool or give up.
    
    MUST be bounded — unbounded retry loops will fail grading.
    """
```

**Implementation:**
```python
def route_after_retry(state: AgentState) -> str:
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)
    
    if attempt < max_attempts:
        return "tool"  # Try again
    
    return "dead_letter"  # Max retries exceeded
```

**⚠️ CRITICAL:** Không bao giờ return `"retry"` ở đây - điều đó sẽ tạo infinite loop!

---

### 4.4 route_after_approval

```python
def route_after_approval(state: AgentState) -> str:
    """Route based on human approval decision.
    """
```

**Implementation:**
```python
def route_after_approval(state: AgentState) -> str:
    approval = state.get("approval")
    
    # Check if approved
    if approval and hasattr(approval, "approved"):
        if approval.approved:
            return "tool"  # Proceed with risky action
        else:
            return "clarify"  # Ask user for alternative
    
    # Default: treat as rejected
    return "clarify"
```

---

## CHECKLIST trước khi bàn giao

- [ ] 6 nodes đã implement đầy đủ
- [ ] 4 routing functions đúng logic
- [ ] `route_after_retry` có kiểm tra bounded (`attempt < max_attempts`)
- [ ] Run `make test` và pass routing tests
- [ ] Import nodes đúng trong routing.py

---

## Verify với test nhanh

```bash
# Test routing functions
python -c "
from src.langgraph_agent_lab.routing import (
    route_after_classify, 
    route_after_evaluate, 
    route_after_retry,
    route_after_approval
)

# Test classify routing
print('simple:', route_after_classify({'route': 'simple'}))
print('tool:', route_after_classify({'route': 'tool'}))
print('missing_info:', route_after_classify({'route': 'missing_info'}))
print('risky:', route_after_classify({'route': 'risky'}))
print('error:', route_after_classify({'route': 'error'}))

# Test evaluate routing
print('needs_retry:', route_after_evaluate({'evaluation_result': 'needs_retry'}))
print('success:', route_after_evaluate({'evaluation_result': 'success'}))

# Test retry routing
print('retry when attempt < max:', route_after_retry({'attempt': 1, 'max_attempts': 3}))
print('dead_letter when attempt >= max:', route_after_retry({'attempt': 3, 'max_attempts': 3}))

# Test approval routing
print('approved:', route_after_approval({'approval': type('obj', (object,), {'approved': True})()}))
print('rejected:', route_after_approval({'approval': type('obj', (object,), {'approved': False})()}))
"
```

---

## Common Issues

1. **Infinite loop**: `route_after_retry` phải return `"dead_letter"` khi `attempt >= max_attempts`, KHÔNG phải `"retry"`

2. **Missing imports**: Đảm bảo import đúng:
   ```python
   from .state import AgentState, ApprovalDecision
   from .nodes import (intake_node, classify_node, tool_node, evaluate_node, 
                       answer_node, ask_clarification_node, risky_action_node,
                       approval_node, retry_or_fallback_node, dead_letter_node, finalize_node)
   ```

3. **Route strings**: Phải match chính xác với node names đăng ký trong graph

---

**Hoàn thành xong → báo Người 3 để build graph! 🏗️**
