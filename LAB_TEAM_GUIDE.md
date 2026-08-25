# 🐺 LangGraph Agent Lab — Hướng dẫn Team (4 người)

## Tổng quan

Bài lab yêu cầu xây dựng một **LangGraph workflow** cho support-ticket agent với:
- ✅ State management với TypedDict + Pydantic
- ✅ 10 node functions (intake, classify, tool, evaluate, answer, clarify, risky_action, approval, retry, dead_letter, finalize)
- ✅ 4 routing functions cho conditional edges
- ✅ LLM integration (structured output + grounded generation)
- ✅ Persistence với SQLite checkpointer
- ✅ Metrics collection và report generation

---

## Kiến trúc Graph Target

```
START → intake → classify → [conditional: route_after_classify]
  ├── simple       → answer → finalize → END
  ├── tool         → tool → evaluate → [conditional: route_after_evaluate]
  │                                     ├── success → answer → finalize → END
  │                                     └── needs_retry → retry → [conditional: route_after_retry]
  │                                                                     ├── attempt < max → tool (loop)
  │                                                                     └── max → dead_letter → finalize → END
  ├── missing_info → clarify → finalize → END
  ├── risky        → risky_action → approval → [conditional: route_after_approval]
  │                                     ├── approved → tool → ... → finalize → END
  │                                     └── rejected → clarify → finalize → END
  └── error        → retry → [conditional: route_after_retry] → ...
```

---

## Scenarios để test (7 scenarios)

| ID | Query | Expected Route |
|----|-------|----------------|
| S01_simple | "How do I reset my password?" | simple |
| S02_tool | "Please lookup order status for order 12345" | tool |
| S03_missing | "Can you fix it?" | missing_info |
| S04_risky | "Refund this customer and send confirmation email" | risky |
| S05_error | "Timeout failure while processing request" | error |
| S06_delete | "Delete customer account after support verification" | risky |
| S07_dead_letter | "System failure cannot recover after multiple attempts" | error (max_attempts=1) |

---

## Phân chia công việc

### 👤 **Người 1: State + Core Nodes (LLM)**
**Files:** `state.py`, `nodes.py` (classify, answer, evaluate, tool)

**Công việc:**
1. **`state.py`** - Thêm các trường còn thiếu:
   - `evaluation_result: str` - cho retry loop gate
   - `pending_question: str | None` - cho clarification flow
   - `proposed_action: str | None` - cho risky action flow
   - `approval: ApprovalDecision | None` - cho HITL decisions

2. **`nodes.py`** - Implement 4 nodes quan trọng:
   - **`classify_node`** ⚠️ **MUST use LLM** với `.with_structured_output()`
   - **`answer_node`** ⚠️ **MUST use LLM** cho grounded response
   - **`evaluate_node`** - Check tool result quality (LLM-as-judge bonus)
   - **`tool_node`** - Mock tool với error simulation cho retry testing

**Checkpoint:** Pass `make test` cho state và classify/answer nodes

---

### 👤 **Người 2: Remaining Nodes + Routing**
**Files:** `nodes.py` (remaining), `routing.py`

**Công việc:**
1. **`nodes.py`** - Implement 6 nodes còn lại:
   - **`ask_clarification_node`** - Generate clarification question
   - **`risky_action_node`** - Prepare action for approval
   - **`approval_node`** - HITL step (mock default, có thể dùng `interrupt()` cho extension)
   - **`retry_or_fallback_node`** - Increment attempt counter
   - **`dead_letter_node`** - Handle max retry exhaustion
   - **`finalize_node`** - Emit final audit event

2. **`routing.py`** - Implement 4 routing functions:
   - `route_after_classify` - Map route → next node
   - `route_after_evaluate` - Retry loop gate (needs_retry vs success)
   - `route_after_retry` - Bounded retry check (attempt < max vs dead_letter)
   - `route_after_approval` - Approved vs rejected routing

**Checkpoint:** All routing tests pass, graph compiles

---

### 👤 **Người 3: Graph Construction + Persistence**
**Files:** `graph.py`, `persistence.py`

**Công việc:**
1. **`graph.py`** - Build complete StateGraph:
   ```python
   from langgraph.graph import StateGraph, START, END
   
   def build_graph(checkpointer=None):
       graph = StateGraph(AgentState)
       
       # Add all 11 nodes
       graph.add_node("intake", intake_node)
       graph.add_node("classify", classify_node)
       # ... all other nodes
       
       # Add fixed edges
       graph.add_edge(START, "intake")
       graph.add_edge("intake", "classify")
       # ...
       
       # Add conditional edges
       graph.add_conditional_edges("classify", route_after_classify, ...)
       # ...
       
       # Compile
       return graph.compile(checkpointer=checkpointer)
   ```

2. **`persistence.py`** - Implement SQLite checkpointer:
   ```python
   if kind == "sqlite":
       import sqlite3
       from langgraph.checkpoint.sqlite import SqliteSaver
       
       conn = sqlite3.connect("checkpoints.db")
       conn.execute("PRAGMA journal_mode=WAL")
       return SqliteSaver(conn)
   ```

**Checkpoint:** `make run-scenarios` tạo valid `outputs/metrics.json`

---

### 👤 **Người 4: Metrics + Report + Extensions**
**Files:** `report.py`, `reports/lab_report.md`, extensions

**Công việc:**
1. **`report.py`** - Implement `render_report()`:
   - Metrics summary table
   - Per-scenario results
   - Architecture explanation
   - Failure analysis
   - Improvement plan

2. **`reports/lab_report.md`** - Fill template với:
   - Graph architecture diagram
   - State schema explanation
   - Metrics results
   - Failure modes (ít nhất 2)
   - Extensions evidence

3. **Extensions** (pick 1+):
   - Real HITL: `LANGGRAPH_INTERRUPT=true` + `interrupt()`
   - Streamlit UI: Approval/reject interface
   - Time travel: `get_state_history()` replay
   - Crash recovery: Kill process, resume from checkpoint
   - Graph diagram: `graph.get_graph().draw_mermaid()`
   - Parallel fan-out: `Send()` cho concurrent tools

**Checkpoint:** `make grade-local` passes

---

## Timeline đề xuất

| Thời gian | Phase | Người |
|-----------|-------|-------|
| 0-90 min | Phase 1: State + Nodes | Người 1 |
| 90-150 min | Phase 2: Routing + Graph | Người 2 + Người 3 |
| 150-180 min | Phase 3: Persistence | Người 3 |
| 180-240 min | Phase 4: Metrics + Report | Người 4 |
| 240+ min | Extensions | Tất cả |

---

## Commands quan trọng

```bash
# Setup
pip install -e '.[dev]'
pip install langchain-openai  # hoặc langchain-anthropic
cp .env.example .env
# Edit .env → set API key

# Development
make test           # Run tests
make lint           # Linter
make typecheck      # Type checking

# Grading
make run-scenarios   # Run all scenarios → outputs/metrics.json
make grade-local     # Validate metrics

# Clean
make clean
```

---

## Scoring Breakdown

| Category | Points | Key Requirements |
|----------|--------|-----------------|
| Architecture & state | 15 | Typed state, correct reducers, student-added fields |
| Graph construction | 15 | All nodes registered, edges correct, conditional edges work |
| **LLM integration** | **15** | **classify_node + answer_node MUST use LLM** |
| Graph behavior | 20 | All routes correct, bounded retry, HITL, all paths terminate |
| Persistence | 10 | Checkpointer wired, thread_id per run, state history |
| Metrics & tests | 15 | metrics.json valid, scenario coverage, tests pass |
| Report & demo | 10 | Architecture, metrics table, failure analysis |

**⚠️ CRITICAL:** Không hard-code answers cho specific scenarios. Dùng LLM classification.

---

## Common Pitfalls

1. **Missing state fields**: Add `evaluation_result`, `pending_question`, `proposed_action`, `approval` khi implement nodes
2. **LLM structured output**: Dùng `.with_structured_output()` cho reliable classification
3. **Unbounded retry**: Always check `attempt < max_attempts` in `route_after_retry`
4. **Graph wiring**: Every path must end at `finalize → END`
5. **SqliteSaver API**: In langgraph-checkpoint-sqlite 3.x, dùng `SqliteSaver(conn=sqlite3.connect(...))`
6. **API key**: Check `.env` file và make sure it's loaded

---

## Bonus Extensions (push toward 90+)

- [ ] Parallel fan-out với `Send()`
- [ ] Real HITL với `LANGGRAPH_INTERRUPT=true`
- [ ] Streamlit approval UI
- [ ] Time travel replay
- [ ] Crash recovery demo
- [ ] Mermaid graph diagram

---

**Good luck! 🚀**
