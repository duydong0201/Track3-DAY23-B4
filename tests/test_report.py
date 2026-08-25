"""Unit tests for report rendering and writing."""

from pathlib import Path

from langgraph_agent_lab.metrics import ScenarioMetric, summarize_metrics
from langgraph_agent_lab.report import render_report, write_report


def test_render_report():
    sm1 = ScenarioMetric(
        scenario_id="S01_simple",
        success=True,
        expected_route="simple",
        actual_route="simple",
        nodes_visited=4,
        retry_count=0,
        interrupt_count=0,
    )
    sm2 = ScenarioMetric(
        scenario_id="S04_risky",
        success=True,
        expected_route="risky",
        actual_route="risky",
        nodes_visited=8,
        retry_count=0,
        interrupt_count=1,
    )
    report = summarize_metrics([sm1, sm2])
    md = render_report(report)

    assert "# Day 08 Lab Report" in md
    assert "S01_simple" in md
    assert "S04_risky" in md
    assert "100.0%" in md
    assert "## 1. Team / student" in md
    assert "## 2. Architecture" in md
    assert "## 3. State schema" in md
    assert "## 4. Scenario results" in md
    assert "## 5. Failure analysis" in md
    assert "## 6. Persistence / recovery evidence" in md
    assert "## 7. Extension work" in md
    assert "## 8. Improvement plan" in md


def test_write_report(tmp_path: Path):
    sm = ScenarioMetric(
        scenario_id="test",
        success=True,
        expected_route="simple",
        actual_route="simple",
        nodes_visited=3,
        retry_count=0,
        interrupt_count=0,
    )
    report = summarize_metrics([sm])
    out_file = tmp_path / "test_report.md"
    write_report(report, out_file)

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "test" in content
