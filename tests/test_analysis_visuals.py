from __future__ import annotations

from laser_knowledge_system.analysis.engine import AnalysisEngine


def test_analysis_engine_can_generate_graph_payloads() -> None:
    engine = AnalysisEngine()
    runs = [
        {"power_w": 20, "speed_mm_s": 100, "quality": 5.0},
        {"power_w": 25, "speed_mm_s": 150, "quality": 6.0},
        {"power_w": 30, "speed_mm_s": 200, "quality": 8.0},
    ]

    payload = engine.plot_quality_against_power(runs)

    assert payload["x"] == [20, 25, 30]
    assert payload["y"] == [5.0, 6.0, 8.0]
    assert payload["title"] == "Power vs Quality"
