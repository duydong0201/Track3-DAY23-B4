# 📊 Prompt cho Người 4: Metrics + Report + Extensions

## Nhiệm vụ của bạn

1. **`src/langgraph_agent_lab/report.py`** - Implement report rendering
2. **`reports/lab_report.md`** - Fill template với analysis
3. **Extensions** - Implement bonus features (pick 1+)

---

## PHẦN 1: report.py

### Current Template Structure

```markdown
# Lab Report - LangGraph Agentic Orchestration

## 1. Architecture Overview
[Describe your graph design, state schema, and key design decisions]

## 2. Metrics Summary
| Metric | Value |
|--------|-------|
| Total Scenarios | X |
| Success Rate | X% |
| Avg Nodes Visited | X |
| Total Retries | X |
| Total Interrupts | X |

## 3. Scenario Results
| Scenario | Expected | Actual | Success | Nodes | Retries |
|----------|----------|--------|---------|-------|---------|
| S01_simple | simple | ? | ? | ? | ? |
| ... | ... | ... | ... | ... | ... |

## 4. Failure Analysis
[At least 2 failure modes you considered]

## 5. Improvement Ideas
[How would you improve the system?]
```

### Implementation

```python
"""Report generation helper."""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data."""
    
    # Calculate summary stats
    total = metrics.total_scenarios
    success_count = sum(1 for s in metrics.scenario_metrics if s.success)
    success_rate = metrics.success_rate * 100
    
    # Build scenario table rows
    scenario_rows = []
    for sm in metrics.scenario_metrics:
        status = "✅" if sm.success else "❌"
        scenario_rows.append(
            f"| {sm.scenario_id} | {sm.expected_route} | {sm.actual_route or 'N/A'} | "
            f"{status} | {sm.nodes_visited} | {sm.retry_count} |"
        )
    scenario_table = "\n".join(scenario_rows)
    
    # Build metrics summary
    metrics_summary = f"""| Metric | Value |
|--------|-------|
| Total Scenarios | {metrics.total_scenarios} |
| Success Rate | {metrics.success_rate:.1%} |
| Avg Nodes Visited | {metrics.avg_nodes_visited:.1f} |
| Total Retries | {metrics.total_retries} |
| Total Interrupts | {metrics.total_interrupts} |
| Resume Success | {"Yes ✅" if metrics.resume_success else "No ❌"} |
"""
    
    # Failure analysis - auto-generate from data
    failures = [s for s in metrics.scenario_metrics if not s.success]
    retry_scenarios = [s for s in metrics.scenario_metrics if s.retry_count > 0]
    
    failure_analysis = ""
    if failures:
        failure_analysis += f"\n### Failed Scenarios\n\n"
        for s in failures:
            failure_analysis += f"- **{s.scenario_id}**: Expected `{s.expected_route}`, got `{s.actual_route or 'N/A'}`\n"
            if s.errors:
                failure_analysis += f"  - Errors: {', '.join(s.errors[:2])}\n"
    
    if retry_scenarios:
        failure_analysis += f"\n### Retry Analysis\n\n"
        for s in retry_scenarios:
            failure_analysis += f"- **{s.scenario_id}**: {s.retry_count} retries\n"
    
    # Improvement ideas based on data
    improvements = []
    
    if metrics.total_retries > 5:
        improvements.append(
            "**Retry optimization**: Consider adding exponential backoff or circuit breaker patterns "
            "to reduce retry attempts on persistent failures."
        )
    
    if metrics.total_interrupts == 0:
        improvements.append(
            "**HITL integration**: Enable real human-in-the-loop approval with "
            "`LANGGRAPH_INTERRUPT=true` for production safety."
        )
    
    if metrics.avg_nodes_visited < 4:
        improvements.append(
            "**Extended paths**: Some scenarios could benefit from additional processing steps, "
            "like caching, A/B testing, or multi-tool coordination."
        )
    
    # Always suggest these
    improvements.extend([
        "**Streaming**: Add response streaming for better UX on long responses.",
        "**Multi-agent**: Coordinate multiple specialized agents for complex queries.",
        "**Memory**: Add conversation memory across multiple turns for follow-up queries.",
    ])
    
    improvement_section = "\n".join(f"- {imp}" for imp in improvements)
    
    # Assemble full report
    report = f"""# Lab Report - LangGraph Agentic Orchestration

## 1. Architecture Overview

### State Schema Design
Our agent state is implemented as a TypedDict with both append-only (audit trail) and overwrite (current values) fields:

- **Append-only fields**: `messages`, `tool_results`, `errors`, `events` — using `Annotated[..., add]` for reducers
- **Overwrite fields**: `route`, `risk_level`, `final_answer`, etc. — replaced on each node visit

### Graph Design
The graph follows a hub-and-spoke pattern after classification:
1. **Classification hub** — All queries enter through `classify_node` using LLM structured output
2. **Route spokes** — Each route has its own specialized path (simple, tool, risky, etc.)
3. **Convergence point** — All paths converge at `finalize_node` before END

### Key Design Decisions
1. **LLM classification** — Using structured output for reliable routing, not keyword heuristics
2. **Bounded retry** — Always checking `attempt < max_attempts` to prevent infinite loops
3. **Mock HITL** — Default to mock approval for CI; enable real HITL with env var

## 2. Metrics Summary

{metrics_summary}

## 3. Scenario Results

| Scenario | Expected | Actual | Status | Nodes | Retries |
|----------|----------|--------|--------|-------|---------|
{scenario_table}

## 4. Failure Analysis

{failure_analysis or "All scenarios completed successfully! No failures detected."}

### Considered Failure Modes
1. **Unbounded retry loops** — Addressed by checking `attempt < max_attempts` in `route_after_retry`
2. **LLM classification errors** — Mitigated by using structured output with explicit enum values
3. **Missing state fields** — Addressed by adding `evaluation_result`, `pending_question`, etc. during implementation

## 5. Improvement Ideas

{improvement_section}

---

*Report generated automatically from metrics data*
"""
    
    return report


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
```

---

## PHẦN 2: lab_report.md Template

### Fill in these sections:

```markdown
# Lab Report: LangGraph Support Ticket Agent

## 1. Architecture Overview

### Graph Structure
[DESCRIBE YOUR GRAPH HERE]

```
START → intake → classify → [conditional routing]
  ├── simple → answer → finalize → END
  ├── tool → tool → evaluate → [retry loop?] → answer → finalize → END
  ├── missing_info → clarify → finalize → END
  ├── risky → risky_action → approval → [approved?] → tool/clarify → ...
  └── error → retry → [bounded loop?] → dead_letter → END
```

### State Schema
[DESCRIBE YOUR STATE FIELDS]
- Append-only: messages, tool_results, errors, events
- Overwrite: route, risk_level, final_answer, evaluation_result, etc.

### Key Implementation Details
[DESCRIBE LLM USAGE, ROUTING LOGIC, ETC.]

## 2. Metrics Summary

[COPY FROM make run-scenarios OUTPUT]

## 3. Scenario Results

[DESCRIBE WHAT HAPPENED WITH EACH SCENARIO]

## 4. Failure Analysis

[ANALYZE ANY FAILURES OR EDGE CASES]

## 5. Extension Evidence

[INCLUDE SCREENSHOTS/LOGS OF BONUS FEATURES]

## 6. Future Improvements

[HOW WOULD YOU ENHANCE THIS SYSTEM?]
```

---

## PHẦN 3: Extensions (Pick 1+)

### Extension A: Real HITL with interrupt()

```python
# In approval_node
import os
if os.getenv("LANGGRAPH_INTERRUPT") == "true":
    from langgraph.types import interrupt
    interrupt(f"Approve this action? {proposed_action}")
```

### Extension B: Time Travel Replay

```python
# After running scenarios, demonstrate replay
history = list(graph.get_state_history(config))
print(f"Found {len(history)} checkpoints")

# Replay from checkpoint 2
target_config = history[2].config
graph.invoke(None, config=target_config)  # Replay
```

### Extension C: Graph Diagram Export

```python
# Export Mermaid diagram
mermaid_code = graph.get_graph().draw_mermaid()
with open("outputs/graph_diagram.mmd", "w") as f:
    f.write(mermaid_code)
print("Saved to outputs/graph_diagram.mmd")
```

### Extension D: Streamlit UI

```python
# Create app.py for approval interface
import streamlit as st
from src.langgraph_agent_lab.graph import build_graph
from src.langgraph_agent_lab.persistence import build_checkpointer

st.title("Support Ticket Agent - Approval Dashboard")

checkpointer = build_checkpointer("sqlite", "checkpoints.db")
graph = build_graph(checkpointer=checkpointer)

# List pending approvals
# ... implement UI ...
```

### Extension E: Crash Recovery Demo

```bash
# 1. Start a long-running scenario
python -c "
from src.langgraph_agent_lab.graph import build_graph
from src.langgraph_agent_lab.persistence import build_checkpointer
from src.langgraph_agent_lab.state import initial_state, Scenario

checkpointer = build_checkpointer('sqlite', 'recovery_demo.db')
graph = build_graph(checkpointer=checkpointer)

# Simulate partial execution
state = initial_state(Scenario(id='test', query='test', expected_route='simple'))
config = {'configurable': {'thread_id': 'test-thread'}}

# Kill this process before completion...
graph.invoke(state, config=config)
"

# 2. Kill the process mid-execution (Ctrl+C or kill signal)

# 3. Resume from checkpoint
python -c "
from src.langgraph_agent_lab.graph import build_graph
from src.langgraph_agent_lab.persistence import build_checkpointer

checkpointer = build_checkpointer('sqlite', 'recovery_demo.db')
graph = build_graph(checkpointer=checkpointer)

# Resume from checkpoint
config = {'configurable': {'thread_id': 'test-thread'}}
state = graph.get_state(config)
print('Resumed from checkpoint:', state)
"
```

---

## FINAL TESTING

```bash
# Run everything
make test           # Unit tests
make lint           # Linting
make typecheck      # Type checking
make run-scenarios  # Run all scenarios
make grade-local    # Validate metrics

# Check outputs
cat outputs/metrics.json
cat outputs/lab_report.md
```

---

## CHECKLIST trước khi submit

- [ ] `report.py` generates valid markdown report
- [ ] `reports/lab_report.md` filled with real data
- [ ] All 7 scenarios covered in metrics
- [ ] `make grade-local` passes
- [ ] At least one extension implemented
- [ ] Can explain one route and one failure mode during demo

---

## Bonus Points Guide

| Extension | Points |
|-----------|--------|
| LLM-as-judge in evaluate_node | +5 |
| Real HITL with interrupt() | +5 |
| Time travel replay | +5 |
| Crash recovery demo | +5 |
| Mermaid graph diagram | +5 |
| Streamlit UI | +5 |
| Parallel fan-out with Send() | +5 |

**Pick 1+ to push toward 90+! 🎯**

---

**Hoàn thành → Tổng hợp và submit! 🚀**
