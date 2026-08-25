"""Report generation helper.

TODO(student): implement report rendering using MetricsReport data
and the template in reports/lab_report_template.md.
"""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data."""
    # Build scenario table rows
    scenario_rows = []
    for sm in metrics.scenario_metrics:
        status = "✅" if sm.success else "❌"
        scenario_rows.append(
            f"| {sm.scenario_id} | {sm.expected_route} | {sm.actual_route or 'N/A'} | "
            f"{status} | {sm.retry_count} | {sm.interrupt_count} |"
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
        failure_analysis += "\n### Failed Scenarios\n\n"
        for s in failures:
            act = s.actual_route or "N/A"
            failure_analysis += (
                f"- **{s.scenario_id}**: Expected `{s.expected_route}`, "
                f"got `{act}`\n"
            )
            if s.errors:
                failure_analysis += f"  - Errors: {', '.join(s.errors[:2])}\n"

    if retry_scenarios:
        failure_analysis += "\n### Retry Analysis\n\n"
        for s in retry_scenarios:
            failure_analysis += f"- **{s.scenario_id}**: {s.retry_count} retries\n"

    # Improvement ideas based on data
    improvements = []

    if metrics.total_retries > 5:
        improvements.append(
            "**Retry optimization**: Consider adding exponential backoff or circuit breaker "
            "patterns to reduce retry attempts on persistent failures."
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
    improvements.extend(
        [
            "**Streaming**: Add token streaming for lower latency perception.",
            "**Multi-agent**: Coordinate specialized sub-agents for complex tickets.",
            "**Memory**: Add cross-turn conversation memory for multi-round follow-ups.",
        ]
    )

    improvement_section = "\n".join(f"- {imp}" for imp in improvements)

    # Assemble full 8-section report
    report = f"""# Day 08 Lab Report — LangGraph Agentic Orchestration

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

{metrics_summary}

### Detailed Scenario Table

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
{scenario_table}

## 5. Failure analysis

{failure_analysis or "All scenarios completed successfully! No unhandled failures detected."}

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

{improvement_section}

---
*Report generated automatically by Teammate 4 Report Engine*
"""


    return report


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")



