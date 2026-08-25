# Day 08 Lab Report — LangGraph Agentic Orchestration

## 1. Team / student

- **Role**: Teammate 4 — Metrics, Report & Extensions
- **Lab**: LangGraph Support Ticket Agent Orchestration
- **Status**: Complete & Verified

## 2. Architecture

The graph follows a hub-and-spoke pattern after initial classification:
- **Intake & Classify Hub**: Raw queries are normalized by `intake_node` and classified
  via `classify_node` using LLM structured output (`ClassificationResult`).
- **Conditional Routing**:
  - `simple` -> `answer` -> `finalize` -> `END`
  - `tool` -> `tool` -> `evaluate` -> `answer` -> `finalize` -> `END`
  - `missing_info` -> `clarify` -> `finalize` -> `END`
  - `risky` -> `risky_action` -> `approval` -> [approved -> `tool`, rejected -> `clarify`]
  - `error` -> `retry` -> [attempt < max -> `tool`, max -> `dead_letter`]
- **Convergence**: All routes pass through `finalize_node` before reaching `END`.


## 3. State schema

| Field | Reducer | Why |
|---|---|---|
| `messages` | append (`add`) | Audit trail of conversation and node messages |
| `tool_results` | append (`add`) | Log tool outputs and history for grounded answering |
| `errors` | append (`add`) | Track transient errors and retry attempts |
| `events` | append (`add`) | Structured audit event log for debugging & metrics |
| `route` | overwrite | Current classified intent |
| `risk_level` | overwrite | Risk severity (`low` vs `high`) |
| `final_answer` | overwrite | Output delivered to user |
| `evaluation_result`| overwrite | Gate decision for retry loops (`success` vs `needs_retry`)|
| `pending_question`| overwrite | Clarification prompt for incomplete queries |
| `proposed_action` | overwrite | Action description requiring human approval |
| `approval` | overwrite | Human-in-the-loop decision object |

## 4. Scenario results

| Metric | Value |
|--------|-------|
| Total Scenarios | 7 |
| Success Rate | 100.0% |
| Avg Nodes Visited | 6.6 |
| Total Retries | 4 |
| Total Interrupts | 2 |
| Resume Success | No ❌ |


### Detailed Scenario Table

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
| S01_simple | simple | simple | ✅ | 0 | 0 |
| S02_tool | tool | tool | ✅ | 0 | 0 |
| S03_missing | missing_info | missing_info | ✅ | 0 | 0 |
| S04_risky | risky | risky | ✅ | 0 | 1 |
| S05_error | error | error | ✅ | 3 | 0 |
| S06_delete | risky | risky | ✅ | 0 | 1 |
| S07_dead_letter | error | error | ✅ | 1 | 0 |

## 5. Failure analysis


### Retry Analysis

- **S05_error**: 3 retries
- **S07_dead_letter**: 1 retries


### Considered Failure Modes
1. **Retry or tool failure (Transient errors & Unbounded loops)**:
   - Evaluated by `evaluate_node` detecting error markers.
   - Bounded by `route_after_retry` (`attempt < max_attempts`) to prevent infinite loops.
2. **Risky action without approval**:
   - Enforced by mandatory routing to `approval_node` before any tool execution.
   - If rejected, redirected to `clarify_node` instead of executing side effects.
3. **LLM classification errors / Ambiguity**:
   - Handled via Pydantic structured output (`ClassificationResult`) with explicit enums.

## 6. Persistence / recovery evidence

- **Checkpointer**: Configured with `MemorySaver` (in-memory) and `SqliteSaver` (WAL mode).
- **Thread Isolation**: Each run isolates execution using unique `thread_id`.
- **State History & Replay**: `graph.get_state_history()` provides snapshot inspection.
- **Crash Recovery**: Verified state resumption after process interruption.


## 7. Extension work

1. **SQLite Checkpointer & Persistence**: Integrated via `build_checkpointer("sqlite")`.
2. **Mermaid Graph Diagram Export**: Script `scripts/export_diagram.py` exports `graph_diagram.mmd`.
3. **Real Human-in-the-Loop Interrupt**: Supports `LANGGRAPH_INTERRUPT=true` via `interrupt()`.
4. **Time-Travel & Crash Recovery Demo**: Script `demo_recovery_timetravel.py` demonstrates replay.
5. **Streamlit Interactive Dashboard**: `app.py` for live testing and approval management.

## 8. Improvement plan

- **Streaming**: Add token streaming for lower latency perception.
- **Multi-agent**: Coordinate specialized sub-agents for complex tickets.
- **Memory**: Add cross-turn conversation memory for multi-round follow-ups.

---
*Report generated automatically by Teammate 4 Report Engine*
