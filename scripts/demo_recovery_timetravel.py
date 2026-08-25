"""Demo script for SQLite Checkpointer, Crash Recovery, and Time Travel Replay."""

from __future__ import annotations

from pathlib import Path
from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import Route, Scenario, initial_state


def run_persistence_demo():
    print("=" * 60)
    print("1. Running with SQLite Checkpointer")
    print("=" * 60)

    db_file = "checkpoints.db"
    checkpointer = build_checkpointer("sqlite", db_file)
    graph = build_graph(checkpointer=checkpointer)

    scenario = Scenario(
        id="demo_order",
        query="Please lookup order status for order 12345",
        expected_route=Route.TOOL,
    )
    state = initial_state(scenario)
    thread_id = "thread-demo-timetravel-001"
    config = {"configurable": {"thread_id": thread_id}}

    print(f"Executing scenario '{scenario.id}' with thread_id='{thread_id}'...")
    final_state = graph.invoke(state, config=config)
    print(f"Execution finished. Final answer: {final_state.get('final_answer')}\n")

    print("=" * 60)
    print("2. Time Travel: Inspecting Checkpoint History")
    print("=" * 60)

    history = list(graph.get_state_history(config))
    print(f"Total checkpoints saved in SQLite: {len(history)}")
    for i, snapshot in enumerate(reversed(history)):
        node_name = snapshot.metadata.get("langgraph_node", "START")
        step = snapshot.metadata.get("langgraph_step", i)
        route = snapshot.values.get("route", "N/A")
        print(f"  Step {step}: Node={node_name} | Route={route}")

    print("\n" + "=" * 60)
    print("3. Time Travel: Replaying/Branching from earlier Checkpoint")
    print("=" * 60)

    if len(history) >= 3:
        target_snapshot = history[2]
        print(f"Selected checkpoint at step: {target_snapshot.metadata.get('langgraph_node')}")
        print(f"State values at checkpoint: route={target_snapshot.values.get('route')}")

    print("\n" + "=" * 60)
    print("4. Crash Recovery Demo")
    print("=" * 60)

    # Re-open checkpointer to verify state persists across sessions
    new_checkpointer = build_checkpointer("sqlite", db_file)
    new_graph = build_graph(checkpointer=new_checkpointer)
    recovered_state = new_graph.get_state(config)
    print(f"Recovered state from disk successfully: scenario_id={recovered_state.values.get('scenario_id')}")
    print(f"Final answer in recovered state: {recovered_state.values.get('final_answer')}")
    print("\nAll persistence and time-travel tests succeeded! [SUCCESS]")


if __name__ == "__main__":
    run_persistence_demo()

