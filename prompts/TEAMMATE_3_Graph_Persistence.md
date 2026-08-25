# 🏗️ Prompt cho Người 3: Graph Construction + Persistence

## Nhiệm vụ của bạn

Implement **2 files chính**:
1. **`src/langgraph_agent_lab/graph.py`** - Build complete StateGraph
2. **`src/langgraph_agent_lab/persistence.py`** - Implement SQLite checkpointer

---

## PHẦN 1: graph.py

### Target Architecture

```
START → intake → classify → [conditional: route_after_classify]
  ├── simple       → answer → finalize → END
  ├── tool         → tool → evaluate → [conditional: route_after_evaluate]
  │                                     ├── success → answer → finalize → END
  │                                     └── needs_retry → retry → [conditional: route_after_retry]
  │                                                                     ├── attempt < max → tool
  │                                                                     └── max → dead_letter → finalize → END
  ├── missing_info → clarify → finalize → END
  ├── risky        → risky_action → approval → [conditional: route_after_approval]
  │                                     ├── approved → tool → evaluate → ... → answer → finalize → END
  │                                     └── rejected → clarify → finalize → END
  └── error        → retry → [conditional: route_after_retry] → ...
```

### Complete Implementation

```python
"""Graph construction.

This module is intentionally import-safe. It imports LangGraph only inside the builder so unit tests
that check schema/metrics can run even if students are still debugging graph wiring.
"""

from __future__ import annotations

from typing import Any

from .state import AgentState


def build_graph(checkpointer: Any | None = None):
    """Build and compile the LangGraph workflow.
    
    Graph Structure:
    START → intake → classify → [conditional: route_after_classify]
      simple → answer → finalize → END
      tool → tool → evaluate → [conditional: route_after_evaluate]
        success → answer → finalize → END
        needs_retry → retry → [conditional: route_after_retry]
          attempt < max → tool
          max → dead_letter → finalize → END
      missing_info → clarify → finalize → END
      risky → risky_action → approval → [conditional: route_after_approval]
        approved → tool → evaluate → ... → answer → finalize → END
        rejected → clarify → finalize → END
      error → retry → [conditional: route_after_retry] → ...
    """
    # Import LangGraph components INSIDE the function (lazy import)
    from langgraph.graph import StateGraph, START, END
    from .nodes import (
        intake_node,
        classify_node,
        tool_node,
        evaluate_node,
        answer_node,
        ask_clarification_node,
        risky_action_node,
        approval_node,
        retry_or_fallback_node,
        dead_letter_node,
        finalize_node,
    )
    from .routing import (
        route_after_classify,
        route_after_evaluate,
        route_after_retry,
        route_after_approval,
    )
    
    # Create the StateGraph
    graph = StateGraph(AgentState)
    
    # ============================================
    # STEP 1: Add all nodes (11 nodes total)
    # ============================================
    graph.add_node("intake", intake_node)
    graph.add_node("classify", classify_node)
    graph.add_node("tool", tool_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("answer", answer_node)
    graph.add_node("clarify", ask_clarification_node)
    graph.add_node("risky_action", risky_action_node)
    graph.add_node("approval", approval_node)
    graph.add_node("retry", retry_or_fallback_node)
    graph.add_node("dead_letter", dead_letter_node)
    graph.add_node("finalize", finalize_node)
    
    # ============================================
    # STEP 2: Add fixed edges
    # ============================================
    # START → intake → classify
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "classify")
    
    # tool → evaluate (always after tool execution)
    graph.add_edge("tool", "evaluate")
    
    # answer → finalize → END
    graph.add_edge("answer", "finalize")
    graph.add_edge("finalize", END)
    
    # clarify → finalize → END
    graph.add_edge("clarify", "finalize")
    
    # dead_letter → finalize → END
    graph.add_edge("dead_letter", "finalize")
    
    # ============================================
    # STEP 3: Add conditional edges
    # ============================================
    
    # After classify: route to appropriate node
    graph.add_conditional_edges(
        source="classify",
        path=route_after_classify,
        path_map={
            "simple": "answer",
            "tool": "tool",
            "missing_info": "clarify",
            "risky": "risky_action",
            "error": "retry",
        }
    )
    
    # After evaluate: retry or continue to answer
    graph.add_conditional_edges(
        source="evaluate",
        path=route_after_evaluate,
        path_map={
            "needs_retry": "retry",
            "success": "answer",
        }
    )
    
    # After retry: continue tool or go to dead letter
    graph.add_conditional_edges(
        source="retry",
        path=route_after_retry,
        path_map={
            "tool": "tool",
            "dead_letter": "dead_letter",
        }
    )
    
    # After approval: proceed with action or clarify
    graph.add_conditional_edges(
        source="approval",
        path=route_after_approval,
        path_map={
            "tool": "tool",
            "clarify": "clarify",
        }
    )
    
    # risky_action → approval (fixed edge)
    graph.add_edge("risky_action", "approval")
    
    # ============================================
    # STEP 4: Compile the graph
    # ============================================
    return graph.compile(checkpointer=checkpointer)
```

---

## PHẦN 2: persistence.py

### Implement SQLite Checkpointer

```python
"""Checkpointer adapter."""

from __future__ import annotations

from typing import Any


def build_checkpointer(kind: str = "memory", database_url: str | None = None) -> Any | None:
    """Return a LangGraph checkpointer.
    
    Supported kinds:
    - "none": No checkpointer (no persistence)
    - "memory": In-memory checkpointer (resets on restart)
    - "sqlite": SQLite checkpointer (persists to disk)
    - "postgres": PostgreSQL checkpointer (requires database_url)
    """
    if kind == "none":
        return None
    
    if kind == "memory":
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    
    if kind == "sqlite":
        import sqlite3
        from langgraph.checkpoint.sqlite import SqliteSaver
        
        # Default database path
        db_path = database_url or "checkpoints.db"
        
        # Create connection with WAL mode for better concurrency
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        
        return SqliteSaver(conn)
    
    if kind == "postgres":
        raise NotImplementedError(
            "TODO(student): implement Postgres checkpointer. "
            "Use langgraph.checkpoint.postgres.PostgresSaver with database_url"
        )
    
    raise ValueError(f"Unknown checkpointer kind: {kind}")
```

---

## VERIFY INSTALLATION

Trước khi implement SQLite, đảm bảo đã cài đặt dependencies:

```bash
pip install langgraph-checkpoint-sqlite
```

---

## TESTING

### Test Graph Construction

```bash
# Test that graph builds successfully
python -c "
from src.langgraph_agent_lab.graph import build_graph

graph = build_graph(checkpointer=None)
print('Graph compiled successfully!')
print('Graph nodes:', list(graph.nodes.keys()))
"
```

### Test with Scenarios

```bash
# Run all scenarios
make run-scenarios

# Check output
cat outputs/metrics.json
```

### Test Persistence (SQLite)

```bash
# Run with SQLite checkpointer
python -c "
from src.langgraph_agent_lab.graph import build_graph
from src.langgraph_agent_lab.persistence import build_checkpointer
from src.langgraph_agent_lab.scenarios import load_scenarios
from src.langgraph_agent_lab.state import initial_state

# Build with SQLite checkpointer
checkpointer = build_checkpointer('sqlite', 'test_checkpoints.db')
graph = build_graph(checkpointer=checkpointer)

# Load a scenario
scenarios = load_scenarios('data/sample/scenarios.jsonl')
scenario = scenarios[0]

# Run
state = initial_state(scenario)
config = {'configurable': {'thread_id': state['thread_id']}}
final_state = graph.invoke(state, config=config)

print('Run completed!')
print('Final route:', final_state.get('route'))
print('Final answer:', final_state.get('final_answer', 'N/A')[:100])

# Check checkpoint exists
import sqlite3
conn = sqlite3.connect('test_checkpoints.db')
cursor = conn.execute('SELECT COUNT(*) FROM checkpoints')
print('Checkpoints stored:', cursor.fetchone()[0])
conn.close()
"
```

---

## CHECKLIST trước khi bàn giao

- [ ] Graph builds without errors
- [ ] All 11 nodes registered
- [ ] All conditional edges wired correctly
- [ ] All paths terminate at `finalize → END`
- [ ] SQLite checkpointer works
- [ ] `make run-scenarios` produces valid `outputs/metrics.json`
- [ ] `make grade-local` passes

---

## Common Issues

### 1. "Node not found" error
→ Kiểm tra tên node trong `add_node()` phải match với routing return values

### 2. "Graph has no end" error
→ Đảm bảo mọi path đều kết thúc ở `finalize → END`

### 3. SQLite connection issues
→ Sử dụng `check_same_thread=False` trong `sqlite3.connect()`

### 4. Import errors
→ Đảm bảo import LangGraph bên trong function (lazy import pattern)

---

## Bonus: Time Travel Demo

Sau khi implement persistence, bạn có thể demo time travel:

```python
# Get state history
history = list(graph.get_state_history(config))
print(f"Total checkpoints: {len(history)}")

# Replay from a specific checkpoint
target_state = history[1]  # Go back one step
graph.update_state(target_state.config, {"query": "Modified query"})
```

---

**Hoàn thành xong → báo Người 4 để viết report! 📝**
