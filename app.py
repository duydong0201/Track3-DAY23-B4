"""Streamlit Dashboard for Support Ticket Agent Orchestration."""

from __future__ import annotations

import os
from pathlib import Path
import streamlit as st

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.scenarios import load_scenarios
from langgraph_agent_lab.state import Route, Scenario, initial_state

st.set_page_config(page_title="LangGraph Agent Dashboard", page_icon="🤖", layout="wide")

st.title("🤖 Support Ticket Agent — LangGraph Orchestration")
st.markdown(
    "Interactive dashboard for agent execution, routing visualization, human-in-the-loop approvals, and persistence."
)

# Sidebar settings
st.sidebar.header("Configuration")
backend = st.sidebar.selectbox("Persistence Backend", ["memory", "sqlite"], index=1)
sqlite_db = st.sidebar.text_input("SQLite DB Path", "checkpoints.db") if backend == "sqlite" else None
interrupt_mode = st.sidebar.checkbox("Enable Real HITL Interrupt", value=False)
if interrupt_mode:
    os.environ["LANGGRAPH_INTERRUPT"] = "true"
else:
    os.environ.pop("LANGGRAPH_INTERRUPT", None)

# Initialize graph
checkpointer = build_checkpointer(backend, sqlite_db)
graph = build_graph(checkpointer=checkpointer)

tabs = st.tabs(["🚀 Run Query", "📋 Batch Scenarios", "🔍 Checkpoint History", "📊 Architecture"])

with tabs[0]:
    st.subheader("Execute a Support Query")
    col1, col2 = st.columns([3, 1])
    with col1:
        user_query = st.text_area(
            "Customer Query",
            placeholder="e.g. Please lookup order status for order 12345, or Refund this customer",
            value="Refund this customer and send confirmation email",
            height=100,
        )
    with col2:
        custom_route = st.selectbox(
            "Expected Route (optional)",
            ["risky", "tool", "simple", "missing_info", "error"],
        )
        thread_id = st.text_input("Thread ID", "thread-custom-001")

    if st.button("Submit Query to Agent", type="primary"):
        scenario = Scenario(id="custom_run", query=user_query, expected_route=Route(custom_route))
        state = initial_state(scenario)
        state["thread_id"] = thread_id
        config = {"configurable": {"thread_id": thread_id}}

        with st.spinner("Agent running through LangGraph StateGraph..."):
            result = graph.invoke(state, config=config)

        st.success("Execution Complete!")
        res_col1, res_col2 = st.columns(2)
        with res_col1:
            st.metric("Classified Route", result.get("route", "N/A"))
            st.metric("Risk Level", result.get("risk_level", "low"))
            st.write("**Final Answer / Response:**")
            st.info(result.get("final_answer") or result.get("pending_question") or "No answer returned")
        with res_col2:
            st.write("**Visited Nodes & Audit Events:**")
            events = result.get("events", [])
            for e in events:
                st.write(f"- `{e.get('node')}`: {e.get('message')}")

with tabs[1]:
    st.subheader("Batch Sample Scenarios")
    sample_file = "data/sample/scenarios.jsonl"
    if Path(sample_file).exists():
        scenarios = load_scenarios(sample_file)
        st.write(f"Loaded {len(scenarios)} scenarios from `{sample_file}`.")
        if st.button("Run All Scenarios"):
            results = []
            progress = st.progress(0)
            for i, sc in enumerate(scenarios):
                st_init = initial_state(sc)
                cfg = {"configurable": {"thread_id": st_init["thread_id"]}}
                res = graph.invoke(st_init, config=cfg)
                events = res.get("events", [])
                nodes = [e.get("node") for e in events]
                matched = res.get("route") == sc.expected_route.value
                results.append({
                    "ID": sc.id,
                    "Query": sc.query,
                    "Expected": sc.expected_route.value,
                    "Actual": res.get("route"),
                    "Success": "✅" if matched else "❌",
                    "Nodes": len(nodes),
                })
                progress.progress((i + 1) / len(scenarios))
            st.dataframe(results, use_container_width=True)

with tabs[2]:
    st.subheader("Inspect State Checkpoints")
    inspect_thread = st.text_input("Enter Thread ID to Inspect", "thread-custom-001")
    if st.button("Load Checkpoints"):
        try:
            inspect_config = {"configurable": {"thread_id": inspect_thread}}
            history = list(graph.get_state_history(inspect_config))
            st.write(f"Found {len(history)} checkpoint snapshots for thread `{inspect_thread}`")
            for i, snap in enumerate(history):
                with st.expander(f"Checkpoint #{i+1} — Node: {snap.metadata.get('langgraph_node', 'START')}"):
                    st.json(snap.values)
        except Exception as ex:
            st.error(f"Error reading checkpoint history: {ex}")

with tabs[3]:
    st.subheader("StateGraph Architecture")
    diagram_path = Path("outputs/graph_diagram.mmd")
    if diagram_path.exists():
        st.code(diagram_path.read_text(encoding="utf-8"), language="mermaid")
    else:
        st.info("Run `python scripts/export_diagram.py` to generate the diagram.")
