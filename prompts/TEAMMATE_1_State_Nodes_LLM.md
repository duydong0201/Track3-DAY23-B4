# 🤖 Prompt cho Người 1: State + Core Nodes (LLM Integration)

## Nhiệm vụ của bạn

Implement **2 files chính**:
1. **`src/langgraph_agent_lab/state.py`** - Thêm các trường state còn thiếu
2. **`src/langgraph_agent_lab/nodes.py`** - Implement 4 nodes quan trọng với LLM

---

## PHẦN 1: state.py

### File hiện tại có gì:
```python
class AgentState(TypedDict, total=False):
    thread_id: str
    scenario_id: str
    query: str
    route: str
    risk_level: str
    attempt: int
    max_attempts: int
    final_answer: str | None
    messages: Annotated[list[str], add]
    tool_results: Annotated[list[str], add]
    errors: Annotated[list[str], add]
    events: Annotated[list[dict[str, Any]], add]
```

### Bạn CẦN thêm các trường sau:

1. **`evaluation_result: str | None`** 
   - Dùng cho: retry loop gate trong `route_after_evaluate`
   - Values: `"needs_retry"` hoặc `"success"`

2. **`pending_question: str | None`**
   - Dùng cho: clarification flow khi query vague/incomplete
   - Example: "Which order would you like to check?"

3. **`proposed_action: str | None`**
   - Dùng cho: risky action flow
   - Example: "Refund order #12345 of $99.99 to customer John"

4. **`approval: ApprovalDecision | None`**
   - Dùng cho: HITL decisions
   - Đã có `ApprovalDecision` model ở trên - chỉ cần thêm field

### Example sau khi thêm:

```python
class AgentState(TypedDict, total=False):
    # ... existing fields ...
    
    # NEW: Add these fields
    evaluation_result: str | None  # For retry loop gate
    pending_question: str | None   # For clarification flow
    proposed_action: str | None    # For risky action flow
    approval: ApprovalDecision | None  # For HITL decisions
```

**⚠️ Lưu ý:** Các trường mới KHÔNG cần `Annotated` vì chúng là overwrite values, không phải append.

---

## PHẦN 2: nodes.py

### 2.1 classify_node (⚠️ MUST USE LLM)

```python
def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using an LLM.
    
    *** MUST use a real LLM call — keyword-only heuristics will lose points. ***
    """
```

**Yêu cầu:**
- Dùng `get_llm()` từ `llm.py` để lấy LLM client
- Dùng `.with_structured_output()` để get reliable enum classification
- Tạo một Pydantic model cho classification result:

```python
from typing import Literal, TYPE_CHECKING

from pydantic import BaseModel

# Import make_event từ state
from .state import AgentState, make_event

class ClassificationResult(BaseModel):
    """Structured output schema for LLM classification."""
    route: Literal["simple", "tool", "missing_info", "risky", "error"]
    risk_level: Literal["low", "high"]
    reasoning: str

def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using an LLM with structured output."""
    from .llm import get_llm
    
    llm = get_llm(temperature=0.0)
    structured_llm = llm.with_structured_output(ClassificationResult)
    
    # Prompt cho LLM
    prompt = f"""Classify this customer support query into one of these routes:
    
    Routes:
    - "simple": General questions answerable without tools or actions
    - "tool": Information lookups (order status, tracking, search)
    - "missing_info": Vague/incomplete queries lacking actionable context
    - "risky": Actions with side effects (refunds, deletions, emails)
    - "error": System failures (timeouts, crashes, service unavailable)
    
    Priority: risky > tool > missing_info > error > simple
    
    Query: {state['query']}
    
    Respond with the classification."""
    
    result = structured_llm.invoke(prompt)
    
    return {
        "route": result.route,
        "risk_level": result.risk_level,
        "events": [make_event("classify", "completed", f"classified as {result.route}")]
    }
```

---

### 2.2 answer_node (⚠️ MUST USE LLM)

```python
def answer_node(state: AgentState) -> dict:
    """Generate a final response using an LLM.
    
    *** MUST use a real LLM call — hardcoded strings will lose points. ***
    """
```

**Yêu cầu:**
- Dùng `get_llm()` để lấy LLM
- Generate response grounded in: `tool_results`, `approval`, `query`
- KHÔNG hard-code responses

```python
from .state import AgentState, make_event

def answer_node(state: AgentState) -> dict:
    """Generate a final response using an LLM."""
    from .llm import get_llm
    
    llm = get_llm(temperature=0.7)  # Higher temp for creative answers
    
    # Build context for grounding
    context_parts = []
    
    if state.get("query"):
        context_parts.append(f"Customer query: {state['query']}")
    
    if state.get("tool_results"):
        context_parts.append(f"Tool results: {' '.join(state['tool_results'])}")
    
    if state.get("approval"):
        approval = state["approval"]
        if hasattr(approval, "approved") and approval.approved:
            context_parts.append(f"Action approved by {approval.reviewer}")
    
    context = "\n".join(context_parts)
    
    prompt = f"""You are a helpful customer support agent. Based on the following context,
generate a helpful and accurate response to the customer's query.

Context:
{context}

Provide a clear, concise response that addresses the customer's needs."""

    response = llm.invoke(prompt)
    
    # Extract content from LLM response (handle different response formats)
    if hasattr(response, 'content'):
        final_answer = response.content
    elif hasattr(response, 'text'):
        final_answer = response.text
    else:
        final_answer = str(response)
    
    return {
        "final_answer": final_answer,
        "events": [make_event("answer", "completed", "LLM-generated response")]
    }
```

---

### 2.3 evaluate_node (LLM-as-judge for bonus)

```python
def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the retry-loop gate.
    
    SHOULD use LLM-as-judge for bonus points. Heuristic acceptable for base score.
    """
```

**Base implementation (heuristic):**
```python
def evaluate_node(state: AgentState) -> dict:
    tool_results = state.get("tool_results", [])
    if not tool_results:
        return {
            "evaluation_result": "needs_retry",
            "events": [make_event("evaluate", "completed", "no tool results")]
        }
    
    latest_result = tool_results[-1]
    
    # Check for error indicators
    error_indicators = ["ERROR", "timeout", "failed", "exception", "unavailable"]
    has_error = any(indicator.lower() in latest_result.lower() for indicator in error_indicators)
    
    if has_error:
        return {
            "evaluation_result": "needs_retry",
            "events": [make_event("evaluate", "completed", "tool result has errors")]
        }
    
    return {
        "evaluation_result": "success",
        "events": [make_event("evaluate", "completed", "tool result satisfactory")]
    }
```

**Bonus: LLM-as-judge version:**
```python
def evaluate_node(state: AgentState) -> dict:
    """LLM-as-judge version for bonus points."""
    from .llm import get_llm
    from .state import make_event
    
    tool_results = state.get("tool_results", [])
    if not tool_results:
        return {
            "evaluation_result": "needs_retry",
            "events": [make_event("evaluate", "completed", "no tool results available")]
        }
    
    latest_result = tool_results[-1]
    
    llm = get_llm(temperature=0.0)
    
    prompt = f"""Evaluate this tool result for a customer support query.

Tool result: {latest_result}

Is this result satisfactory (success) or does it need to be retried (needs_retry)?
- Return "success" if the result is useful and answers the query
- Return "needs_retry" if there are errors, timeouts, or incomplete data

Respond with only: success or needs_retry"""
    
    result = llm.invoke(prompt).content.strip().lower()
    
    if "retry" in result:
        return {
            "evaluation_result": "needs_retry",
            "events": [make_event("evaluate", "completed", "LLM judged: needs retry")]
        }
    return {
        "evaluation_result": "success",
        "events": [make_event("evaluate", "completed", "LLM judged: success")]
    }
```

---

### 2.4 tool_node (Mock tool with error simulation)

```python
def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call.
    
    Simulate transient failures for error-route scenarios to test retry loops.
    """
```

**Implementation:**
```python
from .state import AgentState, make_event

def tool_node(state: AgentState) -> dict:
    """Execute mock tool with error simulation for retry testing."""
    import random
    
    route = state.get("route", "")
    attempt = state.get("attempt", 0)
    
    # Simulate errors for error-route scenarios (first 2 attempts fail)
    if route == "error" and attempt < 2:
        result = f"ERROR: Transient failure on attempt {attempt + 1}"
        event_msg = f"simulated error on attempt {attempt + 1}"
    else:
        # Mock successful tool execution
        query = state.get("query", "")
        
        # Simple mock based on query content
        if "order" in query.lower():
            result = "Order #12345: Status=Shipped, Expected delivery=Aug 30"
        elif "reset" in query.lower() or "password" in query.lower():
            result = "Password reset link sent to registered email"
        else:
            result = f"Tool executed successfully for query: {query[:50]}"
        
        event_msg = "tool executed successfully"
    
    return {
        "tool_results": [result],
        "events": [make_event("tool", "completed", event_msg)]
    }
```

---

## Checklist trước khi bàn giao

- [ ] `state.py` có đủ 4 trường mới
- [ ] `classify_node` dùng `.with_structured_output()`
- [ ] `answer_node` dùng LLM để generate response
- [ ] `evaluate_node` check tool result quality
- [ ] `tool_node` simulate errors cho retry testing
- [ ] Run `make test` và pass các test liên quan
- [ ] Test thủ công với một scenario đơn giản

---

## Test thủ công

```bash
# Test nhanh classification
python -c "
from src.langgraph_agent_lab.state import initial_state, Scenario
from src.langgraph_agent_lab.nodes import classify_node

scenario = Scenario(id='test', query='How do I reset my password?', expected_route='simple')
state = initial_state(scenario)
result = classify_node(state)
print('Route:', result.get('route'))
print('Risk:', result.get('risk_level'))
"
```

---

**Hoàn thành xong → báo Người 2 để tiếp tục với routing! 🚀**
