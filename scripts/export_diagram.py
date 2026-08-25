"""Export LangGraph diagram to Mermaid .mmd file."""

from pathlib import Path
from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer

def export_mermaid_diagram(output_path: str = "outputs/graph_diagram.mmd") -> str:
    graph = build_graph(checkpointer=build_checkpointer("memory"))
    mermaid_code = graph.get_graph().draw_mermaid()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(mermaid_code, encoding="utf-8")
    print(f"Graph diagram exported to {out}")
    return mermaid_code

if __name__ == "__main__":
    export_mermaid_diagram()
