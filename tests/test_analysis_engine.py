from __future__ import annotations

import pandas as pd

from laser_knowledge_system.analysis.engine import AnalysisEngine


def test_analysis_engine_builds_dataframe_from_runs() -> None:
    engine = AnalysisEngine()
    runs = [
        {"power_w": 20, "speed_mm_s": 100, "quality": 5.0},
        {"power_w": 25, "speed_mm_s": 120, "quality": 7.0},
    ]

    df = engine.build_run_dataframe(runs)

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["power_w", "speed_mm_s", "quality"]
    assert len(df) == 2
